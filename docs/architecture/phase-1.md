# MATRIOSHAI Core — Phase 1 Architectural Specification

## 1. Executive Summary

MATRIOSHAI is designed as a local-first personal AI operating layer. Phase 1 delivers **MATRIOSHAI CORE**, establishing decoupled subsystem boundaries so future phases (5C Executive System, Privacy Gatekeeper, Developer Tools, Integrations, Browser Automation, and MCP Tools) can plug in without architectural refactoring.

---

## 2. Core Architectural Layers

```
UI Layer (Tauri 2.x + React + TS)
  ↓ HTTP REST & SSE Streaming (127.0.0.1:8000)
FastAPI API Routers (/api/v1/*)
  ↓
Services Layer (ConversationService, NotesService, MemoryService, StatusService)
  ↓
Providers & Repositories (LLMProvider -> OllamaProvider, EmbeddingProvider -> LocalEmbeddingProvider, SQLite DB)
  v
Durable Local Storage (data/database, data/notes, data/memory, data/logs)
```

---

## 3. Storage Model & Source of Truth

- **Structured Metadata**: Stored in SQLite (`data/database/matrioshai.db`) using WAL journal mode. Contains tables: `users`, `conversations`, `messages`, `notes`, `memory_items`, `app_settings`.
- **Markdown Notes**: Plain `.md` files under `data/notes/YYYY/MM/filename.md` are the durable source of truth. Metadata and tag indices are synchronized to SQLite.
- **Path Traversal Protection**: `NotesService` validates that every resolved path is strictly contained within `data/notes/`. Attempts like `../../etc/passwd` raise security errors and return HTTP 400.

---

## 4. Tiered Memory Architecture

MATRIOSHAI Core implements a 3-tier memory engine:

1. **CORE MEMORY**: Small, structured, high-priority facts (user preferences, active goals, core facts). Automatically injected into every system prompt.
2. **RECALL MEMORY**: Recent decisions, conversation summaries, and active context. Searched via keyword + vector score ranking.
3. **ARCHIVAL MEMORY**: Historical knowledge, documents, and reference materials. Prepared for `sqlite-vec` / ONNX runtime vector extension.

---

## 5. LLM Provider Abstraction

- Abstract Base Class: `LLMProvider` (`health`, `model_info`, `chat`, `stream_chat`).
- Implementation: `OllamaProvider` connecting via `httpx.AsyncClient` to `http://127.0.0.1:11434` with model `qwen3:3b` (configurable).
- Fallback Handling: If Ollama is offline or model is missing, backend responds with clear status message ("LOCAL AI: Unavailable"). UI remains responsive and functional for viewing past history, memory, and editing markdown notes.

---

## 6. Future Extension Points

```
                        +----------------------------+
                        |     MATRIOSHAI CORE        |
                        +--------------+-------------+
                                       |
          +----------------------------+----------------------------+
          v                            v                            v
+------------------+          +------------------+          +------------------+
|  5C EXECUTIVE    |          | PRIVACY GATEWAY  |          | INTEGRATIONS &   |
|  SYSTEM          |          |                  |          | MCP AGENTS       |
|  - CEO Persona   |          | - PII Redaction  |          | - Gmail/Slack    |
|  - COO Persona   |          | - Audit Logging  |          | - Browser Auto   |
|  - CFO Persona   |          | - Policy Rules   |          | - Terminal Agent |
|  - CMO Persona   |          |                  |          |                  |
|  - CTO Persona   |          |                  |          |                  |
+------------------+          +------------------+          +------------------+
```

---

## 7. Definition of Done Checklist

- [x] Desktop app launches (Tauri 2.x + Vite + React)
- [x] FastAPI backend launches and binds strictly to `127.0.0.1`
- [x] React communicates with FastAPI over REST & SSE streaming
- [x] SQLite database initializes with migrations
- [x] Conversations & Messages persist across application restarts
- [x] Ollama integration works with configurable model name
- [x] Graceful fallback when Ollama is offline ("LOCAL AI: Unavailable")
- [x] Notes are created as Markdown files under `data/notes/` and indexed in SQLite
- [x] Path traversal security protection validated
- [x] 3-tier memory engine (Core, Recall, Archival) implemented
- [x] System status diagnostics panel functional
- [x] Structured logging implemented
- [x] All backend pytest automated tests pass
- [x] Frontend TypeScript typecheck and build pass cleanly
- [x] Documentation & Architecture specifications written
