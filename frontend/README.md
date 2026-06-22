# NeuroGraph AI — Frontend

A React frontend for the NeuroGraph AI conversational agent. Built with Vite, Tailwind CSS v4, and a native `fetch`-based SSE client. All state is managed through a single React context — no Redux, no external state library.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 19 |
| Build Tool | Vite 8 |
| Styling | Tailwind CSS v4 (`@tailwindcss/vite` plugin) |
| Markdown Rendering | `react-markdown` + `@tailwindcss/typography` |
| HTTP Client | Axios (thread/memory API calls) + native `fetch` (SSE stream) |
| State Management | React Context + `useState` / `useCallback` / `useRef` |

---

## Project Structure

```
frontend/
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── src/
│   ├── api/
│   │   └── client.js                # Axios instance (baseURL: localhost:8000)
│   ├── components/
│   │   ├── Chat/
│   │   │   ├── ChatWindow.jsx       # Message list, streaming, memory notification
│   │   │   ├── MessageBubble.jsx    # Human + AI message rendering
│   │   │   ├── StreamingMessage.jsx # Live streaming render with tool badges
│   │   │   └── ChatInput.jsx        # Auto-resize textarea, Enter to send
│   │   ├── Sidebar/
│   │   │   ├── Sidebar.jsx          # New chat, collapse toggle, profile toggle
│   │   │   ├── ThreadList.jsx       # List of conversation threads
│   │   │   └── ThreadItem.jsx       # Thread row — click, rename, delete
│   │   ├── Memory/
│   │   │   └── ProfileViewer.jsx    # LTM profile panel — view, delete entries
│   │   └── ToolCall/
│   │       └── ToolCallBadge.jsx    # Tool badge — running/done state, expandable output
│   ├── context/
│   │   └── ChatContext.jsx          # Global state + all API calls + SSE handler
│   ├── pages/
│   │   └── ChatPage.jsx             # Root layout — Sidebar + ChatWindow + ProfileViewer
│   ├── App.jsx                      # ChatProvider wrapper
│   ├── main.jsx                     # React DOM entry point
│   └── index.css                    # Tailwind imports + global styles
├── index.html
├── vite.config.js
└── package.json
```

---

## Architecture

### State Management

All application state lives in `ChatContext`. Components read from context via `useChat()` — no prop drilling anywhere.

```
ChatContext (single source of truth)
├── threads[]              — sidebar thread list
├── activeThreadId         — currently selected thread
├── messages[]             — committed message history
├── streamingMessage       — live in-progress AI response
├── isStreaming            — input disabled during stream
├── profile[]              — LTM profile entries
├── showProfile            — profile panel visibility
└── memoryNotification     — { keys[] } — auto-dismissed after 4s
```

### SSE Streaming

The backend streams responses as Server-Sent Events. The frontend reads the stream using the native `fetch` + `ReadableStream` API — not `EventSource` — because `EventSource` does not support `POST` requests.

```
fetch POST /chat/stream
  → ReadableStream reader
  → TextDecoder + line buffer
  → JSON.parse each "data: {...}" line
  → handleSSEEvent(event)
```

#### SSE Event Handling

| Event Type | Action |
|---|---|
| `text` | Appends to `streamingMessage.content`, strips `MEMORY_UPDATE:` lines live |
| `tool_start` | Sets `streamingMessage.currentTool` with `status: running` |
| `tool_end` | Moves tool to `streamingMessage.toolCalls[]` with `status: done` |
| `memory_update` | Shows `🧠 Memory updated` notification, auto-dismisses after 4s |
| `done` | Commits `streamingMessage` to `messages[]`, clears streaming state |
| `error` | Shows error message, clears streaming state |

### MEMORY_UPDATE Filtering

The agent appends `MEMORY_UPDATE: key=x value=y` sentinel lines to its responses for LTM persistence. These are never intended for display. The frontend strips them in two places:

- **During streaming** — `stripMemoryUpdates()` runs on each `text` chunk as it arrives
- **On `done`** — a final strip pass runs before committing to `messages[]`

This ensures sentinel lines never appear in the rendered chat, regardless of streaming timing.

---

## Components

### ChatWindow

Root chat component. Renders the committed message list, the live `StreamingMessage`, and the `🧠 Memory updated` notification. Handles auto-scroll to the latest message on every update.

The memory notification renders as a small purple pill between the message list and the input bar — non-intrusive, passive, auto-dismisses after 4 seconds.

### MessageBubble

Renders a single committed message.

- **Human messages** — right-aligned gray bubble
- **AI messages** — left-aligned, markdown rendered via `react-markdown` with `@tailwindcss/typography` prose styles. Tool badges render above the response text, sources render below.

Tool badges and sources are visible during live streaming. On history reload, only the AI's final text response is shown — tool metadata is not persisted across page refresh. See [Known Limitations](#known-limitations-and-future-improvements).

### StreamingMessage

Renders the live in-progress AI response. Distinct from `MessageBubble` because streaming state has additional fields (`currentTool`, `toolCalls[]`, cursor blink) that committed messages do not.

States handled:
- **Thinking** — three bouncing dots while waiting for first content
- **Tool running** — `ToolCallBadge` with `Using Web Search...` + pulse indicator
- **Streaming text** — markdown rendered live with blinking cursor
- **Sources** — shown below text once streaming content exists

### ToolCallBadge

Pill badge showing tool execution status. Two visual states:

- `status: running` — blue tint, `Using {Tool}...` label, animated pulse dot
- `status: done` — gray tint, `Used {Tool}` label, expandable chevron

Click to expand and view the raw tool output (truncated to 200 characters). Each tool has a dedicated icon and label:

| Tool | Icon | Label |
|---|---|---|
| `calculator` | 🧮 | Calculator |
| `weather` | 🌤️ | Weather |
| `finance` | 📈 | Finance |
| `get_datetime` | 🕐 | Date & Time |
| `tavily_search` | 🔍 | Web Search |

### Sidebar

Left panel containing the thread list and navigation controls.

- **Collapse toggle** — shrinks to icon-only mode (`w-14`) for more reading space
- **+ New Chat** — creates a thread via `POST /threads` and sets it active
- **Thread list** — sorted by most recent, click to load history
- **Memory Profile button** — toggles `ProfileViewer`, loads profile on open

### ThreadItem

Individual thread row in the sidebar.

- **Single click** — selects thread, loads history via `GET /chat/history/{id}`
- **Double click** — activates inline rename input
- **Enter** — confirms rename via `PATCH /threads/{id}`
- **Escape** — cancels rename
- **Hover** — reveals delete button (`DELETE /threads/{id}`)

### ProfileViewer

Right panel showing the agent's long-term memory about the user. Opens as a third column alongside the chat window.

- Lists all profile entries (key formatted as Title Case, value as stored)
- `✕` button on each entry — deletes via `DELETE /memory/profile/{key}`
- `Clear all memory` button — clears via `DELETE /memory/profile`
- Auto-refreshes when a `memory_update` SSE event fires while the panel is open

### ChatInput

Auto-resizing textarea. Grows up to `128px` then scrolls. `Enter` sends, `Shift+Enter` inserts a newline. Disabled and dimmed while a response is streaming.

---

## Local Development

**Prerequisites:** Node.js 18+

```bash
# 1. Navigate to frontend
cd neurograph-ai/frontend

# 2. Install dependencies
npm install

# 3. Start dev server
npm run dev
```

App runs at `http://localhost:5173`

The backend must be running at `http://localhost:8000` before using the app. Start the backend first — see `backend/README.md`.

---

## Production Deployment (Vercel)

1. Connect your GitHub repo to Vercel
2. Set framework preset to **Vite**
3. Set build command: `npm run build`
4. Set output directory: `dist`
5. Update `src/api/client.js` baseURL and the `fetch` URL in `ChatContext.jsx` to point to your deployed backend URL before building

---

## Known Limitations and Future Improvements

| Area | Current | Future Improvement |
|---|---|---|
| Tool history on reload | Tool badges and sources visible during live streaming only — not shown on history reload | Requires a dedicated `chat_messages` table on the backend written at stream time. Frontend would read `tool_calls` from the history response and render badges identically to live stream |
| Backend URL | Hardcoded to `localhost:8000` in two places — `api/client.js` and `ChatContext.jsx` | Move to a `.env` variable (`VITE_API_URL`) and reference via `import.meta.env` |
| Error handling | Stream errors show a generic message | Per-event error types with user-facing descriptions |
| Loading states | No skeleton loaders on history load or thread switch | Skeleton UI for message area during `selectThread` |
| Authentication | No auth — single shared user | JWT token stored in context, attached as `Authorization` header on all requests |
| Message timestamps | Not displayed | Show relative timestamps on hover |
| Empty state | Generic placeholder text | Suggested starter prompts |