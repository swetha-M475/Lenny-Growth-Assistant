# Product Requirements Document (PRD)
## The Lenny Growth Assistant

**Version:** 1.0  
**Author:** AI-assisted development  
**Date:** August 2026  

---

## 1. Problem Statement

Product managers, growth leaders, and startup operators frequently seek actionable advice from industry experts. Lenny Rachitsky's podcast (269+ episodes) is a goldmine of tactical product and growth insights, but **finding specific answers buried across hundreds of hours of conversation is impractical**.

There is no existing tool that:
1. Makes this knowledge searchable via natural language Q&A
2. Synthesizes insights into publishable content formats
3. Generates visual artifacts from the knowledge base

## 2. Target Users

| User Persona | Needs |
|--------------|-------|
| **Product Managers** | Quick answers on frameworks, prioritization, and PM career advice |
| **Startup Founders** | Tactical growth strategies, product-market fit guidance |
| **Content Creators** | Ready-to-publish essays synthesizing expert perspectives |
| **Growth Engineers** | Data-driven frameworks and visual reference materials |

## 3. Core Features

### 3.1 Conversational Q&A (RAG-Powered)
- Natural language questions about product, growth, and leadership topics
- Answers grounded strictly in Lenny's podcast transcripts (269 episodes)
- Source citations with guest name and episode title
- Multi-turn conversation context within sessions

### 3.2 Ship30for30 Essay Generation
- Dedicated skill for generating ~1,250-word essays
- Ship30for30 formatting: strong hook, 1/3/1 rhythm, bold text, bullet points
- Content synthesized from relevant podcast insights
- Output as a rendered Markdown artifact

### 3.3 Artifact Generation & Viewer
- Generate HTML/CSS components (dashboards, infographics, checklists)
- Generate Markdown documents (frameworks, summaries)
- Side-by-side artifact viewer (chat left, artifact right)
- HTML rendered in sandboxed iframe; Markdown rendered with styled parser

### 3.4 Session Management
- Create new chat sessions (like ChatGPT's "New Chat")
- Session list in sidebar with auto-generated titles
- Persistent storage of all conversations
- Delete sessions

### 3.5 LLM Configuration Toggle
- Switch between Ollama (local), Anthropic Claude, and OpenAI
- Runtime switching via settings modal
- Connection health check
- API key input for cloud providers

## 4. Technical Constraints

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL with pgvector extension (via Supabase)
- **Local LLM:** Ollama (mandatory for demo)
- **Frontend:** Static HTML/CSS/JS served by FastAPI
- **Knowledge Base:** ChatPRD/lennys-podcast-transcripts GitHub repo

## 5. Success Metrics

| Metric | Target |
|--------|--------|
| Q&A Response Accuracy | Answers grounded in transcripts with citations |
| Essay Quality | ~1,250 words, Ship30for30 format, skimmable |
| Artifact Rendering | HTML/CSS renders correctly in viewer |
| Session Persistence | All data survives page refresh |
| LLM Toggle | Seamless switch between 3 providers |
| UI Polish | Premium dark theme, smooth animations |

## 6. Out of Scope (v1)

- User authentication (single default user)
- File uploads
- Voice input/output
- Multi-user collaboration
- Production deployment
