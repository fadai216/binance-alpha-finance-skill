from __future__ import annotations

import time as _time
from datetime import UTC, datetime
from typing import Any

from alpha_monitor.config import Settings, get_settings
from web3_wallet_monitor.client import Web3WalletClient, Web3WalletError
from web3_wallet_monitor.storage import load_state, save_state

_STATE_CACHE_TTL = 20.0

# Known stablecoins for categorization
_STABLECOINS = frozenset(
    {
        "USDT", "USDC", "BUSD", "TUSD", "FDUSD", "DAI", "FRAX", "LUSD", "PYUSD",
        "USDD", "USDP", "GUSD", "crvUSD", "USDe", "sUSDe", "GHO", "USD1", "lisUSD",
        "TUSDOLD",
    }
)

# Protocol trust tier (higher = more trusted); key is lowercase for case-insensitive lookup
_PROTOCOL_TRUST: dict[str, int] = {"aave": 2, "venus": 1}


class Web3WalletService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.client = Web3WalletClient(self.settings)
        self._state_cache: dict[str, Any] | None = None
        self._state_cache_at: float = 0.0

    def _load_state(self) -> dict[str, Any]:
        now = _time.monotonic()
        if self._state_cache is not None and (now - self._state_cache_at) < _STATE_CACHE_TTL:
            return self._state_cache
        state = load_state(self.settings.web3_wallet_cache_file)
        self._state_cache = state
        self._state_cache_at = now
        return state

    def _invalidate_state_cache(self) -> None:
        self._state_cache = None

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> dict[str, Any]:
        pools_raw = self.client.fetch_defi_earn_pools()
        pools = [self._normalize_pool(p) for p in pools_raw]
        pools = [p for p in pools if p is not None]

        snapshot = {
            "pools": pools,
            "updated_at": datetime.now(UTC).isoformat(),
            "source": "web3-defi-earn",
            "total": len(pools),
        }

        state = load_state(self.settings.web3_wallet_cache_file)
        state["latest_snapshot"] = snapshot
        state["last_refresh_error"] = None
        save_state(self.settings.web3_wallet_cache_file, state)
        self._invalidate_state_cache()
        return snapshot

    def refresh_safe(self) -> dict[str, Any]:
        try:
            return self.refresh()
        except Exception as exc:  # noqa: BLE001
            state = load_state(self.settings.web3_wallet_cache_file)
            state["last_refresh_error"] = {
                "message": str(exc),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            save_state(self.settings.web3_wallet_cache_file, state)
            raise

    def is_refresh_due(self) -> bool:
        state = self._load_state()
        snapshot = state.get("latest_snapshot")
        if not snapshot:
            return True
        try:
            updated = datetime.fromisoformat(snapshot["updated_at"])
            age = (datetime.now(UTC) - updated).total_seconds()
            return age >= self.settings.finance_refresh_interval_seconds
        except (KeyError, ValueError):
            return True

    # ------------------------------------------------------------------
    # Normalization & scoring
    # ------------------------------------------------------------------

    def _normalize_pool(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        tokens = raw.get("tokens") or []
        if not tokens:
            return None
        token = tokens[0]
        symbol = token.get("symbol") or ""
        if not symbol:
            return None

        apy = float(raw.get("apy") or 0)
        tvl = float(raw.get("tvl") or 0)
        protocol = raw.get("protocol") or "Unknown"
        network = raw.get("networkId") or "Unknown"
        token_type = "stablecoin" if symbol.upper() in _STABLECOINS else "volatile"
        score = self._score_pool(apy, tvl, protocol, token_type)

        return {
            "pool_id": raw.get("poolId") or "",
            "symbol": symbol,
            "protocol": protocol,
            "network": network,
            "chain_id": raw.get("binanceChainId"),
            "apy": round(apy * 100, 4),  # convert to percentage
            "tvl_usd": round(tvl, 2),
            "token_type": token_type,
            "contract_address": token.get("contractAddress") or "",
            "ctoken_symbol": token.get("csymbol") or "",
            "pool_type": raw.get("type") or "LENDING",
            "score": round(score, 2),
            "score_label": self._score_label(score),
        }

    @staticmethod
    def _score_pool(apy: float, tvl: float, protocol: str, token_type: str) -> float:
        """Score 0-100. Higher = better opportunity (APY + safety)."""
        # APY component (0-40): raw APY maps to score, capped at 15% APY
        apy_pct = apy * 100
        apy_score = min(apy_pct / 15.0, 1.0) * 40

        # TVL component (0-30): log-scale, $10M+ = full score
        import math
        if tvl > 0:
            tvl_score = min(math.log10(tvl) / math.log10(1e7), 1.0) * 30
        else:
            tvl_score = 0.0

        # Protocol trust (0-20); case-insensitive
        trust = _PROTOCOL_TRUST.get(protocol.lower(), 0)
        max_trust = max(_PROTOCOL_TRUST.values())
        protocol_score = (trust / max_trust) * 20 if max_trust > 0 else 0

        # Stablecoin bonus (0-10): stablecoins safer for passive income
        stable_score = 10.0 if token_type == "stablecoin" else 0.0

        return apy_score + tvl_score + protocol_score + stable_score

    @staticmethod
    def _score_label(score: float) -> str:
        if score >= 70:
            return "excellent"
        if score >= 50:
            return "good"
        if score >= 30:
            return "fair"
        return "low"

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_pools(
        self,
        *,
        protocol: str = "all",
        network: str = "all",
        token_type: str = "all",
        sort_by: str = "score",
        order: str = "desc",
        min_apy: float = 0.0,
        limit: int | None = None,
    ) -> dict[str, Any]:
        limit = limit or 20
        state = self._load_state()
        snapshot = state.get("latest_snapshot") or {}
        pools = list(snapshot.get("pools") or [])

        if protocol != "all":
            pools = [p for p in pools if p.get("protocol", "").lower() == protocol.lower()]
        if network != "all":
            pools = [p for p in pools if p.get("network", "").lower() == network.lower()]
        if token_type != "all":
            pools = [p for p in pools if p.get("token_type") == token_type]
        if min_apy > 0:
            pools = [p for p in pools if float(p.get("apy") or 0) >= min_apy]

        reverse = order != "asc"
        if sort_by == "apy":
            pools.sort(key=lambda p: float(p.get("apy") or 0), reverse=reverse)
        elif sort_by == "tvl":
            pools.sort(key=lambda p: float(p.get("tvl_usd") or 0), reverse=reverse)
        elif sort_by == "symbol":
            pools.sort(key=lambda p: p.get("symbol") or "", reverse=reverse)
        else:
            pools.sort(key=lambda p: float(p.get("score") or 0), reverse=reverse)

        top_stable = self._top_by(snapshot.get("pools") or [], "stablecoin", "apy")
        top_volatile = self._top_by(snapshot.get("pools") or [], "volatile", "apy")
        top_tvl = self._top_by(snapshot.get("pools") or [], "all", "tvl_usd")

        protocol_summary = self._protocol_summary(snapshot.get("pools") or [])

        return {
            "items": pools[:limit],
            "total": len(pools),
            "updated_at": snapshot.get("updated_at") or datetime.now(UTC).isoformat(),
            "source": snapshot.get("source"),
            "top_apy_stable": top_stable,
            "top_apy_volatile": top_volatile,
            "top_tvl": top_tvl,
            "protocol_summary": protocol_summary,
            "last_refresh_error": state.get("last_refresh_error"),
        }

    @staticmethod
    def _top_by(
        pools: list[dict[str, Any]],
        token_type: str,
        key: str,
    ) -> dict[str, Any] | None:
        filtered = pools if token_type == "all" else [p for p in pools if p.get("token_type") == token_type]
        if not filtered:
            return None
        return max(filtered, key=lambda p: float(p.get(key) or 0))

    @staticmethod
    def _protocol_summary(pools: list[dict[str, Any]]) -> dict[str, Any]:
        summary: dict[str, dict[str, Any]] = {}
        for pool in pools:
            proto = pool.get("protocol") or "Unknown"
            if proto not in summary:
                summary[proto] = {"pool_count": 0, "total_tvl_usd": 0.0, "avg_apy": 0.0, "_apy_sum": 0.0}
            summary[proto]["pool_count"] += 1
            summary[proto]["total_tvl_usd"] += float(pool.get("tvl_usd") or 0)
            summary[proto]["_apy_sum"] += float(pool.get("apy") or 0)
        for proto, s in summary.items():
            count = s["pool_count"]
            s["avg_apy"] = round(s["_apy_sum"] / count, 4) if count else 0.0
            s["total_tvl_usd"] = round(s["total_tvl_usd"], 2)
            del s["_apy_sum"]
        return summary
