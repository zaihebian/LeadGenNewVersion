# LeadGen - AI-Powered Lead Generation SaaS

A production-grade SaaS application for automated B2B lead generation and outreach.

## Features

- **AI-Powered Lead Search**: Convert natural language keywords into targeted lead searches
- **Apify Integration**: Collect leads via `code_crafter/leads-finder` actor
- **LinkedIn Enrichment**: Fetch recent posts for personalization via `apimaestro/linkedin-profile-posts`
- **Personalized Outreach**: AI-generated unique emails for each lead
- **Gmail Integration**: Send emails via connected Gmail account with OAuth2
- **Reply Monitoring**: Hourly inbox checks with sentiment classification
- **State Machine**: Strict lead lifecycle management with defined transitions
- **Rate Limiting**: Protect Gmail deliverability with configurable limits

## Architecture

```
LeadGen/
├── backend/           # FastAPI Python backend
│   ├── app/
│   │   ├── api/       # REST API routes
│   │   ├── models/    # SQLAlchemy models
│   │   ├── schemas/   # Pydantic schemas
│   │   ├── services/  # Business logic
│   │   └── jobs/      # Background tasks
│   └── requirements.txt
├── frontend/          # React + Vite frontend
│   └── src/
│       ├── pages/     # Page components
│       ├── components/# Reusable components
│       └── api/       # API client
└── docs/              # Documentation
```

## Lead State Machine

```
COLLECTED → ENRICHED → EMAILED_1 → WAITING
                                      ↓
                          ┌───────────┼───────────┐
                          ↓           ↓           ↓
                    INTERESTED  NOT_INTERESTED  EMAILED_2
                          ↓           ↓           ↓
                          └───────→ CLOSED ←──────┘
```

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Apify account with API token
- OpenAI API key
- Google Cloud project with Gmail API enabled

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy environment config
copy .env.example .env
# Edit .env with your API keys

# Run the server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Environment Variables

Create a `.env` file in the backend directory:

```env
# OpenAI API
OPENAI_API_KEY=sk-...

# Apify API
APIFY_API_TOKEN=apify_api_...

# Gmail OAuth2 (from Google Cloud Console)
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REDIRECT_URI=http://localhost:8000/api/auth/gmail/callback

# Database
DATABASE_URL=sqlite+aiosqlite:///./leadgen.db

# Security
SECRET_KEY=your-secret-key-change-in-production

# Testing/Cost Control
MAX_LEADS_PER_RUN=5

# Rate Limiting
MAX_EMAILS_PER_DAY=50
MIN_EMAIL_INTERVAL_SECONDS=120
```

## Usage

1. **Connect Gmail**: Click "Connect Gmail" on the Search page to authenticate
2. **Start a Search**: Enter keywords describing your ideal leads
3. **View Leads**: Monitor collected leads on the Leads page
4. **Send Emails**: Click "Send Email" to generate and send personalized outreach
5. **Monitor Inbox**: Check the Inbox for replies and respond to interested leads
6. **Track Metrics**: View performance on the Dashboard

## Rate Limiting Rules

| Rule | Limit |
|------|-------|
| Max leads per run (testing) | 5 |
| Max emails per lead | 2 |
| AI replies after interest | 0 (human takeover) |
| AI replies after refusal | 1 (polite follow-up) |
| Daily send limit | 50/day |
| Min interval between sends | 2 minutes |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search` | POST | Start new lead search |
| `/api/search/campaigns` | GET | List campaigns |
| `/api/leads` | GET | List leads with filters |
| `/api/leads/{id}/send-email` | POST | Send email to lead |
| `/api/inbox` | GET | List email threads |
| `/api/inbox/{id}/reply` | POST | Send manual reply |
| `/api/dashboard/stats` | GET | Get dashboard metrics |
| `/api/auth/gmail` | GET | Initiate Gmail OAuth |

## Background Jobs

- **Reply Monitor**: Runs every hour to check for new replies
- **Follow-up Sender**: Runs every 6 hours to send 14-day follow-ups

## License

Private - All rights reserved
