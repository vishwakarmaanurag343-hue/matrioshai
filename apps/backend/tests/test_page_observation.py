"""
Unit and Integration Tests for MATRIOSHAI Page Observation Engine (Phase 4)
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.browser.manager import browser_manager
from app.browser.state_store import (
    browser_state_store,
    PageObservation,
    ViewportMetrics,
    BoundingBox,
    InteractiveElement,
    HeadingElement,
    LandmarkElement,
    FrameElement
)
from app.browser.bridge import (
    browser_bridge_server,
    BridgeAction,
    PROTOCOL_VERSION
)

client = TestClient(app)

def test_page_observation_model_and_caching():
    """Test PageObservation Pydantic model serialization, validation, and state caching."""
    store = browser_state_store
    store.reset()

    obs = PageObservation(
        observation_id="obs_test_123",
        tab_id=101,
        url="http://localhost:8765/test_page.html",
        title="Test Page",
        document_state="complete",
        viewport=ViewportMetrics(
            width=1280,
            height=800,
            scroll_x=0,
            scroll_y=0,
            document_width=1280,
            document_height=800
        ),
        visible_text=[
            "Test Page",
            "The verification code for this test is XQ-4471-ZETA."
        ],
        headings=[
            HeadingElement(level=1, text="Test Page", id="heading-1")
        ],
        landmarks=[
            LandmarkElement(role="main", tag_name="main", label="Main Content")
        ],
        interactive_elements=[
            InteractiveElement(
                element_id="el_0",
                tag_name="button",
                role="button",
                text="Submit Code",
                bounding_box=BoundingBox(x=10, y=50, width=120, height=36, top=50, left=10, right=130, bottom=86),
                is_visible=True,
                is_in_viewport=True,
                is_enabled=True,
                attributes={"id": "btn-submit"}
            ),
            InteractiveElement(
                element_id="el_1",
                tag_name="a",
                role="link",
                text="Documentation",
                href="https://docs.matrioshai.local",
                bounding_box=BoundingBox(x=140, y=50, width=100, height=36, top=50, left=140, right=240, bottom=86),
                is_visible=True,
                is_in_viewport=True,
                is_enabled=True,
                attributes={"id": "link-docs"}
            )
        ],
        frames=[]
    )

    # 1. Test model dict conversion
    data = obs.model_dump()
    assert data["observation_id"] == "obs_test_123"
    assert data["tab_id"] == 101
    assert len(data["visible_text"]) == 2
    assert "XQ-4471-ZETA" in data["visible_text"][1]
    assert len(data["interactive_elements"]) == 2
    assert data["interactive_elements"][0]["role"] == "button"

    # 2. Test state store caching
    store.store_observation(obs)
    cached = store.get_observation(101)
    assert cached is not None
    assert cached.observation_id == "obs_test_123"
    assert cached.title == "Test Page"
    assert len(cached.interactive_elements) == 2

    # 3. Test summary includes cached observations
    summary = store.get_summary()
    assert summary["cached_observations_count"] == 1

def test_page_observation_audit_and_rest_endpoint():
    """Test observation retrieval via REST endpoint when cached."""
    store = browser_state_store
    obs = PageObservation(
        observation_id="obs_rest_456",
        tab_id=202,
        url="https://en.wikipedia.org/wiki/Python_(programming_language)",
        title="Python (programming language) - Wikipedia",
        document_state="complete",
        viewport=ViewportMetrics(width=1440, height=900, scroll_x=0, scroll_y=200, document_width=1440, document_height=5000),
        visible_text=["Python was conceived in the late 1980s by Guido van Rossum."],
        headings=[HeadingElement(level=1, text="Python (programming language)")],
        landmarks=[],
        interactive_elements=[],
        frames=[]
    )
    store.store_observation(obs)

    # Calling observe tab endpoint when bridge is disconnected returns cached observation
    res = client.get("/api/v1/browser/control/tabs/202/observe")
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["status"] == "ok"
    assert res_data["observation"]["tab_id"] == 202
    assert "Guido van Rossum" in res_data["observation"]["visible_text"][0]

def test_websocket_page_observe_handshake_and_flow():
    """Test WebSocket handshake with Phase 4 capabilities and page.observe message correlation."""
    token = browser_bridge_server.get_auth_token()

    with client.websocket_connect("/api/v1/browser/bridge/ws") as ws:
        # 1. Authenticate with Phase 4 capabilities
        auth_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "auth_phase4",
            "type": "request",
            "action": BridgeAction.AUTH.value,
            "payload": {
                "token": token,
                "client_id": "matrioshai-chrome-extension",
                "version": "0.1.0",
                "browser_id": "chrome_phase4_instance",
                "capabilities": [
                    "bridge.auth", "bridge.health", "bridge.info", "bridge.ping", "bridge.status",
                    "browser.getStatus", "browser.getWindows", "browser.getTabs", "browser.getActiveTab",
                    "browser.openTab", "browser.closeTab", "browser.switchTab", "browser.navigate",
                    "browser.reload", "browser.goBack", "browser.goForward", "browser.waitForNavigation",
                    "browser.refreshState", "page.observe"
                ]
            }
        }
        ws.send_json(auth_req)
        auth_resp = ws.receive_json()
        assert auth_resp["success"] is True
        assert auth_resp["payload"]["authenticated"] is True
        assert "page.observe" in auth_resp["payload"]["capabilities"]
