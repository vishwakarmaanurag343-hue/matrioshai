# MATRIOSHAI Core (Phase 1)

> **Local-First Personal AI Operating Layer for macOS and Windows**

MATRIOSHAI is an architecture designed for long-term local-first personal AI context, memory, knowledge search, reasoning, and tool execution.

Phase 1 provides the production-grade **MATRIOSHAI CORE** foundation: desktop shell, React UI, FastAPI backend, SQLite persistence, 3-tier memory engine, Markdown notes system, and local LLM integration via Ollama.

---

## 🏗 Architecture Overview

```
+------------------------------------------------------------------------+
|                              TAURI 2.X DESKTOP SHELL                   |
|  +------------------------------------------------------------------+  |
|  |                   React + TypeScript + Vite UI                   |  |
|  |  [Sidebar]  |  [Chat View]  |  [Memory View]  |  [Notes View]    |  |
|  +------------------------------------------------------------------+  |
+-----------------------------------|------------------------------------+
                                    | REST & SSE (127.0.0.1:8000)
                                    v
+------------------------------------------------------------------------+
|                          PYTHON FASTAPI BACKEND                        |
|  +------------------------------------------------------------------+  |
|  |                         API ROUTERS                              |  |
|  |  /conversations | /chat | /notes | /memory | /status | /settings |  |
|  +------------------------------------------------------------------+  |
|                                   |                                    |
|         +-------------------------+-------------------------+          |
|         v                                                   v          |
|  +-----------------------+                       +------------------+  |
|  |  APPLICATION SERVICES  |                       |  LLM ABSTRACTION |  |
|  |  - ConversationSvc    |                       |  - LLMProvider   |  |
|  |  - NotesSvc (MD)      |                       |  - OllamaProvider|  |
|  |  - MemorySvc (3-Tier) |                       +--------+---------+  |
|  +-----------+-----------+                                |            |
+--------------|--------------------------------------------|------------+
               |                                            v
               v                                    +---------------+
+------------------------------+                    | OLLAMA SERVER |
| ISOLATED LOCAL STORAGE DATA/ |                    |  (Qwen3 3B)   |
| - database/matrioshai.db     |                    +---------------+
| - notes/YYYY/MM/*.md         |
| - memory/                    |
| - logs/app.log               |
+------------------------------+
```

---

## ⚡ Prerequisites

1. **Node.js** >= v18
2. **Python** >= 3.10
3. **Rust & Cargo** (for Tauri 2.x desktop app build)
4. **Ollama** (for running local AI models)
   - Download & Install from [ollama.com](https://ollama.com)
   - Pull configured default model (`qwen3:3b`):
     ```bash
     ollama pull qwen3:3b
     ```

---

## 🚀 Getting Started

### 1. Installation

Clone repository and set up backend virtual environment:

```bash
# Clone repository
cd matrioshai

# Install backend dependencies
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..

# Install desktop frontend dependencies
cd apps/desktop
npm install
cd ../..
```

### 2. Running in Development Mode

#### Option A: One-liner Script (Backend + Vite Web UI)
```bash
./scripts/dev.sh
```

#### Option B: Full Tauri Desktop Shell
```bash
# Terminal 1: Start FastAPI backend
cd apps/backend
source .venv/bin/activate
PYTHONPATH=. python main.py

# Terminal 2: Start Tauri Desktop app
cd apps/desktop
npm run tauri dev
```

The application will launch. Top header displays live **LOCAL AI: Connected** (if Ollama is running) or **LOCAL AI: Unavailable** (if offline), allowing access to local Markdown notes, past conversation history, and memory items regardless of model availability.

---

## 🧪 Running Automated Tests

Run full backend pytest suite (testing database migrations, conversation ordering, markdown note CRUD, path traversal security, memory search, core memory, and Ollama fallback):

```bash
cd apps/backend
source .venv/bin/activate
PYTHONPATH=. pytest -v tests
```

Run frontend typecheck and production build:

```bash
cd apps/desktop
npm run check
npm run build
```

---

## 🔐 Security Principles

- **Localhost Binding**: FastAPI backend binds strictly to `127.0.0.1`.
- **Path Traversal Protection**: Markdown note filesystem operations validate target paths to ensure zero file access outside `data/notes/`.
- **Data Isolation**: Application code and private user data (`data/`) are completely separate. `data/` is gitignored by default.
- **SQL Parameterization**: Parameterized queries via SQLAlchemy prevent SQL injection.

---

## 📄 License

MIT License.
