# 🚀 The Lenny Growth Assistant

An AI-powered conversational web application that ingests **269 episodes** of Lenny's Podcast transcripts, enabling product managers and growth leaders to ask questions, generate Ship30for30-style essays, and create rich HTML/Markdown artifacts — all within a premium ChatGPT-like interface.

![Stack](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)

---

## 🏗️ Architecture Overview

```
Frontend (HTML/CSS/JS)  ←→  FastAPI Backend  ←→  PostgreSQL + pgvector
                                 ↕
                        Agent Router (Skills)
                         ├── Q&A Skill (RAG)
                         ├── Ship30for30 Skill
                         └── Artifact Skill
                                 ↕
                     LLM Abstraction Layer
                      ├── Ollama (Local)
                      ├── Anthropic Claude
                      └── OpenAI GPT
```

**Key Components:**
- **FastAPI Backend** — REST API + SSE streaming, session management, agentic routing
- **PostgreSQL + pgvector** — Persistent storage for conversations, vector embeddings for RAG
- **Agent Router** — Classifies user intent and routes to appropriate skill (Q&A, Essay, Artifact)
- **LLM Abstraction** — Runtime-switchable between Ollama, Anthropic, and OpenAI
- **RAG Pipeline** — Embeds and retrieves relevant transcript chunks for grounded responses
- **Frontend** — Premium dark-themed UI with chat, sidebar, artifact viewer, and settings

---

## 📋 Prerequisites

Before you begin, ensure you have:

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ | Backend runtime |
| **PostgreSQL** | 15+ with pgvector | Database (or use Supabase) |
| **Ollama** | Latest | Local LLM (mandatory for demo) |
| **Git** | 2.x+ | Cloning repos |

### Install Ollama Models

```bash
# Required: LLM model
ollama pull llama3.1:8b

# Required: Embedding model for RAG
ollama pull nomic-embed-text
```

---

## 🚀 Step-by-Step Setup

### 1. Clone this repository

```bash
git clone <your-repo-url>
cd Chatbot
```

### 2. Clone the transcript data

```bash
git clone https://github.com/ChatPRD/lennys-podcast-transcripts.git backend/data/transcripts
```

### 3. Set up PostgreSQL

**Option A: Local PostgreSQL**
```bash
# Install pgvector extension
# On Ubuntu: sudo apt install postgresql-15-pgvector
# On Mac: brew install pgvector

# Create database
psql -U postgres -c "CREATE DATABASE lenny_assistant;"
psql -U postgres -d lenny_assistant -c "CREATE EXTENSION vector;"
```

**Option B: Supabase (Recommended)**
1. Create a free project at [supabase.com](https://supabase.com)
2. pgvector is pre-installed on Supabase
3. Copy the connection string from Settings → Database → URI

### 4. Configure environment variables

```bash
cd backend
cp .env.example .env
```

Edit `.env` and set:
```env
# Your PostgreSQL connection string
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres

# LLM provider (start with ollama)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Optional: Cloud LLM keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### 5. Install Python dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 6. Start the application

```bash
# Make sure Ollama is running
ollama serve

# Start FastAPI (from the backend directory)
cd backend
uvicorn app.main:app --reload --port 8000
```

### 7. Ingest transcripts

On first run, trigger the transcript ingestion:
```bash
curl -X POST http://localhost:8000/api/admin/ingest
```

> ⚠️ This may take 15-30 minutes depending on your embedding model speed. It processes 269 episodes.

### 8. Open the application

Navigate to **http://localhost:8000** in your browser.

---

## 🎮 Usage Guide

### Q&A Mode (Default)
Simply ask a question about product management, growth, or leadership:
> "What frameworks do guests recommend for finding product-market fit?"

### Ship30for30 Essay Mode
Request an essay and the agent will generate a ~1,250-word formatted piece:
> "Write a Ship30for30 essay about growth loops"

### Artifact Mode
Ask the agent to create visual or document artifacts:
> "Create an HTML infographic showing the key traits of successful PMs"

### Switch LLM Provider
Click the ⚙️ Settings button in the sidebar to toggle between Ollama, Claude, and OpenAI.

---

## 📁 Project Structure

```
Chatbot/
├── PRD.md                      # Product Requirements Document
├── design.md                   # UI/UX Design Document
├── architecture.md             # Technical Architecture
├── README.md                   # This file
├── agent-transcripts/          # AI coding agent logs
├── backend/
│   ├── .env.example            # Environment template
│   ├── requirements.txt        # Python dependencies
│   └── app/
│       ├── main.py             # FastAPI entry point
│       ├── config.py           # Settings & LLM toggle config
│       ├── database.py         # Async SQLAlchemy setup
│       ├── models.py           # ORM models (5 tables)
│       ├── schemas.py          # Pydantic request/response
│       ├── routers/
│       │   ├── sessions.py     # Session CRUD endpoints
│       │   ├── chat.py         # SSE streaming chat
│       │   └── config.py       # LLM config endpoints
│       ├── services/
│       │   ├── llm_service.py  # LLM abstraction (3 providers)
│       │   ├── rag_service.py  # RAG retrieval pipeline
│       │   └── agent_router.py # Intent classification & routing
│       ├── skills/
│       │   ├── qa_skill.py     # Q&A system prompt
│       │   ├── ship30_skill.py # Ship30for30 essay prompt
│       │   └── artifact_skill.py # Artifact generation prompt
│       └── ingestion/
│           ├── ingest.py       # Transcript parsing & chunking
│           └── embeddings.py   # Embedding generation
└── frontend/
    ├── index.html              # Main HTML page
    ├── css/
    │   └── index.css           # Design system (900+ lines)
    └── js/
        ├── api.js              # API client with SSE support
        └── app.js              # Application logic
```

---

## 🔑 Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `LLM_PROVIDER` | ✅ | `ollama` | Active provider: ollama/anthropic/openai |
| `OLLAMA_BASE_URL` | ✅ | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | ✅ | `llama3.1:8b` | Ollama model name |
| `ANTHROPIC_API_KEY` | ❌ | — | Claude API key |
| `OPENAI_API_KEY` | ❌ | — | OpenAI API key |
| `EMBEDDING_PROVIDER` | ❌ | `ollama` | Embedding source |
| `OLLAMA_EMBED_MODEL` | ❌ | `nomic-embed-text` | Ollama embedding model |

---

## 🧪 Testing

```bash
# Health check
curl http://localhost:8000/api/health

# LLM connectivity
curl http://localhost:8000/api/config/health

# Create a session
curl -X POST http://localhost:8000/api/sessions

# Send a message (SSE)
curl -N -X POST http://localhost:8000/api/chat/{session_id} \
  -H "Content-Type: application/json" \
  -d '{"content": "What is product-market fit?"}'
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | FastAPI, Uvicorn, Python 3.11 |
| **Database** | PostgreSQL + pgvector (Supabase) |
| **ORM** | SQLAlchemy (Async) |
| **LLM** | Ollama, Anthropic SDK, OpenAI SDK |
| **Streaming** | Server-Sent Events (SSE) |
| **Frontend** | Vanilla HTML/CSS/JS |
| **Markdown** | Marked.js + Highlight.js |
| **Embeddings** | nomic-embed-text (Ollama) / text-embedding-3-small (OpenAI) |

---

## 📄 License

This project is built for educational and evaluation purposes.
