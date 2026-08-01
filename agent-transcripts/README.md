# Agent Transcripts — The Lenny Growth Assistant

This folder contains transcripts and logs from AI coding agents used during development.

## Development Tools Used

- **Gemini Antigravity IDE** — Primary coding agent for architecture, backend, frontend, and documentation
- Session ID: `66146911-37ae-4426-9061-4a08c618e1d6`

## Build Timeline

### Phase 1: Research & Planning (15:33 - 15:37)
- Researched Ship30for30 writing style
- Analyzed ChatPRD/lennys-podcast-transcripts GitHub repository structure
- Researched Matt Pocock's Software Factory methodology
- Studied FastAPI + RAG + PostgreSQL architecture patterns
- Created comprehensive implementation plan

### Phase 2: Execution (15:37 - 15:53)
- Built complete project structure (38 files)
- Implemented FastAPI backend with:
  - SQLAlchemy ORM models (5 tables including pgvector)
  - LLM abstraction layer (Ollama/Claude/OpenAI with streaming)
  - RAG pipeline (transcript parsing, chunking, embedding, retrieval)
  - Agentic router with 3 skills (Q&A, Ship30for30, Artifact)
  - REST + SSE streaming API endpoints
- Built premium frontend:
  - 900+ line CSS design system (dark glassmorphic theme)
  - ChatGPT-like chat interface with sidebar
  - Artifact viewer with iframe/markdown rendering
  - Settings modal for LLM provider toggle
- Created documentation:
  - PRD.md, design.md, architecture.md, README.md

### Challenges & Corrections
1. **Node.js not available** — Adapted from Vite+React plan to static HTML/CSS/JS served by FastAPI. This actually simplified deployment.
2. **PowerShell syntax** — Initial `&&` command chaining failed; switched to `;` separator.
3. **GitHub raw HTML** — Initial repo scrape returned HTML; switched to GitHub API for structured data.

## Agent Decision Log

| Decision | Reasoning |
|----------|-----------|
| Static frontend vs React | Node.js not installed; static files are simpler to deploy and evaluate |
| pgvector for RAG | Same DB for app data + vectors; no separate vector DB needed |
| Keyword-based intent classification | Simpler and more predictable than LLM-based classification for 3 skills |
| SSE for streaming | Better browser support than WebSockets; simpler implementation |
| Memory-based LLM toggle | App always starts from .env defaults; runtime changes are ephemeral |
