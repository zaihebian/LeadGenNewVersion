# Deployment Guide

## Architecture

This project consists of:
- **Frontend**: React + Vite (deploy to Vercel)
- **Backend**: FastAPI (deploy to Railway, Render, or Fly.io)

## Frontend Deployment (Vercel)

### Step 1: Deploy Frontend

1. **Push your code to GitHub** (if not already done)
   ```bash
   git add .
   git commit -m "Prepare for deployment"
   git push origin main
   ```

2. **Connect to Vercel**
   - Go to [vercel.com](https://vercel.com)
   - Click "New Project"
   - Import your GitHub repository
   - **Important**: Set the root directory to `frontend`
   - Framework Preset: Vite
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Install Command: `npm install`

3. **Add Environment Variable**
   - In Vercel project settings → Environment Variables
   - Add: `VITE_API_URL` = `https://your-backend-url.com`
   - (You'll set this after deploying the backend)

4. **Deploy**
   - Click "Deploy"
   - Vercel will build and deploy your frontend

### Step 2: Update API URL

After deploying the backend (see below), update the `VITE_API_URL` environment variable in Vercel with your backend URL.

## Backend Deployment Options

### Option 1: Railway (Recommended - Easiest)

1. **Sign up** at [railway.app](https://railway.app)
2. **New Project** → Deploy from GitHub
3. **Select your repo** and set root directory to `backend`
4. **Add Environment Variables**:
   ```
   OPENAI_API_KEY=your-key
   APIFY_API_TOKEN=your-token
   GMAIL_CLIENT_ID=your-id
   GMAIL_CLIENT_SECRET=your-secret
   GMAIL_REDIRECT_URI=https://your-backend.railway.app/api/auth/gmail/callback
   DATABASE_URL=sqlite+aiosqlite:///./leadgen.db
   SECRET_KEY=your-secret-key
   MAX_LEADS_PER_RUN=5
   MAX_EMAILS_PER_DAY=50
   MIN_EMAIL_INTERVAL_SECONDS=120
   ```
5. **Railway will auto-detect Python** and install dependencies
6. **Set Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
7. **Deploy** - Railway will give you a URL like `https://your-app.railway.app`

### Option 2: Render

1. **Sign up** at [render.com](https://render.com)
2. **New Web Service** → Connect GitHub
3. **Settings**:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Add Environment Variables** (same as Railway)
5. **Deploy**

### Option 3: Fly.io

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`
2. **In backend directory**:
   ```bash
   fly launch
   ```
3. **Follow prompts** and add environment variables
4. **Deploy**: `fly deploy`

## Post-Deployment

### 1. Update CORS in Backend

Update `backend/app/main.py` to allow your Vercel domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://your-frontend.vercel.app",  # Add your Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Update Gmail OAuth Redirect URI

In Google Cloud Console, update the authorized redirect URI to:
```
https://your-backend-url.com/api/auth/gmail/callback
```

### 3. Update Frontend Environment Variable

In Vercel, set `VITE_API_URL` to your backend URL:
```
VITE_API_URL=https://your-backend.railway.app
```

## Database Considerations

**Note**: SQLite works for development, but for production consider:
- **PostgreSQL** (Railway, Render offer managed PostgreSQL)
- Update `DATABASE_URL` to PostgreSQL connection string
- Update `requirements.txt` to use `asyncpg` instead of `aiosqlite`

## Testing

1. Visit your Vercel frontend URL
2. Check browser console for API connection errors
3. Test a search to verify backend connection
4. Check backend logs for any errors

## Troubleshooting

### 404 on Vercel
- Make sure root directory is set to `frontend`
- Check that `vercel.json` is in the frontend directory

### CORS Errors
- Update CORS origins in backend to include your Vercel domain
- Check that backend URL is correct in frontend environment variable

### API Connection Failed
- Verify `VITE_API_URL` is set correctly in Vercel
- Check backend is running and accessible
- Verify CORS settings
