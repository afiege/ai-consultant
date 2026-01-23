# AI & Digitalization Consultant for SMEs

An AI-powered digitalization consultant application for Small and Medium Enterprises (SMEs) that guides companies through a comprehensive 5-step consultation process using LLMs via LiteLLM (supporting OpenAI, Anthropic, Mistral, OpenRouter, and more).

## Features

### 5-Step Consultation Process

1. **Company Overview Collection** (Step 1)
   - Free text input for company information
   - File uploads (PDF, DOCX) with automatic text extraction
   - Web crawling to gather information from company websites

2. **Interactive 6-3-5 Brainstorming** (Step 2)
   - Real-time collaborative ideation with up to 6 participants
   - AI participant that contributes ideas alongside humans
   - Each participant contributes 3 ideas per round
   - 5-minute rounds with automatic sheet rotation
   - QR code sharing for easy session joining

3. **Idea Prioritization** (Step 3)
   - Vote and score generated ideas
   - Collaborative ranking system
   - Identify top ideas for implementation

4. **CRISP-DM Business Understanding** (Step 4)
   - AI-guided consultation using CRISP-DM methodology
   - Streaming chat responses (Server-Sent Events)
   - Extracts 4 key findings:
     - Business Objectives
     - Situation Assessment
     - AI/Data Mining Goals
     - Project Plan

5. **Business Case Calculation** (Step 5)
   - 5-Level Value Framework analysis
   - AI-assisted ROI estimation
   - Produces:
     - Classification (which value level)
     - Back-of-the-envelope Calculation
     - Validation Questions
     - Management Pitch

6. **Professional PDF Export**
   - Comprehensive report generation
   - Includes all consultation data from all 5 steps
   - Professional formatting with executive summary

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React + Vite)                          │
│                                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Step1    │ │ Step2    │ │ Step3    │ │ Step4    │ │ Step5    │         │
│  │ Company  │ │ 6-3-5    │ │ Prioriti-│ │ CRISP-DM │ │ Business │         │
│  │ Profile  │ │ Method   │ │ zation   │ │ Consult  │ │ Case     │         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘         │
│       │            │            │            │            │                │
│       │      ┌─────┴────────────┴────────────┴────────────┘                │
│       │      │  ApiKeyPrompt (modal) - prompts for LLM API key             │
│       │      └─────┬─────────────────────────────────────────              │
│  ┌────┴────────────┴──────────────────────────────────────────┐            │
│  │                    services/api.js                          │            │
│  │  apiKeyManager (sessionStorage) + API client functions      │            │
│  └─────────────────────────────┬──────────────────────────────┘            │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │ HTTP/REST + SSE
                                 │ (API key in request body)
┌────────────────────────────────┼────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                   │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────────┐         │
│  │                         Routers                                │         │
│  │  sessions │ six_three_five │ consultation │ business_case     │         │
│  │  prioritization │ expert_settings │ company_info              │         │
│  └─────────────────────────────┬─────────────────────────────────┘         │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────────┐         │
│  │                         Services                               │         │
│  │  llm_service.py ──► LiteLLM ──► OpenAI/Anthropic/Mistral/etc  │         │
│  │  six_three_five_service │ consultation_service                 │         │
│  │  business_case_service │ pdf_generator │ web_crawler           │         │
│  └─────────────────────────────┬─────────────────────────────────┘         │
│                                │                                            │
│  ┌─────────────────────────────┴─────────────────────────────────┐         │
│  │                    Models (SQLAlchemy)                         │         │
│  │  Session │ CompanyInfo │ Participant │ IdeaSheet │ Idea       │         │
│  │  Prioritization │ ConsultationMessage │ ConsultationFinding   │         │
│  └───────────────────────────────────────────────────────────────┘         │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐      ┌──────────────────┐      ┌──────────────────┐
│    SQLite     │      │  LLM Providers   │      │  File Storage    │
│  sessions.db  │      │  (via LiteLLM)   │      │  uploads/        │
│               │      │  - OpenAI        │      │  exports/        │
│               │      │  - Anthropic     │      │                  │
│               │      │  - Mistral       │      │                  │
│               │      │  - OpenRouter    │      │                  │
└───────────────┘      └──────────────────┘      └──────────────────┘
```

### Key Design Decisions

- **No server-side API key storage**: User API keys are stored only in browser `sessionStorage` (cleared when tab closes) and passed with each LLM request
- **LiteLLM abstraction**: Supports 100+ LLM providers through a unified interface
- **SSE streaming**: Chat responses stream in real-time for better UX
- **SQLite database**: Simple file-based storage, easy backup/restore
- **Modular architecture**: Each step has dedicated router and service layer

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **SQLite** - Database with WAL mode for better concurrency
- **LiteLLM** - Multi-provider LLM integration (OpenAI, Anthropic, Mistral, OpenRouter, etc.)
- **WeasyPrint** - PDF generation
- **BeautifulSoup4** - Web scraping
- **PyPDF2 & python-docx** - File processing

### Frontend
- **React 18** - UI framework
- **React Router** - Navigation
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **i18next** - Internationalization (English & German)
- **React Markdown** - Markdown rendering in chat
- **QRCode.react** - QR code generation for session sharing

## Project Structure

```
ai-consultant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── config.py            # Configuration (env vars)
│   │   ├── database.py          # Database setup
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── session.py       # Session, CompanyInfo
│   │   │   ├── brainstorm.py    # Participant, IdeaSheet, Idea
│   │   │   ├── prioritization.py
│   │   │   └── consultation.py  # Messages, Findings
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API endpoint handlers
│   │   │   ├── sessions.py
│   │   │   ├── company_info.py
│   │   │   ├── six_three_five.py
│   │   │   ├── prioritization.py
│   │   │   ├── consultation.py
│   │   │   ├── business_case.py
│   │   │   └── expert_settings.py
│   │   └── services/            # Business logic
│   │       ├── llm_service.py   # LiteLLM integration
│   │       ├── six_three_five_service.py
│   │       ├── consultation_service.py
│   │       ├── business_case_service.py
│   │       ├── pdf_generator.py
│   │       ├── web_crawler.py
│   │       └── default_prompts.py
│   ├── uploads/                 # Uploaded files
│   ├── exports/                 # Generated PDF reports
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app with routing
│   │   ├── main.jsx             # Entry point
│   │   ├── pages/               # Page components
│   │   │   ├── HomePage.jsx
│   │   │   ├── Step1Page.jsx
│   │   │   ├── Step2Page.jsx
│   │   │   ├── Step3Page.jsx
│   │   │   ├── Step4Page.jsx
│   │   │   ├── Step5Page.jsx
│   │   │   └── ExportPage.jsx
│   │   ├── components/          # Reusable components
│   │   │   ├── common/          # Shared UI components
│   │   │   │   ├── ApiKeyPrompt.jsx
│   │   │   │   ├── PageHeader.jsx
│   │   │   │   └── ExplanationBox.jsx
│   │   │   ├── step1/
│   │   │   ├── step2/
│   │   │   └── step3/
│   │   ├── services/
│   │   │   └── api.js           # API client + apiKeyManager
│   │   └── i18n/
│   │       └── locales/         # en.json, de.json
│   ├── package.json
│   └── vite.config.js
│
└── README.md
```

## Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- npm or yarn

### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv

   # On macOS/Linux:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and configure:
   - `LLM_MODEL` - Default model (e.g., `mistral/mistral-small-latest`, `gpt-4o`, `claude-3-sonnet`)
   - `LLM_API_BASE` - Custom API base URL (optional, for local models or proxies)

   **Note**: API keys are entered by users in the app at runtime and are NOT stored on the server.

5. **Run the backend**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   The backend will be available at `http://localhost:8000`
   API documentation at `http://localhost:8000/docs`

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   The defaults should work for local development:
   ```
   VITE_API_URL=http://localhost:8000
   ```

4. **Run the development server**
   ```bash
   npm run dev
   ```

   The frontend will be available at `http://localhost:5173`

## Usage

1. **Start a new consultation**
   - Open `http://localhost:5173` in your browser
   - Click "Start New Consultation"

2. **Step 1: Company Overview**
   - Enter company information via text, upload files, or provide a website URL
   - Submit information to proceed

3. **Step 2: 6-3-5 Brainstorming**
   - Share the session link or QR code with participants
   - Each participant enters their name to join
   - Enter your API key when prompted (for AI participant)
   - Start the brainstorming session
   - Write 3 ideas during each 5-minute round
   - Sheets rotate to the next participant after each round

4. **Step 3: Prioritization**
   - Review all generated ideas
   - Allocate points to your favorite ideas
   - See ranked results based on collective votes

5. **Step 4: CRISP-DM Consultation**
   - Enter your API key for the LLM provider (if not already set)
   - Engage in an AI-guided interview following CRISP-DM methodology
   - The AI extracts key findings into structured categories
   - Click "Generate Summary" to extract findings

6. **Step 5: Business Case**
   - Continue the conversation to develop a business case
   - The AI uses the 5-level value framework:
     1. Budget Substitution
     2. Process Efficiency
     3. Project Acceleration
     4. Risk Mitigation
     5. Strategic Scaling
   - Extract findings for classification, calculation, validation questions, and management pitch

7. **Export**
   - Generate a comprehensive PDF report
   - Download the report containing all consultation data

## API Key Handling

This application uses a **pass-per-request** approach for API keys:

1. When an LLM operation is triggered, the app checks if an API key exists in `sessionStorage`
2. If not, a modal prompts the user to enter their API key
3. The key is stored in `sessionStorage` (browser tab only, cleared on close)
4. Each API request includes the key in the request body
5. The server never stores API keys - they're used only in-memory for the LLM call

**Supported providers** (via LiteLLM):
- OpenAI (GPT-4, GPT-3.5, etc.)
- Anthropic (Claude)
- Mistral AI
- OpenRouter (100+ models)
- Any OpenAI-compatible endpoint

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Database Schema

The application uses these main tables:
- `sessions` - Consultation sessions with settings
- `company_info` - Company data from Step 1
- `participants` - 6-3-5 session participants
- `idea_sheets` - Idea sheets that rotate between participants
- `ideas` - Individual ideas (3 per round per sheet)
- `prioritizations` - Votes and point allocations
- `consultation_messages` - Chat messages (CRISP-DM and Business Case)
- `consultation_findings` - Extracted findings from consultations
- `expert_settings` - Per-session LLM configuration

## Security Features

- **No API Key Storage**: API keys are entered by users at runtime, stored only in browser sessionStorage, and passed with each request - never persisted on the server
- **Input Validation**: All user inputs validated via Pydantic schemas
- **File Upload Security**: File type restrictions, size limits, UUID-based filenames
- **CORS Protection**: Configured allowed origins
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

## Internationalization

The application supports:
- **English** (default)
- **German**

Language can be switched via the UI. Translations are in `frontend/src/i18n/locales/`.

## Development

### Running Tests

Backend:
```bash
cd backend
pytest
```

### Building for Production

Frontend:
```bash
cd frontend
npm run build
```

The built files will be in `frontend/dist/`

## Deployment

See [DEPLOY.md](DEPLOY.md) for deployment instructions including:
- Railway deployment
- Docker deployment
- Manual VPS deployment

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Contact

For questions or support, please open an issue on GitHub.
