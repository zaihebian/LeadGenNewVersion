# Deployment Guide: Railway (Backend) + Vercel (Frontend)

This guide provides step-by-step instructions for deploying the LeadGen application to Railway (backend) and Vercel (frontend).

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Backend Deployment (Railway)](#backend-deployment-railway)
3. [Frontend Deployment (Vercel)](#frontend-deployment-vercel)
4. [Environment Variables](#environment-variables)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Database Setup](#database-setup)
7. [Gmail OAuth Configuration](#gmail-oauth-configuration)
8. [Testing & Verification](#testing--verification)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before deploying, ensure you have:

- ✅ GitHub account with your code pushed to a repository
- ✅ Railway account ([railway.app](https://railway.app))
- ✅ Vercel account ([vercel.com](https://vercel.com))
- ✅ Google Cloud Console project with Gmail API enabled
- ✅ OpenAI API key
- ✅ Apify API token

---

## Backend Deployment (Railway)

### Step 1: Create Railway Account

1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub (recommended for easy repo access)
3. Complete account setup

### Step 2: Create New Project

1. Click **"New Project"** in Railway dashboard
2. Select **"Deploy from GitHub repo"**
3. Choose your repository
4. Railway will create a new project

### Step 3: Configure Service

1. Railway will auto-detect it's a Python project
2. **Set Root Directory**: Click on the service → Settings → Root Directory → Set to `backend`
3. **Set Start Command**: In Settings → Deploy → Start Command:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
4. **Set Python Version**: Railway uses `runtime.txt` (Python 3.11) automatically

### Step 4: Add Environment Variables

In Railway project → Variables tab, add all required environment variables:

#### Required Variables

```bash
# OpenAI API
OPENAI_API_KEY=sk-your-openai-key-here

# Apify API
APIFY_API_TOKEN=apify_api_your-token-here

# Gmail OAuth2 (get from Google Cloud Console)
GMAIL_CLIENT_ID=your-client-id.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=your-client-secret
GMAIL_REDIRECT_URI=https://your-app.railway.app/api/auth/gmail/callback

# Database (SQLite for development, PostgreSQL for production - see Database Setup)
DATABASE_URL=sqlite+aiosqlite:///./leadgen.db

# Security
SECRET_KEY=generate-a-random-secret-key-here-min-32-characters

# Testing/Cost Control
MAX_LEADS_PER_RUN=5

# Rate Limiting
MAX_EMAILS_PER_DAY=50
MIN_EMAIL_INTERVAL_SECONDS=120

# Reply Monitoring
NO_REPLY_FOLLOWUP_DAYS=14

# Frontend URL (for CORS - update after deploying frontend)
FRONTEND_URL=https://your-frontend.vercel.app

# Mock Mode (set to false for production)
USE_MOCK_LEADS=false
```

**Important Notes:**
- Replace `your-app.railway.app` with your actual Railway domain (you'll get this after first deploy)
- Generate a secure `SECRET_KEY` (use: `openssl rand -hex 32` or similar)
- `GMAIL_REDIRECT_URI` must match exactly what you configure in Google Cloud Console

### Step 5: Deploy

1. Railway will automatically detect changes and deploy
2. First deployment may take 3-5 minutes
3. Once deployed, Railway will provide a URL like: `https://your-app-name.railway.app`
4. **Save this URL** - you'll need it for frontend configuration

### Step 6: Verify Backend Deployment

1. Visit `https://your-app-name.railway.app/` in browser
2. You should see: `{"status":"ok","service":"LeadGen API"}`
3. Check Railway logs for any errors

---

## Frontend Deployment (Vercel)

### Step 1: Create Vercel Account

1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub (recommended)
3. Complete account setup

### Step 2: Import Project

1. Click **"Add New..."** → **"Project"**
2. Import your GitHub repository
3. Select the repository containing your code

### Step 3: Configure Project Settings

**Framework Preset:** Vite (auto-detected)

**Root Directory:** `frontend`

**Build Settings:**
- **Build Command:** `npm run build`
- **Output Directory:** `dist`
- **Install Command:** `npm install` (default)

**Note:** Vercel will auto-detect Vite settings from `vite.config.ts` and `vercel.json`

### Step 4: Add Environment Variables

In Vercel project → Settings → Environment Variables, add:

```bash
# Backend API URL (update with your Railway URL)
VITE_API_URL=https://your-app-name.railway.app
```

**Important:** 
- Replace `your-app-name.railway.app` with your actual Railway backend URL
- This must be set **before** deploying
- You can update it later if needed

### Step 5: Deploy

1. Click **"Deploy"**
2. Vercel will build and deploy your frontend
3. First deployment takes 1-2 minutes
4. Vercel will provide a URL like: `https://your-project.vercel.app`
5. **Save this URL** - you'll need it for backend CORS configuration

---

## Environment Variables

### Complete Environment Variable Reference

#### Backend (Railway)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key | `sk-...` |
| `APIFY_API_TOKEN` | ✅ | Apify API token | `apify_api_...` |
| `GMAIL_CLIENT_ID` | ✅ | Google OAuth client ID | `xxx.apps.googleusercontent.com` |
| `GMAIL_CLIENT_SECRET` | ✅ | Google OAuth client secret | `xxx` |
| `GMAIL_REDIRECT_URI` | ✅ | OAuth callback URL | `https://your-app.railway.app/api/auth/gmail/callback` |
| `DATABASE_URL` | ✅ | Database connection string | See [Database Setup](#database-setup) |
| `SECRET_KEY` | ✅ | Secret key for sessions | Generate random 32+ char string |
| `MAX_LEADS_PER_RUN` | ⚠️ | Max leads per search (testing) | `5` |
| `MAX_EMAILS_PER_DAY` | ⚠️ | Daily email limit | `50` |
| `MIN_EMAIL_INTERVAL_SECONDS` | ⚠️ | Min seconds between emails | `120` |
| `NO_REPLY_FOLLOWUP_DAYS` | ⚠️ | Days before follow-up | `14` |
| `FRONTEND_URL` | ⚠️ | Frontend URL for CORS | `https://your-project.vercel.app` |
| `USE_MOCK_LEADS` | ⚠️ | Use mock data (testing) | `false` |

#### Frontend (Vercel)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `VITE_API_URL` | ✅ | Backend API URL | `https://your-app.railway.app` |

---

## Post-Deployment Configuration

### Step 1: Update Backend CORS

After deploying frontend, update backend CORS settings:

1. In Railway → Your Project → Variables
2. Add/Update `FRONTEND_URL` variable:
   ```
   FRONTEND_URL=https://your-project.vercel.app
   ```

3. The backend code already handles this in `app/main.py`:
   ```python
   if hasattr(settings, 'frontend_url') and settings.frontend_url:
       cors_origins.append(settings.frontend_url)
   ```

4. **Redeploy backend** (Railway auto-redeploys when env vars change)

### Step 2: Update Gmail OAuth Redirect URI

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **APIs & Services** → **Credentials**
3. Click on your OAuth 2.0 Client ID
4. Add authorized redirect URI:
   ```
   https://your-app-name.railway.app/api/auth/gmail/callback
   ```
5. **Save** changes

### Step 3: Update Frontend API URL (if needed)

If you need to change the backend URL:

1. In Vercel → Your Project → Settings → Environment Variables
2. Update `VITE_API_URL` with new backend URL
3. **Redeploy** (Vercel will auto-redeploy or click "Redeploy")

---

## Database Setup

### Option 1: SQLite (Development/Testing)

**Pros:** Simple, no setup required  
**Cons:** Not suitable for production, data lost on redeploy

**Configuration:**
```bash
DATABASE_URL=sqlite+aiosqlite:///./leadgen.db
```

**Note:** Railway's filesystem is ephemeral - data will be lost on redeploy. Use PostgreSQL for production.

### Option 2: PostgreSQL (Production - Recommended)

**Pros:** Persistent, scalable, production-ready  
**Cons:** Requires setup

#### Setup PostgreSQL on Railway

1. In Railway project → **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Railway will create a PostgreSQL database
3. Railway automatically provides `DATABASE_URL` environment variable
4. **Update your service** to use the PostgreSQL `DATABASE_URL`

#### Update Backend for PostgreSQL

1. Railway automatically sets `DATABASE_URL` with PostgreSQL connection string
2. Update `requirements.txt` to include PostgreSQL driver:
   ```
   asyncpg>=0.29.0
   ```
3. Update `backend/app/database.py` to use PostgreSQL:
   ```python
   # Change from:
   # sqlite+aiosqlite:///...
   # To:
   # postgresql+asyncpg://...
   ```

**Railway automatically handles this** - just use the provided `DATABASE_URL` variable.

---

## Gmail OAuth Configuration

### Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable **Gmail API**:
   - Navigate to **APIs & Services** → **Library**
   - Search for "Gmail API"
   - Click **Enable**

### Step 2: Create OAuth 2.0 Credentials

1. Navigate to **APIs & Services** → **Credentials**
2. Click **"+ CREATE CREDENTIALS"** → **"OAuth client ID"**
3. If prompted, configure OAuth consent screen:
   - User Type: **External** (unless you have Google Workspace)
   - App name: Your app name
   - User support email: Your email
   - Developer contact: Your email
   - Add scopes: `https://www.googleapis.com/auth/gmail.send`, `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.modify`
4. Create OAuth client ID:
   - Application type: **Web application**
   - Name: LeadGen App
   - Authorized redirect URIs:
     - `http://localhost:8000/api/auth/gmail/callback` (for local dev)
     - `https://your-app-name.railway.app/api/auth/gmail/callback` (for production)

### Step 3: Get Credentials

1. Copy **Client ID** → Use as `GMAIL_CLIENT_ID`
2. Copy **Client Secret** → Use as `GMAIL_CLIENT_SECRET`
3. Add to Railway environment variables

---

## Testing & Verification

### Backend Health Check

1. Visit `https://your-app-name.railway.app/`
2. Should return: `{"status":"ok","service":"LeadGen API"}`
3. Visit `https://your-app-name.railway.app/api/debug/health`
4. Should show service configuration status

### Frontend Connection Test

1. Visit your Vercel frontend URL
2. Open browser DevTools → Console
3. Check for any API connection errors
4. Try navigating to different pages

### End-to-End Test

1. **Connect Gmail:**
   - Go to Search page
   - Click "Connect Gmail"
   - Complete OAuth flow
   - Should redirect back to app

2. **Test Lead Search:**
   - Enter keywords
   - Start search
   - Check backend logs in Railway
   - Verify leads appear in Leads page

3. **Test Email Sending:**
   - Wait for emails to be sent (3-minute interval)
   - Check Gmail inbox
   - Verify emails were sent

---

## Troubleshooting

### Backend Issues

#### Backend Not Starting

**Symptoms:** 502/503 errors, no response

**Solutions:**
1. Check Railway logs: Project → Deployments → View logs
2. Verify start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. Check Python version matches `runtime.txt` (3.11)
4. Verify all required environment variables are set
5. Check for import errors in logs

#### Database Connection Errors

**Symptoms:** Database errors in logs

**Solutions:**
1. Verify `DATABASE_URL` is set correctly
2. For PostgreSQL: Check Railway database is running
3. For SQLite: Ensure path is writable
4. Check database initialization in logs

#### CORS Errors

**Symptoms:** Frontend can't connect to backend, CORS errors in console

**Solutions:**
1. Verify `FRONTEND_URL` is set in Railway with your Vercel URL
2. Check backend logs for CORS errors
3. Verify frontend `VITE_API_URL` matches backend URL exactly
4. Ensure backend URL doesn't have trailing slash

### Frontend Issues

#### 404 Errors on Routes

**Symptoms:** Page refreshes show 404

**Solutions:**
1. Verify `vercel.json` exists in `frontend/` directory
2. Check `rewrites` configuration in `vercel.json`
3. Ensure root directory is set to `frontend` in Vercel

#### API Connection Failed

**Symptoms:** Frontend can't reach backend

**Solutions:**
1. Verify `VITE_API_URL` is set in Vercel environment variables
2. Check backend is running and accessible
3. Test backend URL directly in browser
4. Check browser console for exact error
5. Verify CORS configuration

#### Build Failures

**Symptoms:** Vercel build fails

**Solutions:**
1. Check build logs in Vercel dashboard
2. Verify `package.json` has correct scripts
3. Check for TypeScript errors
4. Verify all dependencies are in `package.json`

### Gmail OAuth Issues

#### OAuth Redirect Mismatch

**Symptoms:** "Redirect URI mismatch" error

**Solutions:**
1. Verify redirect URI in Google Cloud Console matches exactly:
   - `https://your-app-name.railway.app/api/auth/gmail/callback`
2. Check Railway URL is correct (no trailing slash)
3. Ensure `GMAIL_REDIRECT_URI` in Railway matches Google Console

#### OAuth Not Working

**Symptoms:** Can't connect Gmail

**Solutions:**
1. Verify Gmail API is enabled in Google Cloud Console
2. Check OAuth consent screen is configured
3. Verify scopes are added to consent screen
4. Check Railway logs for OAuth errors
5. Ensure `GMAIL_CLIENT_ID` and `GMAIL_CLIENT_SECRET` are correct

### General Issues

#### Environment Variables Not Working

**Solutions:**
1. Verify variables are set in correct project (Railway vs Vercel)
2. Check variable names match exactly (case-sensitive)
3. Redeploy after adding/changing variables
4. For Vercel: Variables must start with `VITE_` to be exposed to frontend

#### Scheduled Jobs Not Running

**Symptoms:** Emails not sending, replies not checking

**Solutions:**
1. Check Railway logs for scheduler startup messages
2. Verify backend is running continuously (not sleeping)
3. Check for errors in job logs
4. Railway free tier may sleep after inactivity - upgrade to keep running

---

## Railway-Specific Notes

### Free Tier Limitations

- **Sleeping:** Free tier services sleep after 30 minutes of inactivity
- **Solution:** Upgrade to paid plan or use Railway's "Always On" feature
- **Impact:** Scheduled jobs won't run if service is sleeping

### Persistent Storage

- Railway's filesystem is **ephemeral**
- SQLite database files will be lost on redeploy
- **Use PostgreSQL** for production (Railway provides managed PostgreSQL)

### Custom Domain

1. Railway → Project → Settings → Domains
2. Add custom domain
3. Update `GMAIL_REDIRECT_URI` with new domain
4. Update Google Cloud Console redirect URI

### Monitoring

- Railway provides logs in real-time
- Check logs: Project → Deployments → View logs
- Set up alerts for errors (Railway Pro feature)

---

## Vercel-Specific Notes

### Automatic Deployments

- Vercel auto-deploys on every push to main branch
- Preview deployments for pull requests
- Can disable auto-deploy in settings

### Environment Variables

- Variables can be set per environment (Production, Preview, Development)
- Use Production environment for live site
- Variables starting with `VITE_` are exposed to frontend code

### Custom Domain

1. Vercel → Project → Settings → Domains
2. Add custom domain
3. Follow DNS configuration instructions
4. Update `FRONTEND_URL` in Railway with new domain

### Build Optimization

- Vercel automatically optimizes Vite builds
- Uses edge network for fast global delivery
- No additional configuration needed

---

## Security Checklist

Before going to production:

- [ ] Generate strong `SECRET_KEY` (32+ random characters)
- [ ] Use PostgreSQL instead of SQLite
- [ ] Set `USE_MOCK_LEADS=false`
- [ ] Configure proper `MAX_EMAILS_PER_DAY` limit
- [ ] Set `FRONTEND_URL` in backend for CORS
- [ ] Verify Gmail OAuth redirect URI matches exactly
- [ ] Review all environment variables
- [ ] Enable Railway/Vercel monitoring/alerts
- [ ] Test OAuth flow end-to-end
- [ ] Verify scheduled jobs are running

---

## Cost Estimation

### Railway

- **Free Tier:** $5 credit/month
- **Hobby Plan:** $5/month (always-on, no sleeping)
- **Pro Plan:** $20/month (better performance, more resources)

**Estimated cost:** $5-20/month for backend

### Vercel

- **Free Tier:** Unlimited deployments, 100GB bandwidth
- **Pro Plan:** $20/month (more bandwidth, team features)

**Estimated cost:** $0-20/month for frontend

**Total:** ~$5-40/month depending on usage

---

## Quick Reference

### Railway Backend URL
```
https://your-app-name.railway.app
```

### Vercel Frontend URL
```
https://your-project.vercel.app
```

### Key Environment Variables

**Railway:**
- `DATABASE_URL` (auto-set if using Railway PostgreSQL)
- `GMAIL_REDIRECT_URI=https://your-app-name.railway.app/api/auth/gmail/callback`
- `FRONTEND_URL=https://your-project.vercel.app`

**Vercel:**
- `VITE_API_URL=https://your-app-name.railway.app`

### Important URLs

- Railway Dashboard: https://railway.app
- Vercel Dashboard: https://vercel.com
- Google Cloud Console: https://console.cloud.google.com
- Railway Logs: Project → Deployments → View logs
- Vercel Logs: Project → Deployments → View build logs

---

## Support

If you encounter issues:

1. Check Railway logs for backend errors
2. Check Vercel build logs for frontend errors
3. Verify all environment variables are set correctly
4. Test backend URL directly in browser
5. Check browser console for frontend errors
6. Review this troubleshooting section

For Railway-specific help: https://docs.railway.app  
For Vercel-specific help: https://vercel.com/docs
