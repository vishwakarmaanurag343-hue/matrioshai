import pytest
from app.browser.models import BrowserTab, PageContextSummary
from app.browser.filter_list import filter_list_manager
from app.browser.context_extractor import browser_context_extractor
from app.browser.gateway import browser_gateway

def test_filter_list_ad_and_tracker_blocking():
    # Tracker should be blocked
    assert filter_list_manager.should_block_url("https://google-analytics.com/analytics.js") is True
    assert filter_list_manager.should_block_url("https://doubleclick.net/ad.js") is True

    # Legitimate URL should NOT be blocked
    assert filter_list_manager.should_block_url("https://github.com/matrioshai") is False
    assert filter_list_manager.should_block_url("https://en.wikipedia.org/wiki/Artificial_intelligence") is False

    stats = filter_list_manager.get_stats()
    assert stats.total_blocked >= 2

def test_browser_context_extractor():
    sample_html = """
    <html>
      <head>
        <script>console.log("tracking noise");</script>
        <style>body { color: red; }</style>
      </head>
      <body>
        <h1>Matrioshai Architecture</h1>
        <h2>Overview</h2>
        <p>A unified personal AI operating system.</p>
        <a href="https://example.com/docs">Documentation</a>
        <form action="/login"><input type="text" name="user"/></form>
      </body>
    </html>
    """
    context: PageContextSummary = browser_context_extractor.extract_context(
        url="https://docs.matrioshai.local",
        raw_html_or_text=sample_html,
        title="Architecture Docs"
    )
    assert context.title == "Architecture Docs"
    assert "Matrioshai Architecture" in context.headings
    assert "A unified personal AI operating system." in context.visible_text_summary
    assert "console.log" not in context.visible_text_summary  # script stripped
    assert context.links_count == 1
    assert context.forms_count == 1
    assert context.is_secure_https is True

def test_browser_gateway_tab_lifecycle():
    # 1. Create tab
    tab = browser_gateway.create_tab(url="https://github.com", title="GitHub")
    assert tab.id is not None
    assert tab.url == "https://github.com"
    assert tab.is_active is True

    # 2. List tabs
    tabs = browser_gateway.list_tabs()
    assert len(tabs) >= 2

    # 3. Navigate tab
    navigated = browser_gateway.navigate_tab(tab.id, "https://news.ycombinator.com")
    assert navigated.url == "https://news.ycombinator.com"
    assert navigated.title == "news.ycombinator.com"

    # 4. Close tab
    closed = browser_gateway.close_tab(tab.id)
    assert closed is True
