# NeuroGraph AI — Backend

A production-focused conversational AI agent built with LangGraph, FastAPI, and Gemini 2.5 Flash. The system features a manually constructed ReAct graph with two memory layers — short-term memory (STM) via LangGraph checkpointing and long-term memory (LTM) via a persistent user profile store.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI Backend                     │
│                                                         │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  Chat API   │    │  Threads API │    │ Memory API │  │
│  │  /chat      │    │  /threads    │    │ /memory    │  │
│  └──────┬──────┘    └──────────────┘    └────────────┘  │
│         │                                               │
│  ┌──────▼──────────────────────────────────────────┐    │
│  │            LangGraph ReAct Agent                │    │
│  │                                                 │    │
│  │  reasoner ──► tool_executor ──► reasoner ──► END│    │
│  │      │                                          │    │
│  │      └── Gemini 2.5 Flash + 5 Tools             |    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────────┐    ┌──────────────────────────┐   │
│  │  STM             │    │  LTM                     │   │
│  │  SqliteSaver /   │    │  user_profile table      │   │
│  │  AsyncPostgres   │    │  SQLite / Postgres       │   │
│  └──────────────────┘    └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI |
| Agent | LangGraph (manual ReAct graph) |
| LLM | Gemini 2.5 Flash via `langchain-google-genai` |
| STM | LangGraph `AsyncSqliteSaver` / `AsyncPostgresSaver` |
| LTM | SQLAlchemy + SQLite (dev) / Postgres (prod) |
| Observability | LangSmith |
| Config | Pydantic Settings |
| Streaming | FastAPI `StreamingResponse` + SSE |

---

## Project Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py                  # Dependency injection
│   │   └── routes/
│   │       ├── chat.py              # POST /chat/stream, GET /chat/history/{id}
│   │       ├── threads.py           # CRUD /threads
│   │       ├── memory.py            # CRUD /memory/profile
│   │       └── health.py            # GET /health
│   ├── agent/
│   │   ├── graph.py                 # LangGraph graph definition
│   │   ├── state.py                 # AgentState TypedDict
│   │   ├── nodes/
│   │   │   ├── reasoner.py          # LLM reasoning node
│   │   │   ├── tool_executor.py     # Tool execution node
│   │   │   └── memory_writer.py     # LTM write node
│   │   └── tools/
│   │       ├── calculator.py
│   │       ├── search.py            # Tavily web search
│   │       ├── weather.py
│   │       ├── finance.py           # yFinance
│   │       └── datetime_tool.py
│   ├── core/
│   │   ├── config.py                # Pydantic Settings
│   │   ├── exceptions.py            # Custom exception hierarchy
│   │   └── logging.py              # Structured logging
│   ├── db/
│   │   ├── base.py                  # SQLAlchemy engine + session factory
│   │   └── models.py                # Thread + UserProfile ORM models
│   ├── memory/
│   │   ├── checkpointer.py          # STM checkpointer config
│   │   └── ltm_store.py             # LTM CRUD operations
│   ├── schemas/
│   │   ├── chat.py
│   │   ├── thread.py
│   │   └── memory.py
│   └── main.py                      # App factory + lifespan
├── data/                            # SQLite files (local dev, gitignored)
├── .env                             # Local secrets (gitignored)
├── .env.example                     # Environment variable reference
└── requirements.txt
```

---

## Memory Architecture

### Short-Term Memory (STM)

Implemented via LangGraph's checkpointing system. Each conversation thread maintains its own checkpoint — the full agent state (messages, tool calls, reasoning) is persisted per turn and restored on subsequent requests within the same thread.

- **Local dev:** `AsyncSqliteSaver` → `data/checkpoints.db`
- **Production:** `AsyncPostgresSaver` → Supabase Postgres

### Long-Term Memory (LTM)

Implemented as a key-value profile store backed by SQLAlchemy. The agent extracts persistent user facts (name, location, profession, preferences) during conversation and writes them via a `memory_writer` node. On each new request, the stored profile is injected into the system prompt so the agent retains context across sessions and threads.

- **Local dev:** SQLite → `data/neurograph.db`
- **Production:** Supabase Postgres

---

## Agent Graph

The ReAct graph is built manually using LangGraph's `StateGraph` — not the prebuilt `create_react_agent`. This allows custom node definitions for tool execution and memory writing.

```
START
  │
  ▼
reasoner          ← Gemini 2.5 Flash, decides next action
  │
  ├── tool call? ──► tool_executor ──► reasoner (loop)
  │
  └── done? ──► END
                 │
                 └── memory_writer runs post-graph
                     (fresh DB session, outside graph)
```

**Why manual graph construction:**
The prebuilt `create_react_agent` does not support custom post-graph hooks like the LTM memory writer, which requires a database session injected at request time rather than graph compile time.

---

## Tools

| Tool | Description |
|---|---|
| `calculator` | Evaluates mathematical expressions |
| `tavily_search` | Web search via Tavily API — returns sources with title + URL |
| `weather` | Current weather for any city via wttr.in |
| `finance` | Stock price and info via yFinance |
| `get_datetime` | Current UTC date and time |

---

## API Reference

### Chat

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat/stream` | Send a message, receive SSE stream |
| GET | `/chat/history/{thread_id}` | Full message history for a thread |

#### SSE Event Types

```json
{"type": "text", "content": "..."}
{"type": "tool_start", "tool_name": "...", "tool_input": {}}
{"type": "tool_end", "tool_name": "...", "tool_output": "...", "sources": []}
{"type": "done"}
{"type": "error", "message": "..."}
```

### Threads

| Method | Endpoint | Description |
|---|---|---|
| POST | `/threads` | Create a new thread |
| GET | `/threads` | List all threads (ordered by recent activity) |
| GET | `/threads/{id}` | Get a single thread |
| PATCH | `/threads/{id}` | Rename a thread |
| DELETE | `/threads/{id}` | Delete a thread |

### Memory (LTM)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/memory/profile` | Read all stored profile facts |
| PUT | `/memory/profile` | Upsert a profile entry |
| PATCH | `/memory/profile/{key}` | Update a single entry |
| DELETE | `/memory/profile/{key}` | Delete a single entry |
| DELETE | `/memory/profile` | Clear entire profile |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |

---

## Environment Variables

Copy `.env.example` to `.env` and fill in your values.

```env
# Gemini
GOOGLE_API_KEY=

# LangSmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=neurograph-ai

# Tavily
TAVILY_API_KEY=

# App
APP_ENV=development
FRONTEND_URL=http://localhost:5173

# Database
# Leave DATABASE_URL empty for SQLite (local dev)
# Set to Supabase Postgres connection string for production
DATABASE_URL=
SQLITE_DB_PATH=./data/neurograph.db
CHECKPOINT_DB_PATH=./data/checkpoints.db
```

---

## Local Development

**Prerequisites:** Python 3.11+, pip

```bash
# 1. Clone and navigate to backend
cd neurograph-ai/backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Fill in your API keys in .env

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

Swagger UI available at `http://localhost:8000/docs`

---

## Production Deployment (Render)

1. Create a new Web Service on Render, connect your GitHub repo
2. Set build command: `pip install -r requirements.txt`
3. Set start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add all environment variables from `.env.example` in Render dashboard
5. Set `DATABASE_URL` to your Supabase Postgres connection string
6. Set `APP_ENV=production`
7. Set `FRONTEND_URL` to your Vercel deployment URL

---

## Observability

All LLM calls, tool executions, and agent graph runs are traced automatically via LangSmith. Set `LANGCHAIN_API_KEY` and `LANGCHAIN_PROJECT` in your environment — no additional instrumentation required.

Traces are visible at `https://smith.langchain.com` under your configured project.

---

## Known Limitations and Future Improvements

| Area | Current | Future Improvement |
|---|---|---|
| Authentication | None — all endpoints public | JWT-based auth via `python-jose` |
| STM in production | AsyncPostgresSaver (Supabase) | Already implemented |
| Rate limiting | None | `slowapi` middleware |
| Input validation | Pydantic schema only | Message length limits |
| Tests | None | `pytest` + `httpx.AsyncClient` |
| Structured logging | Plain text | JSON logs via `python-json-logger` |
| Calculator security | `eval()` with restricted builtins | `numexpr` or `mathjs` |
| Pagination | All results returned | Limit/offset on `/threads` and `/memory/profile` |