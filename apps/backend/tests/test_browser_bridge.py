"""
Unit and Integration Tests for MATRIOSHAI Browser Communication Bridge (Phase 2)
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from main import app
from app.browser.bridge import (
    browser_bridge_server,
    ConnectionState,
    MessageType,
    BridgeAction,
    BridgeEnvelope,
    PROTOCOL_VERSION,
    PHASE_2_CAPABILITIES
)

client = TestClient(app)

def test_bridge_status_endpoint_disconnected():
    """Test bridge status when disconnected."""
    response = client.get("/api/v1/browser/bridge/status")
    assert response.status_code == 200
    data = response.json()
    assert data["protocol_version"] == PROTOCOL_VERSION
    assert "state" in data
    assert "capabilities" in data

def test_bridge_token_endpoint():
    """Test local authentication token retrieval."""
    response = client.get("/api/v1/browser/bridge/token")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "token" in data
    assert len(data["token"]) >= 32

def test_bridge_ping_when_disconnected():
    """Test ping returns 503 when no extension is connected."""
    response = client.post("/api/v1/browser/bridge/ping")
    assert response.status_code == 503
    assert "Bridge is not ready" in response.json()["detail"]

def test_bridge_envelope_serialization():
    """Test message envelope schema validation and serialization."""
    env = BridgeEnvelope(
        protocol_version=PROTOCOL_VERSION,
        message_id="msg_test123",
        type=MessageType.REQUEST,
        action=BridgeAction.HEALTH.value,
        payload={"query": "status"}
    )
    dumped = env.model_dump()
    assert dumped["protocol_version"] == "1.0"
    assert dumped["message_id"] == "msg_test123"
    assert dumped["type"] == "request"
    assert dumped["action"] == "bridge.health"
    assert dumped["payload"] == {"query": "status"}

def test_websocket_auth_handshake_and_ping():
    """Test full WebSocket connection, authentication, and bidirectional ping/pong."""
    token = browser_bridge_server.get_auth_token()

    with client.websocket_connect("/api/v1/browser/bridge/ws") as ws:
        # 1. Send auth request
        auth_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "auth_001",
            "type": "request",
            "action": BridgeAction.AUTH.value,
            "payload": {
                "token": token,
                "client_id": "test-chrome-extension",
                "version": "0.1.0",
                "capabilities": ["bridge.auth", "bridge.health", "bridge.info", "bridge.ping", "bridge.status"]
            }
        }
        ws.send_json(auth_req)

        # 2. Receive auth response
        auth_resp = ws.receive_json()
        assert auth_resp["success"] is True
        assert auth_resp["payload"]["authenticated"] is True
        assert auth_resp["payload"]["state"] == "READY"
        assert set(auth_resp["payload"]["capabilities"]) == PHASE_2_CAPABILITIES

        # 3. Verify status endpoint reflects READY
        status_res = client.get("/api/v1/browser/bridge/status")
        assert status_res.json()["state"] == "READY"
        assert status_res.json()["connected"] is True

        # 4. Extension sends bridge.ping to server
        ping_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "ping_001",
            "type": "request",
            "action": BridgeAction.PING.value,
            "payload": {}
        }
        ws.send_json(ping_req)

        # 5. Receive pong response from server
        ping_resp = ws.receive_json()
        assert ping_resp["success"] is True
        assert ping_resp["payload"]["pong"] is True

def test_websocket_invalid_auth_token():
    """Test rejection of invalid authentication token."""
    with client.websocket_connect("/api/v1/browser/bridge/ws") as ws:
        auth_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "auth_bad",
            "type": "request",
            "action": BridgeAction.AUTH.value,
            "payload": {
                "token": "invalid_wrong_token_12345",
                "client_id": "malicious-client",
                "version": "0.1.0"
            }
        }
        ws.send_json(auth_req)
        auth_resp = ws.receive_json()
        assert auth_resp["success"] is False
        assert auth_resp["error"]["code"] == "AUTH_FAILED"
