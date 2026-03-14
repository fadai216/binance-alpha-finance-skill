# 🍼 Binance Alpha Finance Skill 保姆级教程

欢迎使用！本教程专为“小白”设计，即便你完全没写过代码，只要跟着步骤走也能成功运行。

---

## 🛠️ 第一步：准备工作 (Pre-check)

在开始之前，请确保你的电脑已经安装了以下两个基础工具：

1.  **Git** (用来下载代码)
    - [下载地址](https://git-scm.com/downloads)
    - 安装完成后，在终端输入 `git --version` 看到数字即成功。
2.  **Python 3.11 或更高版本** (用来运行程序)
    - [下载地址](https://www.python.org/downloads/)
    - **注意**：Windows 用户安装时务必勾选 **"Add Python to PATH"** 复选框！
    - 安装完成后，在终端输入 `python --version` 看到数字即成功。

> **💡 什么是终端 (Terminal)？**
> - **Windows 用户**：点击开始菜单，搜索 `PowerShell` 并打开。
> - **Mac 用户**：点击 Command+空格，搜索 `Terminal` 并打开。

---

## 📥 第二步：下载与安装 (Install)

请在你的终端里**一行一行**复制并执行以下命令：

### 1. 下载项目
```bash
git clone https://github.com/fadai216/binance-alpha-finance-skill.git ~/.openclaw/skills/binance-alpha-finance
```

### 2. 进入目录
```bash
cd ~/.openclaw/skills/binance-alpha-finance
```

### 3. 一键启动后端
```bash
bash scripts/ensure_backend.sh
```
**✨ 成功的样子：**
脚本运行完后，如果最后几行显示 `Backend is healthy at 127.0.0.1:8000`，说明你的“理财数据大脑”已经成功启动了！

---

## 🔑 第三步：配置 API Key (进阶可选)

默认情况下，你只能看到“活动公告”中的理财产品。如果你想看**完整的币安理财池**，需要配置 API Key：

1. 找到项目根目录下的 `config.json`（或者根据你的系统环境配置）。
2. 为了简单起见，小白可以直接在终端输入：
   ```bash
   export BINANCE_API_KEY="你的Key"
   export BINANCE_API_SECRET="你的Secret"
   ```
   *注意：这种方式在关闭终端后会失效。长期使用建议在 OpenClaw 的环境变量或 `.env` 文件中配置。*

---

## 🔍 第四步：如何查询数据 (Quick Query)

现在你的后端已经在后台默默运行了，你可以试着运行以下命令来看看它抓到了什么：

### 1. 看看当前最稳的 Alpha 代币
```bash
bash scripts/query.sh alpha 'top=3'
```

### 2. 看看高收益理财产品
```bash
bash scripts/query.sh finance 'sort_by=apr&limit=5'
```

### 3. 获取一份投资建议摘要 (Copilot)
```bash
bash scripts/query.sh summary 'style=balanced'
```
**✨ 成功的样子：**
你会看到一串 JSON 格式的数据。别担心，如果你把这个 Skill 接进 **OpenClaw**，AI Agent 会把这些枯燥的数据变成好听的人话告诉你。

---

## 🤖 在 OpenClaw 中怎么用？

这个项目是 OpenClaw 的“技能包”。配置好后，你可以直接问 AI：
- *“帮我分析一下最近币安最稳的 Alpha 币。”*
- *“今天有哪些高年化的理财活动可以参加？”*
- *“根据我的保守型风格，给出一份理财建议。”*

---

## 🆘 常见问题 (FAQ)

### 1. 运行 `ensure_backend.sh` 没反应或报错？
- 检查你的网络是否能正常访问币安 API。
- 确保 Python 版本是 3.11 或更高。

### 2. 为什么我看不到某些币种的理财？
- 如果没配 API Key，数据来源仅限公开的活动公告。配上 API Key 后即可解锁完整池子。

### 3. 如何更新到最新版？
```bash
cd ~/.openclaw/skills/binance-alpha-finance
git pull
bash scripts/ensure_backend.sh
```

---
**现在，你已经完成了所有设置！快去和你的 AI 助手聊聊币安行情吧！🚀**
