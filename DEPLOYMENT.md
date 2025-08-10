# 🚀 Creative Keitaro Bot - Deployment Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Local Development Setup](#local-development-setup)
4. [Production Deployment on Render.com](#production-deployment-on-rendercom)
5. [Environment Variables](#environment-variables)
6. [Database Setup](#database-setup)
7. [Google Services Setup](#google-services-setup)
8. [Monitoring & Troubleshooting](#monitoring--troubleshooting)

## Overview

Creative Keitaro Bot is a Telegram bot for managing media buying creatives and generating analytics reports from Keitaro tracker. This guide covers deployment to Render.com with PostgreSQL database.

### Key Features
- 📊 Advanced Dashboard with traffic source filtering
- 👥 User management and role-based access
- 📈 Detailed analytics reports (buyers, creatives, geo, offers)
- 🔄 Real-time data from Keitaro API
- ☁️ Google Drive integration for file storage
- 📋 Google Sheets integration for data export

## Prerequisites

Before deployment, ensure you have:

1. **Telegram Bot Token** - Create bot via [@BotFather](https://t.me/BotFather)
2. **Keitaro Tracker** - Running instance with API access
3. **Google Cloud Project** - For Drive/Sheets integration
4. **Render.com Account** - For hosting
5. **GitHub Repository** - For code deployment

## Local Development Setup

### 1. Clone Repository
```bash
git clone https://github.com/your-username/creative-keitaro-bot.git
cd creative-keitaro-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Configuration
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Database Setup (Local)
```bash
# Create PostgreSQL database
createdb creative_bot

# Run migrations
alembic upgrade head
```

### 5. Run Bot
```bash
python -m src.bot.main
```

## Production Deployment on Render.com

### Step 1: Prepare Repository

1. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Verify .gitignore**: Ensure no sensitive files are committed:
   - `.env` files
   - `google-service-account.json`
   - `*.log` files
   - `users.json`

### Step 2: Create Render.com Services

#### A. Create PostgreSQL Database

1. Go to [Render.com Dashboard](https://dashboard.render.com)
2. Click **"New PostgreSQL"**
3. Configure:
   - **Name**: `creative-bot-db`
   - **Database**: `creative_bot`
   - **User**: `creative_bot_user`
   - **Region**: Choose closest to your users
   - **Plan**: Start with Free tier
4. Click **"Create Database"**
5. **Save the connection details** - you'll need `DATABASE_URL`

#### B. Create Web Service

1. Click **"New Web Service"**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `creative-keitaro-bot`
   - **Environment**: `Docker`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Build Command**: *(leave empty, handled by Dockerfile)*
   - **Start Command**: *(leave empty, handled by Dockerfile)*

### Step 3: Configure Environment Variables

In your Render.com Web Service settings, add these environment variables:

#### Required Variables
```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather

# Database (automatically provided by Render for PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:port/db

# Keitaro API
KEITARO_BASE_URL=https://your-keitaro.com
KEITARO_API_TOKEN=your_api_token

# Google Services
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
GOOGLE_DRIVE_ROOT_FOLDER_ID=your_folder_id
GOOGLE_SHEETS_MANIFEST_ID=your_sheet_id

# Application
APP_ENV=production
SECRET_KEY=generate_strong_random_string
ALLOWED_USERS=your_telegram_id:owner:

# Optional
LOG_LEVEL=INFO
TZ=Europe/Moscow
```

### Step 4: Deploy

1. Click **"Create Web Service"**
2. Render will automatically:
   - Build Docker image
   - Run database migrations
   - Start the bot
   - Set up health checks

### Step 5: Verify Deployment

1. **Check logs** in Render.com dashboard
2. **Test bot** by sending `/start` to your Telegram bot
3. **Verify database** connection in logs
4. **Test Dashboard** functionality

## Environment Variables

### Core Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather | `1234567890:ABC...` | ✅ |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@host:port/db` | ✅ |
| `KEITARO_BASE_URL` | Keitaro tracker URL | `https://track.example.com` | ✅ |
| `KEITARO_API_TOKEN` | Keitaro API token | `abc123...` | ✅ |
| `SECRET_KEY` | App secret key | `random_string_here` | ✅ |
| `ALLOWED_USERS` | Initial user whitelist | `123:owner:,456:buyer:n1` | ✅ |

### Google Integration

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_PROJECT_ID` | Google Cloud project ID | ✅ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account JSON (as string) | ✅ |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Root folder for uploads | ✅ |
| `GOOGLE_SHEETS_MANIFEST_ID` | Sheet for data export | ✅ |

### Optional Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_ENV` | `production` | Environment mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `TZ` | `Europe/Moscow` | Timezone |
| `MAX_FILE_SIZE_MB` | `50` | Upload limit |
| `CACHE_TTL_SECONDS` | `120` | Cache duration |

## Database Setup

### Automatic Migrations

The bot automatically runs database migrations on startup via `start.sh`:

```bash
alembic upgrade head
```

### Manual Migration (if needed)

If automatic migrations fail:

```bash
# Connect to your Render PostgreSQL via CLI
alembic upgrade head
```

### Database Schema

Key tables:
- `users` - User management and roles
- `creatives` - Uploaded creative assets
- `buyers` - Buyer statistics
- `audit_logs` - System audit trail

## Google Services Setup

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project: `creative-bot`
3. Enable APIs:
   - Google Drive API
   - Google Sheets API

### 2. Create Service Account

1. Go to **IAM & Admin > Service Accounts**
2. Click **"Create Service Account"**:
   - **Name**: `creative-bot-service`
   - **Role**: `Editor`
3. Create and download JSON key
4. **Convert JSON to single line** for environment variable

### 3. Configure Google Drive

1. Create folder in Google Drive for bot uploads
2. Share folder with service account email
3. Copy folder ID from URL: `https://drive.google.com/drive/folders/FOLDER_ID_HERE`

### 4. Configure Google Sheets

1. Create spreadsheet for data export
2. Share with service account email (Editor access)
3. Copy spreadsheet ID from URL

## Monitoring & Troubleshooting

### Health Checks

Render.com automatically monitors:
- HTTP health endpoint: `/health`
- Container health
- Database connectivity

### Log Analysis

**Common log patterns to monitor:**

```bash
# Successful startup
✅ Database initialized successfully!
✅ Bot started successfully!

# API errors
❌ API request failed: 400 - Column 'traffic_source_id' is not defined
CRITICAL: API error mentions 'traffic_source_id'

# Database issues  
❌ Migration failed: connection refused
⚠️ Database initialization failed
```

### Troubleshooting Guide

#### Bot Not Responding
1. **Check environment variables** in Render.com
2. **Verify Telegram token** is correct
3. **Check logs** for startup errors

#### Dashboard Shows Zeros
1. **Verify Keitaro API token** has proper permissions
2. **Check API field names** in logs (should use `ts_id`, not `traffic_source_id`)
3. **Clear cache** by restarting service

#### Database Connection Failed
1. **Verify DATABASE_URL** is properly set
2. **Check PostgreSQL service** is running
3. **Ensure asyncpg driver** in connection string

#### Google Integration Errors
1. **Verify service account JSON** is valid single-line string
2. **Check folder/sheet permissions** for service account
3. **Validate Google API quotas** aren't exceeded

### Performance Optimization

#### For High-Traffic Instances

1. **Upgrade Render.com plan** for more resources
2. **Enable Redis caching**:
   ```env
   REDIS_URL=redis://your-redis-instance
   ```
3. **Optimize database queries** by adding indexes
4. **Implement request rate limiting**

#### Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
CREATE INDEX IF NOT EXISTS idx_creatives_created_at ON creatives(created_at);
CREATE INDEX IF NOT EXISTS idx_buyers_buyer_id ON buyers(buyer_id);
```

### Backup Strategy

#### Database Backup
Render.com PostgreSQL includes:
- **Daily backups** (retained for 7 days on free tier)
- **Point-in-time recovery**
- **Manual backup** via dashboard

#### Configuration Backup
- Keep `.env.example` updated with all required variables
- Store sensitive configs in secure password manager
- Document any custom configurations

### Security Considerations

#### Environment Variables Security
- ✅ Never commit `.env` files to git
- ✅ Use strong random `SECRET_KEY`
- ✅ Limit `ALLOWED_USERS` to necessary accounts only
- ✅ Rotate API tokens periodically

#### API Security
- ✅ Keitaro API token should have minimal required permissions
- ✅ Google service account should have minimal required access
- ✅ Monitor API usage for unusual patterns

#### Bot Security
- ✅ Implement proper user validation
- ✅ Log all user actions for audit trail
- ✅ Regular security updates of dependencies

## Maintenance

### Regular Tasks

1. **Monitor logs** for errors or performance issues
2. **Update dependencies** monthly:
   ```bash
   pip list --outdated
   pip install -U package_name
   ```
3. **Review user access** and remove inactive accounts
4. **Check API quotas** for Google services
5. **Monitor database storage** usage

### Updates and Deployments

1. **Test changes locally** before deployment
2. **Use feature branches** for development
3. **Deploy to staging** environment first (if available)
4. **Monitor logs** after production deployment
5. **Have rollback plan** ready

---

## 🎉 Congratulations!

Your Creative Keitaro Bot is now deployed and ready for production use. The bot provides:

- ✅ **Real-time analytics** from Keitaro
- ✅ **Advanced Dashboard** with traffic filtering
- ✅ **User management** with role-based access
- ✅ **File uploads** with Google Drive integration
- ✅ **Data exports** to Google Sheets
- ✅ **Production-ready** deployment on Render.com

For support or questions, refer to the logs and troubleshooting section above.