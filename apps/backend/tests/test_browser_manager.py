"""
Unit and Integration Tests for MATRIOSHAI Browser Manager and Control Layer (Phase 3)
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.browser.manager import browser_manager
from app.browser.state_store import (
    browser_state_store,
    WindowState,
    TabState,
    TabStatus,
    NavigationStatus
)
from app.browser.bridge import (
    browser_bridge_server,
    BridgeAction,
    PROTOCOL_VERSION
)

client = TestClient(app)

def test_url_validation():
    """Test strict URL validation and normalization."""
    # Valid URLs
    ok, norm, err = browser_manager.validate_url("https://example.com")
    assert ok is True
    assert norm == "https://example.com"

    ok, norm, err = browser_manager.validate_url("http://localhost:8765/test")
    assert ok is True
    assert norm == "http://localhost:8765/test"

    ok, norm, err = browser_manager.validate_url("example.com/search?q=rust")
    assert ok is True
    assert norm == "https://example.com/search?q=rust"

    # Dangerous / rejected schemes
    ok, norm, err = browser_manager.validate_url("javascript:alert(1)")
    assert ok is False
    assert "Dangerous" in err

    ok, norm, err = browser_manager.validate_url("data:text/html,<h1>Test</h1>")
    assert ok is False

    ok, norm, err = browser_manager.validate_url("file:///etc/passwd")
    assert ok is False

    ok, norm, err = browser_manager.validate_url("vbscript:test")
    assert ok is False

    # Empty
    ok, norm, err = browser_manager.validate_url("")
    assert ok is False

def test_state_store_events_and_reconciliation():
    """Test state store event application and state reconciliation."""
    store = browser_state_store
    store.reset()

    # 1. Tab created event
    store.apply_tab_created({
        "tab_id": 101,
        "window_id": 1,
        "index": 0,
        "active": True,
        "url": "https://matrioshai.local",
        "title": "Home",
        "status": "READY"
    })

    assert store.tabs[101].url == "https://matrioshai.local"
    assert store.active_tab_id == 101

    # 2. Tab updated event
    store.apply_tab_updated({
        "tab_id": 101,
        "window_id": 1,
        "index": 0,
        "active": True,
        "url": "https://example.com",
        "title": "Example Domain",
        "status": "READY"
    })
    assert store.tabs[101].url == "https://example.com"
    assert store.tabs[101].title == "Example Domain"

    # 3. Add second tab and switch active
    store.apply_tab_created({
        "tab_id": 102,
        "window_id": 1,
        "index": 1,
        "active": False,
        "url": "https://docs.matrioshai.local",
        "title": "Docs",
        "status": "READY"
    })
    assert len(store.tabs) == 2
    assert store.active_tab_id == 101

    store.apply_tab_activated(102, 1)
    assert store.active_tab_id == 102
    assert store.tabs[102].active is True
    assert store.tabs[101].active is False

    # 4. Remove tab
    store.apply_tab_removed(101, 1)
    assert 101 not in store.tabs
    assert len(store.tabs) == 1

    # 5. Deterministic Reconciliation
    windows_data = [{"window_id": 1, "type": "normal", "focused": True, "state": "normal", "tab_ids": [201, 202], "active_tab_id": 202}]
    tabs_data = [
        {"tab_id": 201, "window_id": 1, "index": 0, "active": False, "url": "https://alpha.com", "title": "Alpha", "status": "READY"},
        {"tab_id": 202, "window_id": 1, "index": 1, "active": True, "url": "https://beta.com", "title": "Beta", "status": "READY"}
    ]
    store.reconcile_state(windows_data, tabs_data)
    assert len(store.tabs) == 2
    assert 102 not in store.tabs  # Stale tab removed
    assert store.active_tab_id == 202
    assert store.tabs[202].url == "https://beta.com"

def test_audit_logging():
    """Test audit log creation and retrieval."""
    store = browser_state_store
    store.record_audit_log("act_001", "browser.navigate", 101, "https://example.com", "success")
    store.record_audit_log("act_002", "browser.navigate", 101, "javascript:bad", "failed", "Invalid URL")

    logs = store.get_audit_logs(10)
    assert len(logs) >= 2
    assert logs[-2].type == "browser.navigate"
    assert logs[-2].result == "success"
    assert logs[-1].result == "failed"
    assert logs[-1].error == "Invalid URL"

def test_control_rest_endpoints():
    """Test REST control endpoints status and validation."""
    # Control status
    res = client.get("/api/v1/browser/control/status")
    assert res.status_code == 200
    data = res.json()
    assert "browser_layer_ready" in data
    assert "bridge" in data
    assert "browser" in data

    # Invalid URL on open tab
    res = client.post("/api/v1/browser/control/tabs", json={"url": "javascript:alert(1)"})
    assert res.status_code == 400
    assert "Dangerous" in res.json()["detail"]

    # Audit logs endpoint
    res = client.get("/api/v1/browser/control/audit-logs")
    assert res.status_code == 200
    assert "audit_logs" in res.json()

def test_websocket_browser_control_and_events():
    """Test WebSocket browser control requests and real-time event streaming."""
    token = browser_bridge_server.get_auth_token()

    with client.websocket_connect("/api/v1/browser/bridge/ws") as ws:
        # 1. Authenticate with Phase 3 capabilities
        auth_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "auth_phase3",
            "type": "request",
            "action": BridgeAction.AUTH.value,
            "payload": {
                "token": token,
                "client_id": "matrioshai-chrome-extension",
                "version": "0.1.0",
                "browser_id": "chrome_test_instance_123",
                "capabilities": [
                    "bridge.auth", "bridge.health", "bridge.info", "bridge.ping", "bridge.status",
                    "browser.getStatus", "browser.getWindows", "browser.getTabs", "browser.getActiveTab",
                    "browser.openTab", "browser.closeTab", "browser.switchTab", "browser.navigate",
                    "browser.reload", "browser.goBack", "browser.goForward", "browser.waitForNavigation",
                    "browser.refreshState"
                ]
            }
        }
        ws.send_json(auth_req)
        auth_resp = ws.receive_json()
        assert auth_resp["success"] is True
        assert auth_resp["payload"]["authenticated"] is True
        assert "browser.navigate" in auth_resp["payload"]["capabilities"]

        # 2. Extension streams a tab.created event to backend
        evt = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "evt_001",
            "type": "event",
            "action": BridgeAction.TAB_CREATED.value,
            "payload": {
                "tab": {
                    "tab_id": 555,
                    "window_id": 1,
                    "index": 0,
                    "active": True,
                    "url": "https://testpage.local",
                    "title": "Test Page",
                    "status": "READY"
                }
            }
        }
        ws.send_json(evt)

        # 3. Synchronize via ping/pong
        ping_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "ping_sync",
            "type": "request",
            "action": BridgeAction.PING.value,
            "payload": {}
        }
        ws.send_json(ping_req)
        ping_resp = ws.receive_json()
        assert ping_resp["success"] is True

        # State store should now have tab 555
        tab = browser_state_store.get_tab(555)
        assert tab is not None
        assert tab.url == "https://testpage.local"
        assert browser_state_store.active_tab_id == 555
