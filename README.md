# AI & Digitalization Consultant for SMEs

An AI-powered digitalization consultant application for Small and Medium Enterprises (SMEs) that guides companies through a comprehensive 4-step consultation process using the Mistral-small LLM.

## Features

### 4-Step Consultation Process

1. **Company Overview Collection**
   - Free text input for company information
   - File uploads (PDF, DOCX) with automatic text extraction
   - Web crawling to gather information from company websites

2. **Interactive 6-3-5 Brainstorming**
   - Real-time collaborative ideation with up to 6 participants
   - Each participant contributes 3 ideas per round
   - 5-minute rounds with automatic sheet rotation
   - WebSocket-based real-time updates

3. **Idea Prioritization**
   - Vote and score generated ideas
   - Collaborative ranking system
   - Identify top ideas for implementation

4. **AI-Guided Consultation Interview**
   - Interactive interview powered by Mistral-small API
   - Focus on 3 key factors:
     - AI/digitalization project to tackle
     - Main risks and challenges
     - End user identification
   - Context-aware responses based on company info and brainstorming results

5. **Professional PDF Export**
   - Comprehensive report generation
   - Includes all consultation data from all 4 steps
   - Professional formatting with sections and summaries

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - ORM for database operations
- **SQLite** - Database with WAL mode for better concurrency
- **WebSockets** - Real-time communication
- **Mistral AI API** - LLM integration
- **ReportLab** - PDF generation
- **BeautifulSoup4** - Web scraping
- **PyPDF2 & python-docx** - File processing
- **Cryptography** - API key encryption

### Frontend
- **React 18** - UI framework
- **React Router** - Navigation
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Axios** - HTTP client
- **Socket.IO Client** - WebSocket client
- **Zustand** - State management
- **React Dropzone** - File uploads
- **React Timer Hook** - Countdown timers

## Project Structure

```
ai-consultant/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Database setup
│   │   ├── models/              # SQLAlchemy models
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API endpoints
│   │   ├── services/            # Business logic
│   │   └── utils/               # Utilities
│   ├── uploads/                 # File storage
│   ├── exports/                 # Generated PDFs
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── components/          # React components
│   │   ├── hooks/               # Custom hooks
│   │   ├── services/            # API clients
│   │   ├── context/             # React context
│   │   └── styles/              # CSS files
│   ├── package.json
│   └── vite.config.js
│
└── database/
    └── ai_consultant.db         # SQLite database
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

   Edit `.env` and set:
   - `ENCRYPTION_KEY` - Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `MISTRAL_API_KEY` - Your Mistral API key (optional, users can provide their own)
   - Other settings as needed

5. **Run the backend**
   ```bash
   cd app
   python main.py
   ```

   Or using uvicorn directly:
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
   VITE_WS_URL=ws://localhost:8000
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
   - Share the session link with up to 5 other participants (6 total)
   - Each participant enters their name to join
   - When ready, start the brainstorming session
   - Write 3 ideas during each 5-minute round
   - Sheets automatically rotate to the next participant
   - Continue for up to 6 rounds or until all sheets are filled

4. **Step 3: Prioritization**
   - Review all generated ideas
   - Vote or score each idea
   - See ranked results based on collective votes

5. **Step 4: AI Consultation**
   - Enter your Mistral API key (securely encrypted)
   - Engage in an AI-guided interview
   - The AI will help identify:
     - Which AI/digitalization project to tackle
     - Main risks and challenges
     - Target end users
   - Review the extracted key findings

6. **Export**
   - Generate a comprehensive PDF report
   - Download the report containing all consultation data

## API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Database Schema

The application uses 8 main tables:
- `sessions` - Consultation sessions
- `company_info` - Company data from Step 1
- `participants` - 6-3-5 session participants
- `idea_sheets` - Idea sheets that rotate
- `ideas` - Individual ideas (3 per round)
- `prioritizations` - Votes and rankings
- `consultation_messages` - AI interview messages
- `consultation_findings` - Key findings (3 factors)

## Security Features

- **API Key Encryption**: Mistral API keys are encrypted using Fernet before storage
- **Input Validation**: All user inputs are validated and sanitized
- **File Upload Security**: File type and size restrictions, UUID-based filenames
- **CORS Protection**: Configured allowed origins
- **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

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

## Current Status

✅ **Phase 1 Complete**: Foundation & Setup
- Project structure initialized
- Backend with FastAPI, database models, and session management
- Frontend with React, routing, and session context
- All configuration files ready

🔄 **Next Phases**:
- Phase 2: Company Overview Collection (Step 1)
- Phase 3: 6-3-5 Brainstorming (Step 2)
- Phase 4: Idea Prioritization (Step 3)
- Phase 5: AI Consultation (Step 4)
- Phase 6: PDF Export
- Phase 7: Testing & Polish

## License

MIT License

## Contributing

This is a diploma/thesis project. Contributions are welcome after initial completion.

## Contact

For questions or support, please contact the project maintainer.
