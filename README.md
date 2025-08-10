# 🤖 Creative Keitaro Bot

> **Advanced Telegram Bot for Media Buying Analytics & Creative Management**

A professional-grade Telegram bot that integrates with Keitaro tracker to provide real-time analytics, advanced reporting, and creative asset management for media buying teams.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

## ✨ Key Features

### 📊 Advanced Analytics Dashboard
- **Real-time traffic data** from Keitaro tracker
- **Traffic source filtering** (Google, Facebook, etc.)
- **Comprehensive metrics**: clicks, conversions, revenue, ROI
- **Interactive reporting** with drill-down capabilities

### 👥 Team Management
- **Role-based access control** (Owner, Head, Teamlead, Buyer, etc.)
- **User registration system** with admin approval
- **Buyer-specific data filtering** and permissions

### 📈 Professional Reporting
- **Buyers Performance** - Individual buyer analytics
- **Creative Analysis** - Creative performance metrics  
- **Geo & Offers** - Geographic and offer performance
- **Export capabilities** to Google Sheets

### ☁️ Cloud Integration
- **Google Drive** - Automatic creative uploads
- **Google Sheets** - Data export and manifests
- **PostgreSQL** - Production-ready data storage

### 🔧 Production Ready
- **Docker containerization** for easy deployment
- **Render.com integration** with health checks
- **Automatic database migrations** 
- **Comprehensive logging** and error handling

## 🚀 Quick Start

### Option 1: Deploy to Render.com (Recommended)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

**One-click deployment with PostgreSQL database included**

1. Click the deploy button above
2. Connect your GitHub account
3. Configure environment variables (see [Environment Variables](#environment-variables))
4. Deploy automatically with database setup

### Option 2: Local Development

#### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Git

#### Setup
```bash
# Clone repository
git clone https://github.com/patriot-33/creative-keitaro-bot.git
cd creative-keitaro-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Setup database
createdb creative_bot
alembic upgrade head

# Run bot
python -m src.bot.main
```

## 📋 Environment Variables

### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | `1234567890:ABC...` |
| `DATABASE_URL` | PostgreSQL connection | `postgresql://user:pass@host/db` |
| `KEITARO_BASE_URL` | Keitaro tracker URL | `https://track.example.com` |
| `KEITARO_API_TOKEN` | Keitaro API token | `your_api_token_here` |
| `SECRET_KEY` | Application secret key | `random_secure_string` |
| `ALLOWED_USERS` | Initial admin users | `123456789:owner:` |

### Google Services (Optional)
| Variable | Description |
|----------|-------------|
| `GOOGLE_PROJECT_ID` | Google Cloud project ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Service account credentials |
| `GOOGLE_DRIVE_ROOT_FOLDER_ID` | Drive folder for uploads |
| `GOOGLE_SHEETS_MANIFEST_ID` | Spreadsheet for exports |

See [.env.example](.env.example) for complete configuration options.

## 🏗️ Architecture

### Core Components
- **Bot Framework**: aiogram 3.4+ for Telegram integration
- **Database**: PostgreSQL with SQLAlchemy ORM
- **API Client**: Async HTTP client for Keitaro integration
- **Services Layer**: Business logic separation
- **Background Tasks**: Scheduled reporting and maintenance

### Data Flow
```
Telegram Bot ←→ Services Layer ←→ Keitaro API
     ↓              ↓                    ↓
PostgreSQL   Google Drive        Google Sheets
```

### Security
- ✅ Role-based access control
- ✅ Input validation and sanitization  
- ✅ Secure environment variable handling
- ✅ API rate limiting and error handling
- ✅ Audit logging for user actions

## 📊 Dashboard Features

### Traffic Source Analysis
```
📊 Dashboard Summary (🔍 Google)
📅 Period: Yesterday

💰 Overall Metrics:
🖱 Unique Clicks: 2,724
👤 Registrations: 142  
💳 Deposits: 51
💰 Revenue: $5,630.00

📈 Performance Ratios:
🎯 CR: 7.09%
💎 reg2dep: 1:3 (35.9%)
💰 uEPC: $2.067
📊 ROI: 1966.8%
```

### Advanced Filtering
- **Traffic Sources**: Google, Facebook, Native, etc.
- **Time Periods**: Today, Yesterday, Last 7 days, Custom ranges
- **Buyer Filtering**: Individual or team performance
- **Geographic Analysis**: Country-wise breakdowns

## 🛠️ Development

### Project Structure
```
src/
├── bot/                 # Telegram bot logic
│   ├── handlers/       # Message handlers
│   ├── keyboards/      # Inline keyboards
│   ├── services/       # Business logic
│   └── main.py        # Bot entry point
├── core/               # Core configuration
├── db/                 # Database models & migrations
└── integrations/       # External API clients
    ├── keitaro/       # Keitaro API client
    └── google/        # Google APIs client
```

### Key Technologies
- **Backend**: Python 3.11, asyncio, aiohttp
- **Database**: PostgreSQL 13+, SQLAlchemy, Alembic
- **APIs**: Telegram Bot API, Keitaro API, Google APIs
- **Deployment**: Docker, Render.com, GitHub Actions

### Development Workflow
1. **Feature branches** - Create feature branches from `main`
2. **Local testing** - Test changes locally before deployment
3. **Code review** - Submit pull requests for review
4. **Automated deployment** - Deploy via Render.com integration

## 📚 API Documentation

### Keitaro Integration
The bot integrates with Keitaro tracker API for real-time analytics:

- **Traffic Sources** - `/admin_api/v1/report/build`
- **Conversions** - `/admin_api/v1/conversions/log` 
- **Buyers Data** - Custom aggregation logic
- **Time Filtering** - Accurate timezone handling (UTC ↔ Moscow)

### Database Schema
- `users` - User management and roles
- `creatives` - Creative asset tracking
- `buyers` - Buyer performance data
- `audit_logs` - System activity logs

## 🔧 Configuration

### User Roles
- **Owner** - Full system access
- **Head** - Team management and reporting
- **Teamlead** - Team reporting and user approval
- **Buyer** - Personal statistics and uploads
- **Bizdev** - Business development access
- **Finance** - Financial reporting access

### Traffic Source IDs
Default Keitaro traffic source mappings:
- `2` - Google (Google Ads, etc.)
- `11`, `16`, etc. - Facebook sources
- Custom sources via API discovery

## 📈 Monitoring & Analytics

### Health Checks
- **HTTP endpoint**: `/health` for Render.com monitoring
- **Database connectivity**: Automatic health verification
- **API status**: Keitaro API connection monitoring

### Logging
```python
# Structured logging with levels
INFO  - Normal operations
WARN  - Non-critical issues  
ERROR - API failures, database issues
DEBUG - Detailed debugging information
```

### Performance Metrics
- **Response times** - API call latencies
- **Error rates** - Failed requests tracking
- **User activity** - Command usage statistics
- **Resource usage** - Memory and CPU monitoring

## 🤝 Contributing

### Getting Started
1. **Fork** the repository
2. **Clone** your fork locally
3. **Create** a feature branch
4. **Make** your changes
5. **Test** thoroughly
6. **Submit** a pull request

### Code Standards
- **PEP 8** - Python code formatting
- **Type hints** - Full type annotation coverage
- **Docstrings** - Comprehensive function documentation
- **Error handling** - Proper exception handling
- **Security** - No hardcoded credentials

### Testing
```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src tests/

# Type checking
mypy src/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

### Documentation
- **[Deployment Guide](DEPLOYMENT.md)** - Complete deployment instructions
- **[Bug Reports](BUGFIXES.md)** - Known issues and solutions
- **[API Reference](docs/api.md)** - Technical API documentation

### Getting Help
- **Issues** - Report bugs via [GitHub Issues](https://github.com/patriot-33/creative-keitaro-bot/issues)
- **Discussions** - Ask questions in [GitHub Discussions](https://github.com/patriot-33/creative-keitaro-bot/discussions)
- **Email** - Contact support at your-email@example.com

---

<div align="center">

**⭐ Star this repo if you find it useful!**

Made with ❤️ for the media buying community

[Report Bug](https://github.com/patriot-33/creative-keitaro-bot/issues) · [Request Feature](https://github.com/patriot-33/creative-keitaro-bot/issues) · [Documentation](DEPLOYMENT.md)


</div>