# 🎬 Telegram AutoFilter Bot — Premium + Shortener + Free Trial

A production-ready PM/Group auto-filter bot on **MongoDB**, built with **Pyrogram (pyrofork)**,
fully async so it handles hundreds of users at once without freezing.

## ✨ Features

| Feature | Command / How |
|---|---|
| Auto Filter (group + PM) | just send a name |
| Manual Filter (custom name + photo + buttons) | `/addfilter`, `/delfilter`, `/filters` |
| Link Shortener verification | automatic for free users |
| Free trial — 2 clicks for new users | automatic (`FREE_TRIAL_CLICKS`) |
| Premium membership | `/premium`, `/myplan`, `/addpremium id days`, `/removepremium id`, `/premiumusers` |
| Auto expiry + expiry DM | background worker every 10 min |
| Index old files | forward last channel message / send its link → `/index` |
| Index new files | automatic for every channel in `CHANNELS` |
| Batch file store | `/batch first_link last_link`, `/link` (reply to a file) |
| Pagination, page counter, close button | inline UI |
| Auto delete files after N min | `AUTO_DELETE`, `DELETE_TIME` |
| Force subscribe | `AUTH_CHANNEL` |
| Broadcast | reply to a message + `/broadcast` |
| Ban / unban users | `/ban id`, `/unban id` |
| Stats, users, logs | `/stats`, `/users`, `/logs` |
| Delete files | `/delete name`, `/deleteall` |
| Health endpoint for uptime monitors | `http://your-ip:8080/` |

### Access logic (exactly as requested)
1. **Premium user** → clicks a button → gets the file instantly, no shortlink.
2. **New user** → gets **2 free clicks** (no shortlink at all).
3. **After the trial** → bot sends a **shortened verification link**; opening it unlocks
   all files for `VERIFY_HOURS` (default 24h). Repeats after that.
4. Premium expiry is calculated automatically and the user is downgraded with a DM.

---

## 🚀 Setup Guide

### 1. Get your credentials
* `API_ID` / `API_HASH` → https://my.telegram.org → API development tools
* `BOT_TOKEN` → [@BotFather](https://t.me/BotFather) → `/newbot`
* Your numeric id → send `/id` to the bot or [@userinfobot](https://t.me/userinfobot)

### 2. MongoDB
1. Create a free cluster on https://cloud.mongodb.com
2. Database Access → add a user (password auth)
3. Network Access → **Allow access from anywhere** (`0.0.0.0/0`)
4. Connect → Drivers → copy the URI → put it in `DATABASE_URI`

### 3. Channels
* Create your **database channel(s)**, upload files there, **make the bot admin**.
* Copy each channel id (forward a post to the bot and use `/id`) into `CHANNELS`.
* Create a private **log channel**, make the bot admin, put the id in `LOG_CHANNEL`.

### 4. Shortener
Sign up at any shortener that uses the standard API (`shrinkme.io`, `gplinks.in`,
`droplink.co`, `omnifly.in.net`, `mdisk`, `shareus.io`…), copy the API token:
```
SHORTENER_SITE=shrinkme.io
SHORTENER_API=xxxxxxxxxxxxxxxxxx
```
Set `IS_SHORTENER=False` to disable verification completely.

### 5. Run on a VPS (Ubuntu 22.04 / 24.04)
```bash
apt update && apt install -y python3 python3-pip python3-venv git screen
git clone <your-repo>  autofilter-bot   # or upload this folder
cd autofilter-bot
cp sample.env .env && nano .env          # fill in your values
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```
Keep it alive forever:
```bash
# option A — screen
screen -S bot
python3 bot.py       # Ctrl+A then D to detach

# option B — systemd (recommended)
cp autofilter.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now autofilter
systemctl status autofilter        # logs: journalctl -u autofilter -f
```

### 6. Docker (optional)
```bash
cp sample.env .env && nano .env
docker compose up -d --build
docker compose logs -f
```

---

## 📥 Indexing your old files
1. Make the bot **admin** in the database channel.
2. Forward the **last** message of that channel to the bot in PM (as admin), **or**
   send its link e.g. `https://t.me/c/1234567890/9999`.
3. Press **✅ Start indexing**. Progress updates every 100 messages; you can cancel anytime.

New files posted to `CHANNELS` are indexed automatically.

## 🧩 Manual filter example
Reply to a poster image in your group:
```
/addfilter "Animal 2023" <b>Animal (2023) Hindi</b>
[480p](buttonurl:https://t.me/yourchannel/12)
[720p](buttonurl:https://t.me/yourchannel/13)
```
Now anyone searching `Animal 2023` gets your custom poster + buttons instead of the raw list.
Run `/addfilter` in the bot's **PM** (as admin) to make it **global** for every group.

## 💎 Selling premium
* User sends `/premium` → sees the price (`₹50/month`) and your contact button.
* After payment you run: `/addpremium 123456789 30`
* Remove early: `/removepremium 123456789`
* List actives: `/premiumusers` · user checks with `/myplan`

## 🛠 Troubleshooting
| Problem | Fix |
|---|---|
| `Missing required config` | fill `.env` (copied from `sample.env`) |
| Bot doesn't answer in group | make it **admin** with *delete messages* permission, and disable group privacy in BotFather (`/setprivacy` → Disable) |
| `PEER_ID_INVALID` on send | the user hasn't started the bot in PM |
| No search results | run indexing; check `CHANNELS` ids start with `-100` |
| Shortlink not generated | wrong `SHORTENER_SITE`/`SHORTENER_API`; bot falls back to a normal link |
| MongoDB timeout | whitelist `0.0.0.0/0` in Network Access |

## ⚡ Performance notes
* MongoDB **text + name indexes** are created on startup — searches stay fast on 1M+ files.
* Motor connection pool (100) + Pyrogram 50 workers → many concurrent users.
* Broadcast and batch sending are rate-limited (`asyncio.sleep`) to avoid FloodWait bans.
