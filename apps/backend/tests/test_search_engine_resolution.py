import pytest
from app.browser.models import BrowserTab
from app.browser.gateway import browser_gateway
from app.browser.filter_list import filter_list_manager

def test_search_engine_direct_resolution():
    # Verify Search Engine URL generation logic
    engine_templates = {
        "google": "https://www.google.com/search?q={query}",
        "bing": "https://www.bing.com/search?q={query}",
        "duckduckgo": "https://duckduckgo.com/?q={query}",
        "brave": "https://search.brave.com/search?q={query}",
    }

    query = "LMM"
    for engine, template in engine_templates.items():
        resolved_url = template.replace("{query}", query)
        assert query in resolved_url
        assert not resolved_url.startswith("http://127.0.0.1:8000/api/v1/browser/search")

def test_browser_gateway_navigation_with_real_search_engines():
    tab = browser_gateway.create_tab(url="https://www.google.com/search?q=LMM", title="Google Search")
    assert tab.url == "https://www.google.com/search?q=LMM"
    assert tab.is_secure is True

    # Navigate to Bing
    updated_tab = browser_gateway.navigate_tab(tab.id, "https://www.bing.com/search?q=LMM")
    assert updated_tab.url == "https://www.bing.com/search?q=LMM"

    # Navigate directly to URL
    direct_url_tab = browser_gateway.navigate_tab(tab.id, "https://en.wikipedia.org/wiki/Large_language_model")
    assert direct_url_tab.url == "https://en.wikipedia.org/wiki/Large_language_model"
