# Deployment Guide

This document covers three deployment targets:

1. **Docker Compose** (recommended) — simplest setup for local or production deployment
2. **Debian VPS / VM** — manual setup with systemd + Nginx
3. **Railway** — quick cloud deployment for testing

---

## Docker Compose Deployment (Recommended)

The quickest way to run the full stack. Requires Docker and Docker Compose.

### Prerequisites

| Requirement | Version |
|---|---|
| Docker | 20.10+ |
| Docker Compose | v2+ |

### 1. Configure Environment

```bash
cp .env.example .env
```

Edit `.env`:

```bash
# Required
CORS_ORIGINS=http://localhost:3001

# Optional — defaults shown
LLM_MODEL=mistral/mistral-small-latest
SESSION_SECRET_KEY=change-me-in-production
DATABASE_URL=sqlite:///./database/ai_consultant.db
```

### 2. Build & Start

```bash
docker compose up -d --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3001 |
| Backend API | http://localhost:8001 |
| API Docs | http://localhost:8001/docs |

### 3. Volumes

Three named volumes persist data across container restarts:

| Volume | Purpose |
|---|---|
| `backend-data` | SQLite database |
| `backend-uploads` | Uploaded files |
| `backend-exports` | Generated PDF reports |

### 4. Updating

```bash
git pull
docker compose up -d --build
```

### 5. Using PostgreSQL with Docker

Add a PostgreSQL service to `docker-compose.yml` and set:

```bash
DATABASE_URL=postgresql://user:password@db:5432/aiconsultant
```

---

## Debian VPS / VM Deployment

A single Debian-based server running the backend (Uvicorn) and frontend (Nginx-served static files). Suitable for a university or small-team deployment.

### Prerequisites

| Requirement | Version |
|---|---|
| Debian / Ubuntu server | 11+ / 22.04+ |
| Python | 3.11+ |
| Node.js | 18+ (only needed at build time) |
| Nginx | latest |
| Git | latest |

### 1. Server Preparation

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3 python3-venv python3-pip \
  nodejs npm nginx git ufw

# Open ports
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### 2. Clone and Build

```bash
# Clone repository
cd /opt
sudo git clone <REPO_URL> ai-consultant
sudo chown -R $USER:$USER /opt/ai-consultant

# ---- Backend ----
cd /opt/ai-consultant/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# ---- Frontend ----
cd /opt/ai-consultant/frontend
npm ci
# Point frontend at backend API — adjust domain/IP to your setup
VITE_API_URL=https://your-domain.example.com npm run build
```

### 3. Backend systemd Service

Create `/etc/systemd/system/ai-consultant.service`:

```ini
[Unit]
Description=AI Consultant Backend
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/ai-consultant/backend
Environment="LLM_MODEL=mistral/mistral-small-latest"
Environment="CORS_ORIGINS=https://your-domain.example.com"
Environment="SESSION_SECRET_KEY=change-me-to-a-random-secret"
ExecStart=/opt/ai-consultant/backend/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Give www-data ownership of runtime dirs
sudo chown -R www-data:www-data /opt/ai-consultant/backend/database \
  /opt/ai-consultant/backend/uploads /opt/ai-consultant/backend/exports

sudo systemctl daemon-reload
sudo systemctl enable --now ai-consultant
sudo systemctl status ai-consultant   # verify running
```

### 4. Nginx Reverse Proxy

Create `/etc/nginx/sites-available/ai-consultant`:

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    # Frontend — static files built by Vite
    root /opt/ai-consultant/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support — disable buffering
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }

    # WebSocket proxy
    location /api/sessions/ {
        proxy_pass http://127.0.0.1:8000/api/sessions/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ai-consultant /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

### 5. TLS with Let's Encrypt (recommended)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example.com
# Certbot auto-renews via systemd timer
```

### 6. Updating

```bash
cd /opt/ai-consultant
git pull

# Backend
cd backend
source .venv/bin/activate && pip install -r requirements.txt
alembic upgrade head   # apply database migrations
sudo systemctl restart ai-consultant

# Frontend
cd ../frontend
npm ci && VITE_API_URL=https://your-domain.example.com npm run build
# Nginx serves dist/ directly — no restart needed
```

### Optional: PostgreSQL

For larger deployments, swap SQLite for PostgreSQL:

```bash
sudo apt install -y postgresql
sudo -u postgres createuser aiconsultant
sudo -u postgres createdb aiconsultant -O aiconsultant

# Set DATABASE_URL in the systemd unit
#   Environment="DATABASE_URL=postgresql://aiconsultant:password@localhost/aiconsultant"
```

Update the backend env to use `DATABASE_URL` and install `psycopg2-binary` in the venv.

---

## Railway Deployment (Test / Staging)

Deploy the AI Consultant app to Railway in minutes.

### Prerequisites

1. Create a [Railway account](https://railway.app)
2. Install Railway CLI: `npm install -g @railway/cli`
3. Login: `railway login`

### Quick Deploy

#### Step 1: Deploy Backend

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

#### Step 2: Deploy Frontend

```bash
cd frontend

# Create new Railway project (separate from backend)
railway init

# Set the backend URL as build argument
railway variables set VITE_API_URL=https://your-backend-url.railway.app

# Deploy
railway up
```

#### Step 3: Update CORS

Go back to your backend project and update CORS:

```bash
cd backend
railway variables set CORS_ORIGINS=https://your-frontend-url.railway.app
railway up
```

### Alternative: Deploy via GitHub

1. Push your code to GitHub
2. Go to [Railway Dashboard](https://railway.app/dashboard)
3. Click "New Project" → "Deploy from GitHub repo"
4. Select your repo and the folder (backend or frontend)
5. Set environment variables in the Railway dashboard
6. Railway will auto-deploy on every push

### Estimated Costs

Railway provides $5 free credit per month, which is typically enough for light usage and testing. For production use expect ~$5-20/month.

---

## Environment Variables

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `LLM_MODEL` | No | LLM model (default: `mistral/mistral-small-latest`) |
| `LLM_API_BASE` | No | Custom API base URL for OpenAI-compatible endpoints |
| `CORS_ORIGINS` | Yes | Frontend URL(s), comma-separated |
| `DATABASE_URL` | No | Database URL — SQLite (default) or PostgreSQL |
| `SESSION_SECRET_KEY` | No | Secret for session token hashing (auto-generated if not set) |
| `ENABLE_TEST_MODE` | No | Enable test/demo endpoints (default: `false`) |

**Note:** API keys are NOT stored on the server. Users enter their API key in the app at runtime.

### Frontend

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | Backend API URL |

## Monitoring & Troubleshooting

### VPS

```bash
# Service logs
sudo journalctl -u ai-consultant -f

# Nginx access / error logs
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

### Railway

- View logs: `railway logs`
- Open dashboard: `railway open`

### Common Issues

| Symptom | Fix |
|---|---|
| CORS errors | Ensure `CORS_ORIGINS` includes the frontend origin with scheme (`https://…`) |
| WebSocket 502 | Confirm Nginx `proxy_http_version 1.1` and `Upgrade` headers in the `/api/sessions/` block |
| SQLite lock errors | Switch to PostgreSQL for concurrent multi-user use (see P7) |
| Build failures | Check `npm run build` output / `pip install -r requirements.txt` |
