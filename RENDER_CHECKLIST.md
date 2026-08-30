# Render Deployment Checklist ✅

## Pre-Deployment
- [ ] Have GitHub account
- [ ] Have Telegram Bot Token from @BotFather
- [ ] Created GitHub repository with code
- [ ] Pushed all files to main branch
- [ ] Have Render account (free at render.com)

## Files Prepared
- [ ] telegram_crunchyroll_render.py (main bot with Flask)
- [ ] emoji_pack.json (in same directory)
- [ ] requirements.txt (with Flask + Gunicorn)
- [ ] Procfile (web: python telegram_crunchyroll_render.py)
- [ ] render.yaml (optional service config)

## Step 1: GitHub Setup
```bash
# Local machine
git init
git add .
git commit -m "Initial deployment"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/crunchyroll-bot.git
git push -u origin main
```
- [ ] GitHub repo created
- [ ] All files pushed
- [ ] Repository is public or Render has access

## Step 2: Render Deployment
1. Go to https://render.com
2. Sign in with GitHub
3. Click "New +" → "Web Service"
4. Select your GitHub repository
5. Configuration:
   - [ ] Name: `crunchyroll-checker-bot`
   - [ ] Environment: `Python 3`
   - [ ] Build Command: `pip install -r requirements.txt`
   - [ ] Start Command: `python telegram_crunchyroll_render.py`
   - [ ] Plan: `Free`

## Step 3: Environment Variables
In Render Dashboard → Environment:
```
BOT_TOKEN = {paste_your_actual_token}
ADMIN_USERNAME = @ego_exist
PORT = 5000
```
- [ ] BOT_TOKEN added
- [ ] ADMIN_USERNAME set
- [ ] Saved

## Step 4: Deployment
- [ ] Click "Create Web Service"
- [ ] Watch build progress in logs
- [ ] Wait for "Live" status
- [ ] Copy your URL: `https://crunchyroll-bot-xxx.onrender.com`

## Step 5: Test Health Endpoint
```bash
curl https://crunchyroll-bot-xxx.onrender.com/health
```
- [ ] Returns status: "alive"
- [ ] Response time < 1 second
- [ ] HTTP 200 status

## Step 6: Setup External Pinging (CRITICAL for 24/7)

### Option A: UptimeRobot (Recommended)
1. Go to https://uptimerobot.com
2. Sign up with email (free)
3. Verify email
4. Click "Add New Monitor"
5. Settings:
   - [ ] Monitor Type: HTTP(s)
   - [ ] Friendly Name: Crunchyroll Bot Health
   - [ ] URL: https://crunchyroll-bot-xxx.onrender.com/health
   - [ ] Check Interval: 5 minutes
   - [ ] Click "Create Monitor"
6. Verify working:
   ```bash
   curl https://crunchyroll-bot-xxx.onrender.com/health
   ```

### Option B: Cron-Job.org
1. Go to https://cron-job.org
2. Create account
3. Create new cronjob:
   - [ ] Title: Bot Health Check
   - [ ] URL: https://crunchyroll-bot-xxx.onrender.com/ping
   - [ ] Interval: Every 5 minutes
   - [ ] Save

### Option C: EasyCron
1. Go to https://www.easycron.com
2. Sign up
3. Create cron:
   - [ ] Cron: `*/5 * * * *`
   - [ ] URL: https://crunchyroll-bot-xxx.onrender.com/health
   - [ ] Save

- [ ] External pinging service active
- [ ] Pinging every 5 minutes

## Step 7: Verify Bot Working
In Telegram:
1. Message your bot
2. Click /start
3. Try "Check Account"
4. Try Settings
5. If admin, check Admin Panel

- [ ] Bot responds to messages
- [ ] Buttons work
- [ ] Settings save to database
- [ ] Admin can access panel

## Step 8: Monitor Logs
```
Render Dashboard → Services → crunchyroll-checker-bot → Logs
```
- [ ] Look for health check pings every 5 min
- [ ] No error messages
- [ ] Bot polling messages

## Step 9: Continuous Monitoring
1. Set up UptimeRobot alerts
2. Get email when bot goes down
3. Check dashboard weekly
4. Monitor response times

- [ ] Alerts configured
- [ ] Email notifications enabled
- [ ] Dashboard bookmarked

## Troubleshooting Checklist

If bot offline:
- [ ] Check Render logs for errors
- [ ] Verify BOT_TOKEN is correct
- [ ] Check emoji_pack.json exists
- [ ] Test health endpoint manually
- [ ] Restart service in Render dashboard

If external pinging not working:
- [ ] Verify pinging service created
- [ ] Check pinging service settings
- [ ] Test URL in browser
- [ ] Check Render logs for 404 errors

If database issues:
- [ ] Database auto-created first run
- [ ] Settings persist after restart
- [ ] Check /status endpoint shows config

## Files to Update When Making Changes

1. **Bot code changes:**
   - Edit telegram_crunchyroll_render.py
   - Commit & push to GitHub
   - Render auto-deploys in 1 min

2. **Emoji pack changes:**
   - Replace emoji_pack.json
   - Commit & push
   - Auto-deploy

3. **Dependency changes:**
   - Update requirements.txt
   - Commit & push
   - Auto-deploy rebuilds

## 24/7 Status Indicators

✅ Bot is 24/7 if:
- Health endpoint responds
- External pinging active
- No gaps in logs (every 5 min)
- Telegram messages answered instantly
- UptimeRobot shows 100% uptime

❌ Bot is NOT 24/7 if:
- Health endpoint times out
- External pinging paused
- Render service in "Spinning Down"
- No ping logs for >15 minutes
- UptimeRobot shows downtime

## Final Status

After completing all steps:
```
✅ Bot deployed to Render
✅ Health endpoint active
✅ External pinging configured
✅ Database persistent
✅ Admin panel working
✅ Emoji pack loaded
✅ 24/7 uptime guaranteed
```

**Bot is now LIVE 24/7!** 🚀🔥

Ping baby, we're up forever.
