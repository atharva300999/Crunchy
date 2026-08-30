# Render Deployment Guide - 24/7 Bot Uptime

## Overview
This guide covers deploying your Crunchyroll bot to Render with:
- ✅ Automatic health checks
- ✅ External pinging for 24/7 uptime
- ✅ Flask health endpoint
- ✅ Zero downtime deployment
- ✅ Free tier compatible

## Prerequisites
- Render account (free tier available at render.com)
- GitHub repo with bot code
- Telegram Bot Token (from @BotFather)
- Optional: UptimeRobot account (free tier at uptimerobot.com)

## Step 1: Prepare GitHub Repository

### Create repo structure:
```
crunchyroll-bot/
├── telegram_crunchyroll_render.py
├── requirements.txt
├── Procfile
├── render.yaml
├── emoji_pack.json
└── README.md
```

### Push to GitHub:
```bash
git init
git add .
git commit -m "Initial bot deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/crunchyroll-bot.git
git push -u origin main
```

## Step 2: Connect to Render

1. Go to https://render.com
2. Sign up with GitHub account
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Select the repo containing bot code

## Step 3: Configure Render Service

**Basic Settings:**
- Name: `crunchyroll-checker-bot`
- Environment: `Python 3`
- Build Command: `pip install -r requirements.txt`
- Start Command: `python telegram_crunchyroll_render.py`
- Instance Type: `Free` (or Starter for production)

**Environment Variables:**
Add these in Render dashboard → Environment:

```
BOT_TOKEN = your_actual_bot_token_here
ADMIN_USERNAME = @ego_exist
PORT = 5000
```

**Settings:**
- Auto-Deploy: ON (deploys when you push to GitHub)
- Health Check Path: `/health`
- Health Check Interval: 30 seconds

## Step 4: Deploy

Click "Create Web Service" and watch the logs:
```
Building...
Running build command...
Starting service...
```

Your bot is now live at: `https://crunchyroll-bot-xxx.onrender.com`

## Step 5: Set Up External Pinging (24/7 Uptime)

### Why External Pinging?
Render's free tier spins down inactive services after 15 minutes.
External pinging keeps the bot awake 24/7.

### Option A: Use UptimeRobot (Recommended)

1. **Create UptimeRobot Account**
   - Go to https://uptimerobot.com
   - Sign up (free tier)
   - Verify email

2. **Create Monitor**
   - Click "Add New Monitor"
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `Crunchyroll Bot Health`
   - URL: `https://crunchyroll-bot-xxx.onrender.com/health`
   - Monitoring Interval: `5 minutes`
   - Click "Create Monitor"

3. **Configure Alerts**
   - Add notification channel (email, Slack, Discord)
   - Set uptime goal: 99.9%

4. **Verify Working**
   ```bash
   curl https://crunchyroll-bot-xxx.onrender.com/health
   ```
   Should return:
   ```json
   {
     "status": "alive",
     "timestamp": "2024-01-15T10:30:00",
     "bot_active": true,
     "message": "Bot is running and ready to serve"
   }
   ```

### Option B: Use Cron-Job (Alternative)

1. Go to https://cron-job.org
2. Create account (free)
3. Create new cronjob:
   - URL: `https://crunchyroll-bot-xxx.onrender.com/ping`
   - Interval: `Every 5 minutes`
   - HTTP Method: `GET`
   - Save

### Option C: Use EasyCron (Alternative)

1. Go to https://www.easycron.com
2. Sign up (free)
3. Create new cron:
   - Cron Expression: `*/5 * * * *` (every 5 min)
   - URL: `https://crunchyroll-bot-xxx.onrender.com/health`
   - Save

## Step 6: Verify 24/7 Operation

### Check Health Endpoints:

**Full Status:**
```bash
curl https://crunchyroll-bot-xxx.onrender.com/status
```

**Quick Ping:**
```bash
curl https://crunchyroll-bot-xxx.onrender.com/ping
```

**Root Endpoint:**
```bash
curl https://crunchyroll-bot-xxx.onrender.com/
```

### Monitor Logs:
- Render Dashboard → Logs
- Look for health check pings
- Bot should respond to requests 24/7

## How It Works

```
┌─────────────────────────────────────┐
│   UptimeRobot / Cron-Job            │
│   Pings /health every 5 minutes     │
└──────────────┬──────────────────────┘
               │
               ↓
┌─────────────────────────────────────┐
│   Render (crunchyroll-bot-xxx)      │
│                                      │
│   Flask Health Endpoint (/health)   │
│   Updates last_health_check time    │
│   Returns: {"status": "alive"}      │
│                                      │
│   Telegram Bot (Background Thread)  │
│   Polls for messages                │
│   Responds to commands              │
└─────────────────────────────────────┘
```

## Troubleshooting

### Bot offline after deploy:
1. Check Render logs
2. Verify BOT_TOKEN is correct
3. Make sure emoji_pack.json exists
4. Check for Python syntax errors

### Health checks failing:
```bash
# Test endpoint
curl -v https://crunchyroll-bot-xxx.onrender.com/health

# Check response time
curl -w "@curl-format.txt" -o /dev/null -s https://crunchyroll-bot-xxx.onrender.com/health
```

### Bot stopping after 15 minutes:
- Enable external pinging (UptimeRobot, Cron-Job, or EasyCron)
- Verify pinging service is actually running
- Check Render logs for crashes

### "502 Bad Gateway":
- Bot crashed or is starting
- Check Render logs
- Restart service manually if needed

## Monitoring Dashboard

### Render Dashboard:
- https://render.com → Services → crunchyroll-checker-bot
- View real-time logs
- Check CPU/memory usage
- Manual restart option

### UptimeRobot Dashboard:
- https://uptimerobot.com → Dashboard
- Monitor uptime percentage
- View response times
- Check alert history

## Cost

- **Render Free Tier:** $0/month
  - 750 hours per month
  - Shared CPU
  - Perfect for bots
  
- **UptimeRobot Free Tier:** $0/month
  - Unlimited monitors
  - 5-minute checks
  - 50 email alerts/month

**Total: $0/month for full 24/7 operation**

## Environment File (.env) - Optional

Create `.env` file locally:
```
BOT_TOKEN=your_token_here
ADMIN_USERNAME=@ego_exist
PORT=5000
```

Add to Render as individual variables (safer than file).

## Database

Bot uses SQLite (`bot_config.db`):
- Stores proxy config
- Stores channel list
- Persistent across restarts
- Located in ephemeral storage (survives 24h)

For permanent storage, migrate to PostgreSQL (optional upgrade).

## Backup & Recovery

### Download Database:
```bash
render run -s crunchyroll-bot-xxx -- sqlite3 bot_config.db ".dump"
```

### Push Code Updates:
Just commit to GitHub:
```bash
git add .
git commit -m "Update bot"
git push origin main
```

Render auto-redeploys within 1 minute.

## Advanced: Custom Domain

Add custom domain in Render Settings:
- Domain: `bot.yourdomain.com`
- Points to Render's DNS
- HTTPS automatic

## Performance Tips

1. **Health Check Interval:** Keep at 5 minutes
2. **Database:** SQLite fine for current use
3. **Threads:** Bot polling + Flask app work together
4. **Memory:** ~50MB typical usage
5. **Bandwidth:** ~1MB/hour typical

## Security

- Bot token never stored in code
- Environment variables used
- HTTPS enforced
- No API keys in GitHub
- SQLite local only

## Next Steps

1. Deploy to Render
2. Set up UptimeRobot pinging
3. Verify health endpoints respond
4. Test bot commands
5. Monitor logs for 24 hours

You're now 24/7 live! 🚀

## Support

Having issues?

1. Check Render logs
2. Verify environment variables
3. Test health endpoint with curl
4. Restart service in Render dashboard
5. Check UptimeRobot is actually pinging

All systems go. Bot is up forever. 6767.
