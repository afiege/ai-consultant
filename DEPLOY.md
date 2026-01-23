# Railway Deployment Guide

Deploy the AI Consultant app to Railway in minutes.

## Prerequisites

1. Create a [Railway account](https://railway.app)
2. Install Railway CLI: `npm install -g @railway/cli`
3. Login: `railway login`

## Quick Deploy

### Step 1: Deploy Backend

```bash
cd backend

# Create new Railway project
railway init

# Set environment variables
railway variables set LLM_MODEL=mistral/mistral-small-latest
railway variables set CORS_ORIGINS=https://your-frontend-url.railway.app

# Deploy
railway up
```

Note the backend URL (e.g., `https://ai-consultant-backend-production.up.railway.app`)

### Step 2: Deploy Frontend

```bash
cd frontend

# Create new Railway project (separate from backend)
railway init

# Set the backend URL as build argument
railway variables set VITE_API_URL=https://your-backend-url.railway.app

# Deploy
railway up
```

### Step 3: Update CORS

Go back to your backend project and update CORS:

```bash
cd backend
railway variables set CORS_ORIGINS=https://your-frontend-url.railway.app
railway up
```

## Environment Variables

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_MODEL` | No | LLM model (default: `mistral/mistral-small-latest`) |
| `LLM_API_BASE` | No | Custom API base URL for OpenAI-compatible endpoints |
| `CORS_ORIGINS` | Yes | Frontend URL(s), comma-separated |
| `DATABASE_URL` | No | SQLite path (default: `./database/ai_consultant.db`) |

**Note:** API keys are NOT stored on the server. Users enter their API key in the app at runtime.

### Frontend

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | Backend API URL |

## Monitoring

- View logs: `railway logs`
- Open dashboard: `railway open`

## Troubleshooting

### CORS Errors
Make sure `CORS_ORIGINS` includes your frontend URL (with `https://`).

### Database Issues
SQLite is ephemeral on Railway. For persistent data, consider:
1. Adding a Railway PostgreSQL plugin
2. Using Railway volumes (paid feature)

### Build Failures
Check logs with `railway logs` to see build errors.

## Alternative: Deploy via GitHub

1. Push your code to GitHub
2. Go to [Railway Dashboard](https://railway.app/dashboard)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repo and the folder (backend or frontend)
5. Set environment variables in the Railway dashboard
6. Railway will auto-deploy on every push

## Estimated Costs

Railway provides $5 free credit per month, which is typically enough for:
- Light usage (a few consultation sessions per day)
- Development and testing

For production use, expect ~$5-20/month depending on usage.
