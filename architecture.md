# Architecture Document
## The Lenny Growth Assistant

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Frontend)                        │
│                                                              │
│  HTML/CSS/JS  ──  REST API calls + SSE streaming             │
│  Marked.js    ──  Markdown rendering                         │
│  Highlight.js ──  Code syntax highlighting                   │
│  iframe       ──  Sandboxed HTML artifact rendering          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/SSE
┌──────────────────────▼──────────────────────────────────────┐
│                    FastAPI Backend                            │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    API Layer                          │   │
│  │  /api/sessions/* ── CRUD for chat sessions           │   │
│  │  /api/chat/*     ── SSE streaming chat               │   │
│  │  /api/config/*   ── LLM toggle & health              │   │
│  │  /api/admin/*    ── Transcript ingestion              │   │
│  └────────────────────────┬─────────────────────────────┘   │
│                           │                                  │
│  ┌────────────────────────▼─────────────────────────────┐   │
│  │              Agent Router (Intent Classifier)         │   │
│  │  Analyzes user message → routes to appropriate skill  │   │
│  └───────┬──────────────┬───────────────┬───────────────┘   │
│          │              │               │                    │
│  ┌───────▼──────┐ ┌────▼────────┐ ┌───▼──────────┐        │
│  │  Q&A Skill   │ │ Ship30for30 │ │ Artifact     │        │
│  │  (Default)   │ │   Skill     │ │   Skill      │        │
│  │  RAG-powered │ │ Essay gen   │ │ HTML/MD gen  │        │
│  └───────┬──────┘ └────┬────────┘ └───┬──────────┘        │
│          │              │               │                    │
│  ┌───────▼──────────────▼───────────────▼───────────────┐   │
│  │              RAG Service                              │   │
│  │  1. Embed query via embedding model                   │   │
│  │  2. Cosine similarity search (pgvector)               │   │
│  │  3. Retrieve top-k relevant transcript chunks         │   │
│  │  4. Format context for LLM prompt                     │   │
│  └───────────────────────┬──────────────────────────────┘   │
│                          │                                   │
│  ┌───────────────────────▼──────────────────────────────┐   │
│  │           LLM Abstraction Layer                       │   │
│  │  ┌──────────┐ ┌────────────┐ ┌───────────┐          │   │
│  │  │ OllamaLLM│ │AnthropicLLM│ │ OpenAILLM │          │   │
│  │  └──────────┘ └────────────┘ └───────────┘          │   │
│  │  Runtime switchable via LLMManager singleton          │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │ asyncpg
┌──────────────────────▼──────────────────────────────────────┐
│              PostgreSQL (Supabase)                            │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐  │
│  │  users   │ │ sessions │ │ messages │ │   artifacts   │  │
│  └──────────┘ └──────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  transcript_chunks (pgvector)                         │   │
│  │  embedding column: vector(768) with IVFFlat index     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Database Schema

### users
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| created_at | TIMESTAMPTZ | NOT NULL |

### sessions
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| user_id | UUID | FK → users.id, ON DELETE CASCADE |
| title | VARCHAR(255) | NOT NULL, default "New Chat" |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL, auto-update |

### messages
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| session_id | UUID | FK → sessions.id, ON DELETE CASCADE |
| role | VARCHAR(20) | NOT NULL ("user" or "assistant") |
| content | TEXT | NOT NULL |
| skill_used | VARCHAR(50) | NULLABLE ("qa", "ship30for30", "artifact") |
| created_at | TIMESTAMPTZ | NOT NULL |

### artifacts
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| message_id | UUID | FK → messages.id, ON DELETE CASCADE |
| session_id | UUID | FK → sessions.id, ON DELETE CASCADE |
| artifact_type | VARCHAR(20) | NOT NULL ("html" or "markdown") |
| title | VARCHAR(255) | NOT NULL |
| content | TEXT | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

### transcript_chunks
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default uuid4 |
| episode_guest | VARCHAR(255) | NOT NULL |
| episode_title | VARCHAR(500) | NOT NULL |
| chunk_text | TEXT | NOT NULL |
| chunk_index | INTEGER | NOT NULL |
| embedding | VECTOR(768) | NULLABLE, IVFFlat indexed |
| metadata | JSONB | NULLABLE |

---

## 3. API Endpoints

### Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create new chat session |
| GET | `/api/sessions` | List all sessions (newest first) |
| GET | `/api/sessions/{id}` | Get session with messages + artifacts |
| PATCH | `/api/sessions/{id}` | Update session title |
| DELETE | `/api/sessions/{id}` | Delete session (cascades) |

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/{session_id}` | Send message → SSE streaming response |
| GET | `/api/chat/{session_id}/messages` | Get message history |
| GET | `/api/chat/artifacts/{id}` | Get single artifact |

### Config
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/config` | Get current LLM config |
| PUT | `/api/config` | Switch LLM provider |
| GET | `/api/config/health` | Check LLM connectivity |

### Admin
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/admin/ingest` | Trigger transcript ingestion |
| GET | `/api/health` | Root health check |

---

## 4. Agentic Routing Logic

The Agent Router uses a **keyword-based intent classifier** to determine which skill handles each request:

```
User Message → Intent Classification → Skill Routing → RAG Context → LLM → Response
```

### Classification Rules:

1. **Explicit hint** (from skill selector dropdown): Takes highest priority
2. **Ship30for30 keywords**: "essay", "article", "write about", "ship30", "blog post", "compose"
3. **Artifact keywords**: "create a", "generate a", "build a" + "html", "dashboard", "infographic", "component"
4. **Default**: Q&A (most natural interaction mode)

### Skill System:

Each skill provides a specialized **system prompt** that:
- Injects RAG context from relevant transcript chunks
- Defines the output format and style rules
- Constrains the LLM to transcript-grounded responses

---

## 5. LLM Toggle Architecture

```python
class LLMManager:
    """Singleton that manages the active LLM provider."""
    
    def switch_provider(provider, model, api_key):
        # 1. Validate provider enum
        # 2. Store new config in memory
        # 3. Destroy old LLM instance
        # 4. Lazy-create new instance on next request
```

The toggle is **memory-based** (not persisted to DB) so the app always starts with `.env` defaults. Runtime changes via the API or settings UI take effect immediately without restart.

Supported providers:

| Provider | SDK | Streaming | Health Check |
|----------|-----|-----------|-------------|
| Ollama | httpx REST | /api/chat stream | /api/tags |
| Anthropic | anthropic SDK | messages.stream() | messages.create() |
| OpenAI | openai SDK | stream=True | completions.create() |

---

## 6. RAG Pipeline

### Ingestion Flow:
1. Clone `ChatPRD/lennys-podcast-transcripts` repo
2. Parse YAML frontmatter + transcript content per episode
3. Chunk text (~1500 chars with 200-char overlap, paragraph-aligned)
4. Generate embeddings via Ollama `nomic-embed-text` (768-dim) or OpenAI
5. Store in `transcript_chunks` table with pgvector

### Query Flow:
1. Embed user query using same embedding model
2. Cosine similarity search via pgvector `<=>` operator
3. Return top-6 most relevant chunks
4. Format as structured context with source attribution
5. Inject into skill's system prompt

---

## 7. SSE Streaming Protocol

The chat endpoint uses **Server-Sent Events** for real-time token streaming:

```
event: skill
data: {"skill": "qa"}

event: token
data: {"token": "Product"}

event: token
data: {"token": "-market"}

event: token
data: {"token": " fit"}

event: artifact
data: {"id": "uuid", "type": "html", "title": "Dashboard", "content": "..."}

event: done
data: {"message_id": "uuid", "skill_used": "qa", "session_title": "..."}
```

This allows the frontend to:
- Show which skill is being used immediately
- Stream text word-by-word for a live typing effect
- Open the artifact panel as soon as artifact data arrives
- Update session title after completion
