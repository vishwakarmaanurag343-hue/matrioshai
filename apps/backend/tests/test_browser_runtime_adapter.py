import pytest
import pytest_asyncio
from app.browser.browser_runtime_adapter import (
    BrowserRuntime,
    ChromeRuntime,
    TauriWKWebViewRuntime,
    ObservationStatus,
    RuntimeType,
    UniversalObservationResult,
    RobustElement,
)


@pytest.mark.asyncio
async def test_chrome_runtime_disconnected():
    runtime = ChromeRuntime(bridge_manager=None)
    assert runtime.runtime_type == RuntimeType.CHROME_EXTENSION

    obs = await runtime.observe()
    assert obs.status == ObservationStatus.UNAVAILABLE
    assert obs.observation_failed is True
    assert "not connected" in obs.error_detail

    health = await runtime.health_check()
    assert health["connected"] is False
    assert health["status"] == "DISCONNECTED"


@pytest.mark.asyncio
async def test_tauri_runtime_disconnected():
    runtime = TauriWKWebViewRuntime(tauri_client=None)
    assert runtime.runtime_type == RuntimeType.TAURI_WKWEBVIEW

    obs = await runtime.observe()
    assert obs.status == ObservationStatus.UNAVAILABLE
    assert obs.observation_failed is True
    assert "not connected" in obs.error_detail

    health = await runtime.health_check()
    assert health["connected"] is False


@pytest.mark.asyncio
async def test_tauri_runtime_mock_observation():
    class MockTauriClient:
        async def invoke(self, cmd: str, args: dict):
            if cmd == "browser_get_semantic_page":
                return {
                    "url": "https://www.google.com",
                    "title": "Google",
                    "headings": ["Google"],
                    "text_blocks": ["Search the world's information"],
                    "observation_status": "SUCCESS",
                    "observation_failed": False,
                    "interactive_elements": [
                        {
                            "element_id": "el_0",
                            "role": "searchbox",
                            "name": "Search",
                            "accessible_name": "Search",
                            "tag": "input",
                            "visible": True,
                            "disabled": False,
                            "is_searchbox": True,
                        },
                        {
                            "element_id": "el_1",
                            "role": "button",
                            "name": "Google Search",
                            "accessible_name": "Google Search",
                            "tag": "button",
                            "visible": True,
                            "disabled": False,
                            "is_searchbox": False,
                        },
                    ],
                }
            elif cmd == "ai_browser_execute_action":
                return {"success": True, "message": "Action executed"}
            return {}

    runtime = TauriWKWebViewRuntime(tauri_client=MockTauriClient())
    obs = await runtime.observe("tab_1")

    assert obs.status == ObservationStatus.SUCCESS
    assert obs.observation_failed is False
    assert obs.url == "https://www.google.com"
    assert len(obs.interactive_elements) == 2
    assert obs.interactive_elements[0].role == "searchbox"
    assert obs.interactive_elements[0].name == "Search"
    assert obs.interactive_elements[1].role == "button"
    assert obs.interactive_elements[1].name == "Google Search"

    # Test Action
    act = await runtime.click("el_1", "tab_1")
    assert act.success is True
    assert act.action == "CLICK"
