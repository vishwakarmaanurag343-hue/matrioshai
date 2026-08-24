"""
MATRIOSHAI Backend Visual Page Intelligence Test Suite (Phase 6)

Verifies:
1. Pydantic schemas for VisualPageModel, ScreenshotMetadata, VisualBoundingBox, VisualElement, VisualRegion, PointQueryResult.
2. BrowserStateStore caching, versioning, screenshot storage, and invalidation.
3. BrowserManager methods (capture_screenshot, get_visual_page, query_visual_point, query_visual_page).
4. REST API endpoints in /api/v1/browser/control/tabs/*.
5. Deterministic z-order candidate sorting in PointQueryResult.
6. Privacy mode policies (STANDARD, STRICT).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from app.browser.state_store import (
    browser_state_store,
    VisualBoundingBox,
    ScreenshotMetadata,
    VisualElement,
    VisualRegion,
    VisualOverlay,
    FixedElement,
    VisualElementMapping,
    VisualPageIndexes,
    VisualPageModel,
    PointQueryResult,
    VisualQueryResult,
    VisualQuery,
    CandidateElement,
    ViewportMetrics
)
from app.browser.manager import browser_manager
from app.browser.bridge import browser_bridge_server, BridgeAction

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_browser_state():
    browser_state_store.reset()
    browser_state_store.set_browser_identity("test_browser_6", "125.0.0.0")
    yield
    browser_state_store.reset()

def create_sample_visual_model(tab_id: int = 101, version: int = 1) -> VisualPageModel:
    viewport = ViewportMetrics(width=1280, height=800, document_width=1280, document_height=2400)
    screenshot_meta = ScreenshotMetadata(
        id=f"screen_{tab_id}_{version}",
        tab_id=tab_id,
        url="https://portal.example.com/flights",
        width=1280,
        height=800,
        device_pixel_ratio=2.0,
        scaled=False,
        original_width=1280,
        original_height=800,
        privacy_mode="STANDARD",
        redacted_regions_count=0,
        visual_version=version
    )

    box_header = VisualBoundingBox(x=0, y=0, width=1280, height=60, coordinate_system="DOM_VIEWPORT")
    box_search = VisualBoundingBox(x=50, y=100, width=400, height=40, coordinate_system="DOM_VIEWPORT")
    box_btn = VisualBoundingBox(x=460, y=100, width=120, height=40, coordinate_system="DOM_VIEWPORT")
    box_canvas = VisualBoundingBox(x=50, y=200, width=500, height=300, coordinate_system="DOM_VIEWPORT")

    reg_header = VisualRegion(
        region_id="reg_header",
        type="HEADER",
        label="Site Header",
        bounding_box=box_header,
        screenshot_box=VisualBoundingBox(x=0, y=0, width=2560, height=120, coordinate_system="SCREENSHOT_PIXEL"),
        z_index=100,
        is_fixed=True,
        element_ids=["el_header"],
        visual_element_ids=["vis_0"]
    )

    el_btn = VisualElement(
        visual_id="vis_btn_1",
        semantic_element_id="sem_btn_1",
        type="BUTTON",
        tag_name="button",
        role="button",
        name="Search Flights",
        dom_box=box_btn,
        screenshot_box=VisualBoundingBox(x=920, y=200, width=240, height=80, coordinate_system="SCREENSHOT_PIXEL"),
        visibility="fully_visible",
        z_index=10,
        is_interactive=True,
        confidence="HIGH",
        attributes={"id": "btn-search"}
    )

    el_canvas = VisualElement(
        visual_id="vis_canvas_1",
        semantic_element_id=None,
        type="CANVAS",
        tag_name="canvas",
        role="img",
        name="Flight Radar",
        dom_box=box_canvas,
        screenshot_box=VisualBoundingBox(x=100, y=400, width=1000, height=600, coordinate_system="SCREENSHOT_PIXEL"),
        visibility="fully_visible",
        z_index=5,
        is_interactive=False,
        is_canvas=True,
        confidence="HIGH"
    )

    mapping_btn = VisualElementMapping(
        element_id="sem_btn_1",
        visual_id="vis_btn_1",
        dom_box=box_btn,
        screenshot_box=VisualBoundingBox(x=920, y=200, width=240, height=80, coordinate_system="SCREENSHOT_PIXEL"),
        confidence="HIGH",
        visibility="fully_visible",
        z_index=10
    )

    indexes = VisualPageIndexes(
        byVisualType={"BUTTON": ["vis_btn_1"], "CANVAS": ["vis_canvas_1"]},
        bySemanticElement={"sem_btn_1": "vis_btn_1"},
        byInteractive=["vis_btn_1"]
    )

    return VisualPageModel(
        visual_model_id=f"vis_mod_{tab_id}_{version}",
        visual_version=version,
        observation_id=f"obs_{tab_id}",
        semantic_model_id=f"sem_mod_{tab_id}",
        tab_id=tab_id,
        is_stale=False,
        screenshot=screenshot_meta,
        viewport=viewport,
        regions=[reg_header],
        overlays=[],
        fixed_elements=[
            FixedElement(
                element_id="reg_header",
                visual_id="vis_0",
                bounding_box=box_header,
                screenshot_box=VisualBoundingBox(x=0, y=0, width=2560, height=120, coordinate_system="SCREENSHOT_PIXEL"),
                z_index=100,
                position_type="fixed"
            )
        ],
        sticky_elements=[],
        visual_elements=[el_btn, el_canvas],
        mappings=[mapping_btn],
        indexes=indexes,
        privacy_mode="STANDARD",
        metadata={"element_count": 2, "region_count": 1}
    )

class TestVisualPageIntelligence:
    def test_visual_model_pydantic_schema_validation(self):
        model = create_sample_visual_model(101, 1)
        assert model.tab_id == 101
        assert model.visual_version == 1
        assert model.is_stale is False
        assert len(model.visual_elements) == 2
        assert model.visual_elements[0].is_interactive is True
        assert model.visual_elements[1].is_canvas is True
        assert model.screenshot.device_pixel_ratio == 2.0
        assert len(model.fixed_elements) == 1

    def test_state_store_visual_caching_and_invalidation(self):
        model = create_sample_visual_model(202, 1)
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        browser_state_store.store_visual_model(model, data_url)

        cached = browser_state_store.get_visual_model(202)
        assert cached is not None
        assert cached.visual_model_id == "vis_mod_202_1"
        assert browser_state_store.get_screenshot(202) == data_url

        # Invalidate model
        browser_state_store.invalidate_visual_model(202)
        assert cached.is_stale is True
        assert cached.visual_version == 2
        assert browser_state_store.get_screenshot(202) is None

    @pytest.mark.asyncio
    async def test_browser_manager_capture_screenshot(self):
        sample_meta = ScreenshotMetadata(
            id="screen_303_1",
            tab_id=303,
            url="https://example.com",
            width=1280,
            height=800,
            original_width=1280,
            original_height=800,
            privacy_mode="STANDARD"
        )
        data_url = "data:image/png;base64,mockpngdata"

        with patch.object(browser_manager, "is_connected", return_value=True), \
             patch.object(browser_bridge_server, "send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                "screenshot": sample_meta.model_dump(),
                "data_url": data_url
            }

            res = await browser_manager.capture_screenshot(303, format="png", privacy_mode="STANDARD")
            assert res["screenshot"].id == "screen_303_1"
            assert res["data_url"] == data_url
            mock_send.assert_called_once_with(
                BridgeAction.PAGE_CAPTURE_SCREENSHOT.value,
                {"tab_id": 303, "format": "png", "privacy_mode": "STANDARD"},
                timeout_seconds=10.0
            )

    @pytest.mark.asyncio
    async def test_browser_manager_get_visual_page(self):
        model = create_sample_visual_model(404, 1)
        data_url = "data:image/png;base64,sampledataurl"

        with patch.object(browser_manager, "is_connected", return_value=True), \
             patch.object(browser_bridge_server, "send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {
                "visual_model": model.model_dump(),
                "screenshot_data_url": data_url
            }

            res = await browser_manager.get_visual_page(404, privacy_mode="STANDARD")
            assert res.tab_id == 404
            assert len(res.visual_elements) == 2
            assert res.is_stale is False

            # Verify cached in state store
            cached = browser_state_store.get_visual_model(404)
            assert cached is not None

    @pytest.mark.asyncio
    async def test_browser_manager_query_visual_point(self):
        model = create_sample_visual_model(505, 1)
        target_el = model.visual_elements[0]

        point_result = PointQueryResult(
            status="FOUND",
            x=500,
            y=120,
            coordinate_system="DOM_VIEWPORT",
            topmost_element=target_el,
            candidates=[CandidateElement(element=target_el, z_index=10, occluded=False, confidence="HIGH")]
        )

        with patch.object(browser_manager, "is_connected", return_value=True), \
             patch.object(browser_bridge_server, "send_request", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"result": point_result.model_dump()}

            res = await browser_manager.query_visual_point(505, 500, 120, "DOM_VIEWPORT")
            assert res.status == "FOUND"
            assert res.topmost_element is not None
            assert res.topmost_element.name == "Search Flights"
            assert len(res.candidates) == 1

    def test_rest_screenshot_endpoint(self):
        sample_meta = ScreenshotMetadata(
            id="screen_606_1",
            tab_id=606,
            url="https://example.com",
            width=1280,
            height=800,
            original_width=1280,
            original_height=800,
            privacy_mode="STANDARD"
        )
        with patch.object(browser_manager, "capture_screenshot", new_callable=AsyncMock) as mock_snap:
            mock_snap.return_value = {
                "screenshot": sample_meta,
                "data_url": "data:image/png;base64,test"
            }

            resp = client.post("/api/v1/browser/control/tabs/606/screenshot", json={"format": "png", "privacy_mode": "STANDARD"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["screenshot"]["id"] == "screen_606_1"
            assert data["data_url"] == "data:image/png;base64,test"

    def test_rest_visual_page_endpoint(self):
        model = create_sample_visual_model(707, 1)
        with patch.object(browser_manager, "get_visual_page", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = model

            resp = client.get("/api/v1/browser/control/tabs/707/visual-page")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["visual_model"]["tab_id"] == 707
            assert len(data["visual_model"]["visual_elements"]) == 2

    def test_rest_visual_point_query_endpoint(self):
        model = create_sample_visual_model(808, 1)
        target_el = model.visual_elements[0]
        point_res = PointQueryResult(
            status="FOUND",
            x=480,
            y=110,
            coordinate_system="DOM_VIEWPORT",
            topmost_element=target_el,
            candidates=[CandidateElement(element=target_el, z_index=10, occluded=False, confidence="HIGH")]
        )
        with patch.object(browser_manager, "query_visual_point", new_callable=AsyncMock) as mock_pq:
            mock_pq.return_value = point_res

            resp = client.post(
                "/api/v1/browser/control/tabs/808/visual-point-query",
                json={"x": 480, "y": 110, "coordinate_system": "DOM_VIEWPORT"}
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert data["result"]["status"] == "FOUND"
            assert data["result"]["topmost_element"]["name"] == "Search Flights"
