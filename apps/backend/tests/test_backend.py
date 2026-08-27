import pytest
from app.services.conversation_service import ConversationService
from app.services.notes_service import NotesService
from app.memory.memory_service import MemoryService
from app.llm.ollama import OllamaProvider

def test_health_and_status_endpoints(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_status = client.get("/api/v1/status")
    assert res_status.status_code == 200
    body = res_status.json()
    assert body["backend"]["status"] == "Connected"
    assert body["database"]["status"] == "Connected"

def test_conversation_and_messages_persistence(test_db, client):
    conv_res = client.post("/api/v1/conversations", json={"title": "Test Architecture"})
    assert conv_res.status_code == 201
    conv_id = conv_res.json()["id"]

    msg_res = client.post(f"/api/v1/conversations/{conv_id}/messages", json={
        "role": "user",
        "content": "What is MATRIOSHAI?"
    })
    assert msg_res.status_code == 201
    assert msg_res.json()["content"] == "What is MATRIOSHAI?"

    get_res = client.get(f"/api/v1/conversations/{conv_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()["messages"]) == 1

def test_notes_crud_and_path_traversal_protection(test_db, client):
    # 1. Create note
    create_res = client.post("/api/v1/notes", json={
        "title": "Architecture Principles",
        "content": "# Local-First Rules\n1. User privacy first.\n2. Modular architecture.",
        "tags": ["arch", "local-first"]
    })
    assert create_res.status_code == 201
    note_data = create_res.json()
    note_id = note_data["id"]
    assert note_data["title"] == "Architecture Principles"
    assert "local-first" in note_data["tags"]

    # 2. Read note
    get_res = client.get(f"/api/v1/notes/{note_id}")
    assert get_res.status_code == 200
    assert "User privacy first" in get_res.json()["content"]

    # 3. Update note
    update_res = client.patch(f"/api/v1/notes/{note_id}", json={
        "title": "Updated Architecture",
        "content": "# Updated Content"
    })
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Architecture"

    # 4. Path traversal protection test in NotesService
    notes_service = NotesService(test_db)
    with pytest.raises(ValueError, match="Security error"):
        notes_service._validate_safe_path("../../etc/passwd")

    # 5. Delete note
    del_res = client.delete(f"/api/v1/notes/{note_id}")
    assert del_res.status_code == 204

def test_memory_service_and_core_memory(test_db, client):
    mem_service = MemoryService(test_db)

    # Core memory set
    core_res = client.post("/api/v1/memory/core", json={
        "user_preferences": "Dark mode enabled, concise answers",
        "active_goals": "Build MATRIOSHAI Phase 1 Core"
    })
    assert core_res.status_code == 200
    assert len(core_res.json()) == 2

    # Add Recall memory
    rec = mem_service.add_memory(
        content="Decided to use SQLite for Phase 1 local persistence",
        memory_tier="RECALL",
        source_type="decision"
    )
    assert rec.memory_tier == "RECALL"

    # Search memory
    search_res = client.post("/api/v1/memory/search", json={"query": "SQLite persistence"})
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1
    assert search_res.json()[0]["content"] == "Decided to use SQLite for Phase 1 local persistence"

@pytest.mark.asyncio
async def test_ollama_fallback_when_offline():
    # Test Ollama provider with a non-existent port
    provider = OllamaProvider(base_url="http://127.0.0.1:59999", default_model="qwen3:3b")
    health_info = await provider.health()
    assert health_info["connected"] is False
    assert "Unable to connect" in health_info["details"]

def test_openapi_generation_and_agent_routes(client):
    """
    Phase 1.5 & Phase 2D Regression Test: Ensure /openapi.json generates HTTP 200 without schema errors,
    canonical agent routes and live control infrastructure are represented, and dead backend agent task routes are cleanly retired.
    """
    res = client.get("/openapi.json")
    assert res.status_code == 200
    data = res.json()
    assert data.get("info", {}).get("title") == "MATRIOSHAI Core"
    paths = data.get("paths", {})
    assert "/api/v1/browser/agent/next-step" in paths
    assert "/api/v1/browser/agent/metrics" in paths
    assert "/api/v1/browser/agent/metrics/start" in paths
    assert "/api/v1/health" in paths
    assert "/api/v1/browser/control/tabs" in paths
    assert "/api/v1/browser/control/audit-logs" in paths
    assert "/api/v1/browser/security/state" in paths
    assert "/api/v1/browser/transactions" in paths

    # Phase 2D: Verify dead /agent/tasks route is cleanly retired from OpenAPI schema
    assert "/api/v1/browser/agent/tasks" not in paths
    assert "/api/v1/browser/agent/tasks/{task_id}/start" not in paths



