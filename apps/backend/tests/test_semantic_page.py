"""
Unit and Integration Tests for MATRIOSHAI Semantic Page & Accessibility Intelligence (Phase 5)
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from app.browser.manager import browser_manager
from app.browser.state_store import (
    browser_state_store,
    SemanticPageModel,
    SemanticElement,
    SemanticElementRef,
    SemanticQuery,
    BoundingBox,
    PageInfo,
    FormSemanticGroup,
    RadioSemanticGroup,
    RadioOption,
    TabSemanticGroup,
    TabOption,
    TableSemanticGroup,
    TableCell,
    ListSemanticGroup,
    SemanticHeading,
    SemanticLandmark,
    SemanticPageIndexes
)
from app.browser.bridge import (
    browser_bridge_server,
    BridgeAction,
    PROTOCOL_VERSION
)

client = TestClient(app)

def create_sample_semantic_model(tab_id: int = 101) -> SemanticPageModel:
    return SemanticPageModel(
        semantic_model_id="sem_test_flight_123",
        model_version=1,
        observation_id="obs_test_456",
        tab_id=tab_id,
        is_stale=False,
        page=PageInfo(url="https://flights.matrioshai.local", title="Flight Booking", language="en"),
        headings=[
            SemanticHeading(level=1, text="Flight Booking", element_id="h1_main"),
            SemanticHeading(level=2, text="Search Flights", element_id="h2_search")
        ],
        landmarks=[
            SemanticLandmark(role="banner", tag_name="header", label="Main Header", element_ids=[]),
            SemanticLandmark(role="main", tag_name="main", label=None, element_ids=["el_from", "el_to", "el_dep", "btn_search_main"])
        ],
        interactive_elements=[
            SemanticElement(
                element_id="el_from",
                role="textbox",
                name="From",
                tag_name="input",
                semantic_type="TEXT",
                source="label",
                confidence="HIGH",
                visible=True,
                enabled=True,
                focused=False,
                required=True,
                readonly=False,
                selected=False,
                checked=False,
                sensitive=False,
                value_available=True,
                value_preview="SFO",
                bounding_box=BoundingBox(x=10, y=50, width=120, height=36, top=50, left=10, right=130, bottom=86),
                attributes={"id": "input-from", "name": "from"}
            ),
            SemanticElement(
                element_id="el_dep",
                role="textbox",
                name="Departure",
                tag_name="input",
                semantic_type="DATE",
                source="label",
                confidence="HIGH",
                visible=True,
                enabled=True,
                focused=False,
                required=True,
                readonly=False,
                selected=False,
                checked=False,
                sensitive=False,
                value_available=True,
                value_preview="2026-09-01",
                bounding_box=BoundingBox(x=140, y=50, width=120, height=36, top=50, left=140, right=260, bottom=86),
                attributes={"id": "input-dep", "name": "depDate"}
            ),
            SemanticElement(
                element_id="el_pass",
                role="textbox",
                name="Password",
                tag_name="input",
                semantic_type="PASSWORD",
                source="label",
                confidence="HIGH",
                visible=True,
                enabled=True,
                focused=False,
                required=False,
                readonly=False,
                selected=False,
                checked=False,
                sensitive=True,
                value_available=False,
                value_preview=None,
                bounding_box=BoundingBox(x=10, y=100, width=120, height=36, top=100, left=10, right=130, bottom=136),
                attributes={"id": "input-pass", "name": "password"}
            ),
            # Duplicate buttons with same name to test ambiguity detection
            SemanticElement(
                element_id="btn_search_1",
                role="button",
                name="Search",
                tag_name="button",
                semantic_type="SUBMIT",
                source="native_html",
                confidence="HIGH",
                visible=True,
                enabled=True,
                focused=False,
                required=False,
                readonly=False,
                selected=False,
                checked=False,
                sensitive=False,
                value_available=False,
                bounding_box=BoundingBox(x=10, y=200, width=100, height=36, top=200, left=10, right=110, bottom=236),
                attributes={"id": "btn-search-1"}
            ),
            SemanticElement(
                element_id="btn_search_2",
                role="button",
                name="Search",
                tag_name="button",
                semantic_type="BUTTON",
                source="native_html",
                confidence="HIGH",
                visible=True,
                enabled=True,
                focused=False,
                required=False,
                readonly=False,
                selected=False,
                checked=False,
                sensitive=False,
                value_available=False,
                bounding_box=BoundingBox(x=120, y=200, width=100, height=36, top=200, left=120, right=220, bottom=236),
                attributes={"id": "btn-search-2"}
            )
        ],
        forms=[
            FormSemanticGroup(
                form_id="flight-form",
                name="Flight Search",
                field_ids=["el_from", "el_dep", "el_pass"],
                submit_button_ids=["btn_search_1"],
                required_field_ids=["el_from", "el_dep"]
            )
        ],
        radio_groups=[
            RadioSemanticGroup(
                group_name="cabinClass",
                label="Cabin class",
                selected_element_id="radio_eco",
                options=[
                    RadioOption(element_id="radio_eco", name="Economy", selected=True, disabled=False),
                    RadioOption(element_id="radio_biz", name="Business", selected=False, disabled=False)
                ]
            )
        ],
        tabs=[
            TabSemanticGroup(
                tab_list_id="main-tabs",
                tabs=[
                    TabOption(element_id="tab_flights", name="Flights", selected=True, controls_panel_id="panel_flights")
                ]
            )
        ],
        dialogs=[],
        tables=[],
        lists=[],
        indexes=SemanticPageIndexes(
            byRole={"textbox": ["el_from", "el_dep", "el_pass"], "button": ["btn_search_1", "btn_search_2"]},
            byName={"from": ["el_from"], "departure": ["el_dep"], "password": ["el_pass"], "search": ["btn_search_1", "btn_search_2"]},
            byLabel={"from": ["el_from"], "departure": ["el_dep"]},
            byId={"el_from": "el_from", "input-from": "el_from", "input-dep": "el_dep", "btn-search-1": "btn_search_1"},
            byTag={"input": ["el_from", "el_dep", "el_pass"], "button": ["btn_search_1", "btn_search_2"]},
            byType={"text": ["el_from"], "date": ["el_dep"], "password": ["el_pass"], "submit": ["btn_search_1"], "button": ["btn_search_2"]}
        ),
        debug_tree="PAGE: Flight Booking\n  FORMS: Flight Search (3 fields)",
        metadata={}
    )

def test_semantic_page_model_schema_and_caching():
    """Test SemanticPageModel serialization, schema validation, and state store caching."""
    store = browser_state_store
    store.reset()

    model = create_sample_semantic_model(101)
    data = model.model_dump()

    assert data["semantic_model_id"] == "sem_test_flight_123"
    assert data["model_version"] == 1
    assert len(data["interactive_elements"]) == 5
    assert len(data["forms"]) == 1

    # Store and retrieve
    store.store_semantic_model(model)
    cached = store.get_semantic_model(101)
    assert cached is not None
    assert cached.semantic_model_id == "sem_test_flight_123"
    assert len(cached.forms[0].required_field_ids) == 2

    # Invalidate
    store.invalidate_semantic_model(101)
    assert store.get_semantic_model(101).is_stale is True

def test_local_semantic_queries_and_ambiguity():
    """Test local semantic query execution, unique match, and ambiguity handling."""
    model = create_sample_semantic_model(101)

    # 1. Unique match: label "Departure" -> FOUND
    res_dep = browser_manager._local_query(model, {"label": "Departure"})
    assert res_dep.status == "FOUND"
    assert res_dep.element is not None
    assert res_dep.element.name == "Departure"
    assert res_dep.element.semantic_type == "DATE"

    # 2. Ambiguous match: role="button", name="Search" -> AMBIGUOUS (2 matches)
    res_btn = browser_manager._local_query(model, {"role": "button", "name": "Search"})
    assert res_btn.status == "AMBIGUOUS"
    assert len(res_btn.matches) == 2
    assert res_btn.element is None  # Crucial: Never arbitrarily pick one

    # 3. Not found
    res_none = browser_manager._local_query(model, {"name": "NonExistentField"})
    assert res_none.status == "NOT_FOUND"

def test_sensitive_data_protection():
    """Verify passwords have sensitive=True and value_available=False."""
    model = create_sample_semantic_model(101)
    pass_el = next(el for el in model.interactive_elements if el.element_id == "el_pass")
    assert pass_el.sensitive is True
    assert pass_el.value_available is False
    assert pass_el.value_preview is None

def test_semantic_rest_endpoints():
    """Test REST endpoints for semantic page models and queries."""
    store = browser_state_store
    model = create_sample_semantic_model(303)
    store.store_semantic_model(model)

    # 1. GET /control/tabs/303/semantic-page
    res = client.get("/api/v1/browser/control/tabs/303/semantic-page")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["semantic_model"]["semantic_model_id"] == "sem_test_flight_123"

    # 2. POST /control/tabs/303/semantic-query (Unique query)
    res_q = client.post("/api/v1/browser/control/tabs/303/semantic-query", json={"query": {"label": "Departure"}})
    assert res_q.status_code == 200
    q_data = res_q.json()
    assert q_data["status"] == "ok"
    assert q_data["result"]["status"] == "FOUND"

    # 3. POST /control/tabs/303/semantic-query (Duplicate button -> AMBIGUOUS)
    res_dup = client.post("/api/v1/browser/control/tabs/303/semantic-query", json={"query": {"role": "button", "name": "Search"}})
    assert res_dup.status_code == 200
    dup_data = res_dup.json()
    assert dup_data["result"]["status"] == "AMBIGUOUS"
    assert len(dup_data["result"]["matches"]) == 2

    # 4. POST /control/tabs/303/invalidate-semantic
    res_inv = client.post("/api/v1/browser/control/tabs/303/invalidate-semantic")
    assert res_inv.status_code == 200
    assert res_inv.json()["invalidated"] is True
    assert store.get_semantic_model(303).is_stale is True

def test_websocket_phase5_capabilities_handshake():
    """Test WebSocket auth with Phase 5 capabilities."""
    token = browser_bridge_server.get_auth_token()

    with client.websocket_connect("/api/v1/browser/bridge/ws") as ws:
        auth_req = {
            "protocol_version": PROTOCOL_VERSION,
            "message_id": "auth_phase5",
            "type": "request",
            "action": BridgeAction.AUTH.value,
            "payload": {
                "token": token,
                "client_id": "matrioshai-chrome-extension",
                "version": "0.1.0",
                "browser_id": "chrome_phase5_instance",
                "capabilities": [
                    "bridge.auth", "bridge.health", "bridge.info", "bridge.ping", "bridge.status",
                    "browser.getStatus", "browser.getWindows", "browser.getTabs", "browser.getActiveTab",
                    "browser.openTab", "browser.closeTab", "browser.switchTab", "browser.navigate",
                    "browser.reload", "browser.goBack", "browser.goForward", "browser.waitForNavigation",
                    "browser.refreshState", "page.observe", "page.semanticObserve", "page.semanticQuery",
                    "page.resolveElement", "page.getSemanticModel", "page.invalidateSemanticModel"
                ]
            }
        }
        ws.send_json(auth_req)
        auth_resp = ws.receive_json()
        assert auth_resp["success"] is True
        assert auth_resp["payload"]["authenticated"] is True
        assert "page.semanticObserve" in auth_resp["payload"]["capabilities"]
        assert "page.semanticQuery" in auth_resp["payload"]["capabilities"]
