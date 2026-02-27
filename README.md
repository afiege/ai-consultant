# AI & Digitalization Consultant for SMEs

An AI-powered digitalization consultant application for Small and Medium Enterprises (SMEs) that guides companies through a comprehensive 6-step consultation process using LLMs via LiteLLM (supporting OpenAI, Anthropic, Mistral, OpenRouter, and more).

## Customer Journey

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         STEP 1                                                    │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                                      │
│  │   STEP 1a    │     │   STEP 1b    │     │   STEP 1c    │                                      │
│  │   Company    │────▶│   Company    │────▶│   Digital    │                                      │
│  │ Information  │     │   Profile    │     │  Maturity    │                                      │
│  │   Input      │     │  Extraction  │     │ Assessment   │                                      │
│  └──────────────┘     └──────────────┘     └──────────────┘                                      │
│   Text, Files,          AI extracts          acatech I4.0                                        │
│   Web Crawling         structured data       Maturity Index                                      │
└──────────────────────────────────────────────────┬───────────────────────────────────────────────┘
                                                   │
┌──────────────────────────────────────────────────┘
│
│    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    │   STEP 2     │     │   STEP 3     │     │   STEP 4     │     │   STEP 5     │
└───▶│    6-3-5     │────▶│    Idea      │────▶│     AI       │────▶│  Business    │
     │ Brainstorming│     │Prioritization│     │ Consultation │     │    Case      │
     └──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
      Collaborative        Vote & rank          CRISP-DM            5-Level Value
      ideation with        generated            methodology         Framework &
      AI participants      ideas                                    Cost Estimation
                                                       │
┌──────────────────────────────────────────────────────┘
│
│    ┌──────────────┐
│    │   STEP 6     │
└───▶│   Export &   │────▶ Professional PDF Report with SWOT Analysis & Technical Briefing
     │   Handover   │
     └──────────────┘
```

## Features

### 6-Step Consultation Process

1. **Company Information** (Step 1a)
   - **Free text input**: Describe your company, challenges, and goals in your own words
   - **File uploads**: Upload PDF or DOCX documents (annual reports, presentations, org charts)
   - **Web crawling**: Automatically extract content from company website by entering URL
   - All sources are combined to build comprehensive company context

2. **Company Profile Extraction** (Step 1b)
   - **AI-powered extraction**: Automatically analyzes all company data to extract structured information
   - **25+ business attributes** organized in categories:
     - Basic info (name, industry, founding year, ownership type)
     - Location data (headquarters, other locations, markets served)
     - Financial KPIs (revenue range, profit margin, cash flow, growth rate)
     - Operational KPIs (production volume, capacity utilization)
     - Business model (products/services, customer segments, key processes)
     - Technology status (current systems, data sources, automation level)
     - Strategic context (pain points, digitalization goals, competitive pressures)
   - **Fully editable**: Click any field to correct AI extraction or fill in missing data
   - **Add list items**: Expand lists (locations, products, goals) with "+" button
   - **Quality indicator**: Shows extraction completeness (high/medium/low)
   - **No hallucination**: AI only extracts explicitly stated information; missing data stays empty
   - **Token optimization**: Reduces context size by ~80% for all subsequent AI interactions

3. **Digital Maturity Assessment** (Step 1c)
   - Based on **acatech Industry 4.0 Maturity Index** framework
   - Self-assessment on 4 dimensions (1-6 scale):
     - **Resources**: Digital skills, technology infrastructure, smart materials
     - **Information Systems**: IT integration, data collection, analytics capabilities
     - **Culture**: Change readiness, innovation openness, knowledge sharing
     - **Organizational Structure**: Agility, cross-functional teams, flat hierarchies
   - Visual radar chart showing dimension breakdown
   - Overall maturity level helps AI calibrate recommendations

4. **Interactive 6-3-5 Brainstorming** (Step 2)
   - Real-time collaborative ideation with up to 6 participants
   - AI participants that contribute ideas alongside humans
   - Each participant contributes 3 ideas per round
   - 5-minute rounds with automatic sheet rotation
   - QR code sharing for easy session joining

5. **Idea Prioritization** (Step 3)
   - Vote and score generated ideas
   - Collaborative ranking system
   - Select focus project for consultation

6. **CRISP-DM Business Understanding** (Step 4)
   - AI-guided consultation using CRISP-DM methodology
   - Streaming chat responses (Server-Sent Events)
   - Topic progress tracking
   - Extracts 4 key findings:
     - Business Objectives
     - Situation Assessment
     - AI/Data Mining Goals
     - Project Plan

7. **Business Case & Cost Estimation** (Step 5)
   - **Business Case** - 5-Level Value Framework analysis:
     1. Budget Substitution
     2. Process Efficiency
     3. Project Acceleration
     4. Risk Mitigation
     5. Strategic Scaling
   - **Cost Estimation** - Investment analysis, TCO, and ROI calculation

8. **Export & Technical Handover** (Step 6)
   - **Executive Summary** - Overview of all findings
   - **SWOT Analysis** - Company readiness evaluation
   - **Technical Transition Briefing** - Handover document for implementation phase
   - **Professional PDF Export** - Comprehensive report with all consultation data

### Additional Features

- **Multi-language Support** - English and German
- **Expert Mode** - Customize all AI prompts and LLM settings
- **Session Backup/Restore** - Export and import session data
- **Multi-participant Collaboration** - Real-time collaboration in brainstorming and consultation

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React + Vite)                          │
│                                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │ Step1  │ │ Step2  │ │ Step3  │ │ Step4  │ │ Step5  │ │ Step6  │        │
│  │Company │ │ 6-3-5  │ │Priorit-│ │CRISP-DM│ │Business│ │Export &│        │
│  │Profile │ │ Method │ │ization │ │Consult │ │ Case   │ │Handover│        │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘        │
│      │          │          │          │          │          │              │
│  ┌───┴──────────┴──────────┴──────────┴──────────┴──────────┴────────┐    │
│  │  CompanyProfileEditor │ ApiKeyPrompt │ ExpertSettingsModal        │    │
│  └───────────────────────────────┬───────────────────────────────────┘    │
│  ┌───────────────────────────────┴───────────────────────────────────┐    │
│  │                    services/api.js                                 │    │
│  │  apiKeyManager (sessionStorage) + companyProfileAPI + ...          │    │
│  └───────────────────────────────┬───────────────────────────────────┘    │
└──────────────────────────────────┼────────────────────────────────────────┘
                                   │ HTTP/REST + SSE
                                   │ (API key in request body)
┌──────────────────────────────────┼────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                  │
│                                  │                                         │
│  ┌───────────────────────────────┴───────────────────────────────────┐    │
│  │                         Routers                                    │    │
│  │  sessions │ company_info │ maturity_assessment │ six_three_five   │    │
│  │  prioritization │ consultation │ business_case │ cost_estimation  │    │
│  │  export │ expert_settings │ session_backup                        │    │
│  └───────────────────────────────┬───────────────────────────────────┘    │
│                                  │                                         │
│  ┌───────────────────────────────┴───────────────────────────────────┐    │
│  │                         Services                                   │    │
│  │  llm_service.py ──► LiteLLM ──► OpenAI/Anthropic/Mistral/etc      │    │
│  │  company_profile_service │ consultation_service                    │    │
│  │  business_case_service │ cost_estimation_service                   │    │
│  │  ai_participant │ pdf_generator │ web_crawler │ file_processor    │    │
│  └───────────────────────────────┬───────────────────────────────────┘    │
│                                  │                                         │
│  ┌───────────────────────────────┴───────────────────────────────────┐    │
│  │                    Models (SQLAlchemy)                             │    │
│  │  Session (+ company_profile JSON) │ CompanyInfo │ MaturityAssess. │    │
│  │  Participant │ IdeaSheet │ Idea │ Prioritization                  │    │
│  │  ConsultationMessage │ ConsultationFinding                        │    │
│  └───────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
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
- **ReportLab** - PDF generation with charts and professional formatting
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
│   │   │   ├── session.py       # Session (+ company_profile), CompanyInfo, MaturityAssessment
│   │   │   ├── brainstorm.py    # Participant, IdeaSheet, Idea
│   │   │   ├── prioritization.py
│   │   │   └── consultation.py  # Messages, Findings
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   │   ├── company_profile.py   # Structured company profile schema (25+ fields)
│   │   │   ├── expert_settings.py   # Custom prompts, LLM config
│   │   │   └── ...
│   │   ├── routers/             # API endpoint handlers
│   │   │   ├── sessions.py
│   │   │   ├── company_info.py      # Includes company profile extraction endpoints
│   │   │   ├── maturity_assessment.py
│   │   │   ├── six_three_five.py
│   │   │   ├── prioritization.py
│   │   │   ├── consultation.py
│   │   │   ├── business_case.py
│   │   │   ├── cost_estimation.py
│   │   │   ├── export.py
│   │   │   ├── expert_settings.py
│   │   │   └── session_backup.py
│   │   └── services/            # Business logic
│   │       ├── company_profile_service.py  # AI-powered profile extraction
│   │       ├── ai_participant.py    # AI brainstorming participant
│   │       ├── consultation_service.py
│   │       ├── business_case_service.py
│   │       ├── cost_estimation_service.py
│   │       ├── pdf_generator.py
│   │       ├── web_crawler.py
│   │       ├── file_processor.py    # PDF/DOCX text extraction
│   │       └── default_prompts.py   # All AI prompts (EN/DE)
│   ├── migrations/              # Database migrations
│   │   └── add_company_profile.py
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
│   │   │   ├── Step1Page.jsx    # Company Info + Profile Extraction + Maturity
│   │   │   ├── Step2Page.jsx    # 6-3-5 Brainstorming
│   │   │   ├── Step3Page.jsx    # Idea Prioritization
│   │   │   ├── Step4Page.jsx    # AI Consultation (CRISP-DM)
│   │   │   ├── Step5Page.jsx    # Business Case & Cost Estimation
│   │   │   └── Step6Page.jsx    # Export & Handover
│   │   ├── components/          # Reusable components
│   │   │   ├── common/          # Shared UI components
│   │   │   │   ├── ApiKeyPrompt.jsx
│   │   │   │   ├── PageHeader.jsx
│   │   │   │   ├── StepProgress.jsx
│   │   │   │   ├── LLMConfigSection.jsx
│   │   │   │   └── ExplanationBox.jsx
│   │   │   ├── step1/
│   │   │   │   ├── CompanyInfoForm.jsx
│   │   │   │   ├── CompanyInfoDisplay.jsx
│   │   │   │   ├── CompanyProfileEditor.jsx  # Editable profile form
│   │   │   │   ├── FileUploader.jsx
│   │   │   │   └── WebCrawlerForm.jsx
│   │   │   ├── step2/
│   │   │   │   ├── ParticipantJoin.jsx
│   │   │   │   ├── ShareSession.jsx
│   │   │   │   └── IdeaSheet.jsx
│   │   │   └── expert/
│   │   │       ├── ExpertSettingsModal.jsx
│   │   │       ├── PromptEditor.jsx
│   │   │       └── LanguageSelector.jsx
│   │   ├── services/
│   │   │   └── api.js           # API client + apiKeyManager + companyProfileAPI
│   │   └── i18n/
│   │       └── locales/         # en.json, de.json (with profile translations)
│   ├── package.json
│   └── vite.config.js
│
├── DEPLOY.md                    # Deployment instructions
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

2. **Step 1a: Company Information**
   - **Text input**: Type or paste company information directly into the text area
   - **File upload**: Upload PDF or DOCX documents (annual reports, company profiles, etc.)
   - **Web crawling**: Enter your company website URL to automatically extract content
   - Combine multiple sources - all information is aggregated for the AI context

3. **Step 1b: Company Profile Extraction**
   - Click **"Extract Profile"** to let AI analyze your company data and create a structured profile
   - Enter your LLM API key when prompted (stored only in browser session)
   - Review the extracted information organized in sections:
     - Basic info (name, industry, founding year, ownership type)
     - Locations (headquarters, other sites, markets served)
     - Financial KPIs (revenue, profit margin, cash flow, growth rate)
     - Operational KPIs (production volume, capacity utilization)
     - Business model (products/services, customer segments)
     - Technology (current systems, automation level, data sources)
     - Strategy (pain points, digitalization goals, competitive pressures)
   - **Edit fields**: Click any field to correct extracted data or add missing information
   - **Add new entries**: Use the "+" buttons to add items to list fields (locations, products, etc.)
   - **Save changes**: Click "Save Profile" to store your corrections
   - **Re-extract**: Click "Re-extract" to run extraction again with updated company info
   - **Quality indicator**: Shows extraction completeness (high/medium/low based on filled fields)
   - The structured profile reduces token usage by ~80% in all subsequent AI interactions

4. **Step 1c: Digital Maturity Assessment**
   - Rate your company on 4 dimensions using a 1-6 scale (based on acatech Industry 4.0 Maturity Index):
     - **Resources**: Digital competence of employees, technology infrastructure
     - **Information Systems**: IT integration, data collection and processing
     - **Culture**: Willingness to change, openness to innovation
     - **Organizational Structure**: Agility, cross-functional collaboration
   - View your overall maturity level and dimension breakdown chart
   - This assessment helps the AI tailor recommendations to your company's readiness level

5. **Step 2: 6-3-5 Brainstorming**
   - Share the session link or QR code with participants
   - Each participant enters their name to join
   - Enter your API key when prompted (for AI participants)
   - Start the brainstorming session
   - Write 3 ideas during each 5-minute round
   - Sheets rotate to the next participant after each round

6. **Step 3: Prioritization**
   - Review all generated ideas
   - Allocate points to your favorite ideas
   - Select the top-voted idea as your focus project

7. **Step 4: AI Consultation**
   - Enter your API key for the LLM provider (if not already set)
   - Engage in an AI-guided consultation following CRISP-DM methodology
   - Track progress on 4 key topics:
     - Business Objectives
     - Situation Assessment
     - AI/Data Mining Goals
     - Project Plan
   - Click "Generate Summary" to extract findings

8. **Step 5: Business Case & Cost Estimation**
   - Generate a **Business Case** using the 5-level value framework
   - Get **Cost Estimation** with ROI analysis

9. **Step 6: Results & Export**
   - View the **Executive Summary** of your consultation
   - Review the **SWOT Analysis** for project readiness
   - Generate **Technical Transition Briefing** for implementation handover
   - Export everything as a professional **PDF report**

## Expert Mode

Expert Mode allows customization of AI behavior and LLM settings:

### Custom Prompts
All AI prompts can be customized:
- Company profile extraction prompt (structured data extraction)
- Brainstorming prompts (system, round 1, subsequent rounds)
- Consultation prompts (system rules, context template)
- Extraction prompts (summary, business case, cost estimation)
- Analysis prompts (SWOT, transition briefing)

### LLM Configuration
- Choose from preset providers (OpenAI, Mistral, Anthropic, Ollama)
- Configure custom API endpoints
- Test connection before saving

### Accessing Expert Mode
1. Click the gear icon in the page header
2. Toggle "Expert Mode" on
3. Customize prompts and LLM settings as needed

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
- `sessions` - Consultation sessions with settings, expert mode config, and structured company profile (JSON)
- `company_info` - Raw company data from Step 1a (text, uploaded files, crawled content)
- `maturity_assessments` - Digital maturity scores from Step 1c (acatech I4.0 index)
- `participants` - 6-3-5 session participants
- `idea_sheets` - Idea sheets that rotate between participants
- `ideas` - Individual ideas (3 per round per sheet)
- `prioritizations` - Votes and point allocations
- `consultation_messages` - Chat messages (CRISP-DM and Business Case)
- `consultation_findings` - Extracted findings from consultations

### Company Profile Schema

The `company_profile` field in sessions stores a structured JSON object with 25+ fields:

```
CompanyProfile {
  name: string                    # Company name (required)
  industry: string?               # Primary industry
  sub_industry: string?           # Specific sub-industry/niche
  employee_count: string?         # Number range (e.g., "50-100")
  founding_year: int?             # Year founded
  ownership: string?              # "family-owned", "founder-led", etc.
  headquarters: string?           # Main office location
  other_locations: string[]?      # Additional offices/plants
  markets_served: string[]?       # Geographic markets
  annual_revenue: string?         # Revenue range (e.g., "€5-10M")
  profit_margin: string?          # Profitability status
  cash_flow_status: string?       # Cash flow situation
  growth_rate: string?            # Recent growth trends
  production_volume: string?      # Output metrics
  capacity_utilization: string?   # Utilization percentage
  core_business: string?          # Main business description
  products_services: string[]?    # Key offerings
  customer_segments: string[]?    # Target customers
  key_processes: string[]?        # Main business processes
  current_systems: string[]?      # IT/software systems in use
  data_sources: string[]?         # Available data sources
  automation_level: string?       # Current automation status
  pain_points: string[]?          # Business challenges
  digitalization_goals: string[]? # AI/digital transformation goals
  competitive_pressures: string?  # Market competition context
}
```

All fields except `name` are nullable to prevent AI hallucination of missing data.

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

## Evaluation Benchmark

The benchmark evaluates how well different LLMs perform as the AI consultant across a set of manufacturing SME personas. The study's B1 matrix ran **8 models × 6 personas × 3 repetitions = 144 runs**.

### Personas

Persona definitions are stored in `evaluation/benchmark_personas.json` (not included in this repository). Each persona contains a company profile, acatech maturity assessment, focus idea, and ground truth expectations (key metrics, critical questions, implementation challenges, business case direction). To run your own benchmark you need to provide this file or create your own personas following the same schema.

### User-Agent Concept

During the consultation the runner needs a counterpart that responds to the consultant's questions. A **user-agent** — a separate LLM instance — role-plays as the SME manager described in the persona. It receives a system prompt built from the persona profile and answers in character throughout the full consultation dialogue. The user-agent model can differ from the consultant model under evaluation.

### Running a Single Benchmark

```bash
# Ensure the backend is running (http://localhost:8000)
python evaluation/run_test_persona1.py \
  --persona mfg_02_plastics_maintenance \
  --consultant-model openai/your-model \
  --consultant-base https://your-api-endpoint/v1 \
  --api-key $YOUR_API_KEY \
  --user-agent-model openai/gemma-3-27b-it \
  --user-agent-base https://your-ua-endpoint/v1 \
  --user-agent-api-keys $UA_API_KEY \
  --language de \
  --no-pdf
```

#### Key Flags

| Flag | Description |
|---|---|
| `--persona` | Persona ID from `benchmark_personas.json` |
| `--consultant-model` | Model ID for the AI consultant under test |
| `--consultant-base` | Base URL of the consultant model's API |
| `--api-key` | API key for the consultant model |
| `--user-agent-model` | Model that simulates the SME user |
| `--user-agent-base` | Base URL of the user-agent model's API |
| `--user-agent-api-keys` | Comma-separated keys for the user-agent (round-robin) |
| `--language` | Consultation language: `de` or `en` (default: `de`) |
| `--run-id` | Optional identifier embedded in output filenames |
| `--no-pdf` | Skip PDF generation (JSON exports are always saved) |
| `--skip-ideation` | Skip the 6-3-5 brainstorming phase |

### Output Files

Results are written to `evaluation/test_runs/` with the naming pattern `{persona_id}_{timestamp}_{uuid8}_*`:

| File | Content |
|---|---|
| `*_findings.json` | Structured findings extracted from each pipeline phase |
| `*_backup.json` | Full conversation history and raw model responses |
| `*_ground_truth.json` | Ground truth snapshot from the persona definition |

---

## License

BSD 3-Clause License - see [LICENSE](LICENSE) file.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Contact

For questions or support, please open an issue on GitHub.
