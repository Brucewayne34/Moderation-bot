# Guardian+ Moderation & Anti-Nuke Bot

![Banner](https://i.pinimg.com/originals/5d/2c/44/5d2c44694918947aede42306cb7154d0.gif)

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.4%2B-blue.svg)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Brucewayne34/guardian-plus-bot?style=social)](https://github.com/Brucewayne34/guardian-plus-bot/stargazers)

---

## ✨ Features

### 🛡 Anti-Nuke Protection
- Stops **mass channel deletions**, **mass role deletions**, and **dangerous permission grants**
- Blocks spam, unsolicited **Discord invite links**, and **NSFW images**
- Automatic timeouts / punishments configurable via setup

### ⚔ Moderation Tools
- `warn`, `removewarn`, `warnings` (with DM notification)
- `kick`, `ban`, `unban`
- `mute` / `timeout`, `unmute` / `removetimeout`
- `jail` / `unjail`
- `purge`, `purgebots`

### ⚙ Utility Commands
- `setup` wizard
- `setlog` for moderation logs
- `uptime`, `stats`, `ping`
- Server, user, role, and channel info
- Avatar & banner fetcher

### 🎯 Fun & Misc
- `say`, `embed`
- `poll`, `8ball`, `choose`, `roll`
- `quote`, `remindme`
- `github` link

---

## 📸 Screenshots
> Replace with your own screenshots
- **Setup Wizard**: ![Setup Wizard](link-to-your-screenshot)
- **Moderation Example**: ![Moderation Example](link-to-your-screenshot)
- **Anti-Nuke Log**: ![Anti-Nuke Log](link-to-your-screenshot)

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Discord Bot Token
- (Optional) MongoDB connection string

### Installation
```bash
git clone https://github.com/Brucewayne34/guardian-plus-bot.git
cd guardian-plus-bot
pip install -r requirements.txt
```

### Configuration
1. Copy `config.sample.json` to `config.json`
2. Fill in your bot token and MongoDB URI (if using MongoDB)
3. Enable **Server Members Intent** and **Message Content Intent** in the [Discord Developer Portal](https://discord.com/developers/applications)

### Running the Bot
```bash
python bot.py
```

---

## 🛠 Command Examples
```bash
-warn @user Spamming in chat
-removewarn 123456
-jail @user 1d Breaking rules
-ban @user Advertising
/ban @user reason: "Toxic behavior"
```

---

## 👨‍💻 Developer
**Bruce Wayne**  
[![GitHub](https://img.shields.io/badge/GitHub-Brucewayne34-black?logo=github)](https://github.com/Brucewayne34)

![Bruce's GitHub stats](https://github-readme-stats.vercel.app/api?username=Brucewayne34&show_icons=true&theme=tokyonight)
![Top Langs](https://github-readme-stats.vercel.app/api/top-langs/?username=Brucewayne34&layout=compact&theme=tokyonight)

---

## 📜 License
MIT License

> Developed with ❤️ by Bruce Wayne
