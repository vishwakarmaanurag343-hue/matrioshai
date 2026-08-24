import pytest
from app.memory.models import MemoryRecord, MemoryType, MemoryStatus
from app.memory.extraction import memory_extraction_service
from app.memory.consolidation import memory_consolidation_service
from app.knowledge.models import EntityType, RelationshipType
from app.knowledge.service import knowledge_graph_service
from app.proactive.models import ProactiveSignalType, ProactivePriority
from app.proactive.service import proactive_service

def test_memory_extraction_and_candidate_detection():
    # User statement that implies a project fact
    text = "We are building MATRIOSHAI as a Mac-first AI operating layer."
    candidates = memory_extraction_service.extract_candidates(text, source="chat")
    assert len(candidates) >= 1
    cand = candidates[0]
    assert cand.proposed_type == MemoryType.SEMANTIC
    assert "MATRIOSHAI" in cand.content

def test_memory_secret_redaction_during_extraction():
    text_with_secret = "I prefer using this API_KEY: secret_live_token_777888 for testing."
    candidates = memory_extraction_service.extract_candidates(text_with_secret, source="chat")
    for c in candidates:
        assert "secret_live_token_777888" not in c.content

def test_memory_contradiction_detection():
    existing = [
        MemoryRecord(
            id="mem_1",
            memory_type=MemoryType.SEMANTIC,
            status=MemoryStatus.ACTIVE,
            content="Project will launch in September."
        )
    ]
    # Contradicting statement
    new_text = "Project will launch in November."
    contradictions = memory_consolidation_service.detect_contradictions(new_text, existing)
    assert len(contradictions) >= 1
    assert contradictions[0].existing_memory.id == "mem_1"

def test_superseded_memory_provenance():
    old_mem = MemoryRecord(
        id="mem_old",
        memory_type=MemoryType.SEMANTIC,
        status=MemoryStatus.ACTIVE,
        content="Initial design uses Electron"
    )
    superseded = memory_consolidation_service.supersede_memory(old_mem, new_memory_id="mem_new_tauri")
    assert superseded.status == MemoryStatus.SUPERSEDED
    assert superseded.superseded_by == "mem_new_tauri"

def test_knowledge_graph_entities_and_relationships():
    # Add entity
    ent_qwen = knowledge_graph_service.add_entity("Qwen 2.5", EntityType.TECHNOLOGY, canonical_name="Qwen")
    assert ent_qwen.id is not None
    assert ent_qwen.canonical_name == "Qwen"

    # Add relationship
    rel = knowledge_graph_service.add_relationship("MATRIOSHAI", "Qwen", RelationshipType.USES)
    assert rel is not None
    assert rel.relationship_type == RelationshipType.USES

    # Search graph
    results = knowledge_graph_service.search_entities("Qwen")
    assert len(results) >= 1

def test_proactive_suggestions_and_dismissal():
    suggestions = proactive_service.get_active_suggestions()
    assert len(suggestions) >= 1

    # Verify explainable fields
    sug = suggestions[0]
    assert sug.reason is not None
    assert sug.evidence is not None
    assert sug.suggested_action is not None

    # Test dismissal
    target_id = sug.id
    ok = proactive_service.dismiss_suggestion(target_id)
    assert ok is True

    # Confirm dismissed is omitted from active list
    remaining_ids = [s.id for s in proactive_service.get_active_suggestions()]
    assert target_id not in remaining_ids
