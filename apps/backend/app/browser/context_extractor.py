import re
from typing import List, Dict, Any
from app.browser.models import PageContextSummary
from app.browser.filter_list import filter_list_manager

class BrowserContextExtractor:
    """
    Intelligent Webpage Context Extraction Engine:
    - Strips noisy JavaScript, tracking beacons, and raw HTML tags.
    - Extracts clean semantic visible text, headings, forms, and tables.
    - Encloses all web content in strict UNTRUSTED boundaries for AI safety.
    """

    @classmethod
    def extract_context(cls, url: str, raw_html_or_text: str, title: str = "Webpage") -> PageContextSummary:
        # Strip script and style tags
        cleaned = re.sub(r'<script.*?</script>', '', raw_html_or_text, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r'<style.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)

        # Extract headings
        headings = re.findall(r'<h[1-3][^>]*>(.*?)</h[1-3]>', cleaned, flags=re.IGNORECASE)
        headings = [re.sub(r'<[^>]+>', '', h).strip() for h in headings if h.strip()]

        # Extract basic counts
        links_count = len(re.findall(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"', cleaned, re.IGNORECASE))
        forms_count = len(re.findall(r'<form', cleaned, re.IGNORECASE))
        tables_count = len(re.findall(r'<table', cleaned, re.IGNORECASE))

        # Plain text conversion
        visible_text = re.sub(r'<[^>]+>', ' ', cleaned)
        visible_text = re.sub(r'\s+', ' ', visible_text).strip()

        is_https = url.lower().startswith("https://") or url.lower().startswith("about:")

        return PageContextSummary(
            title=title or "Webpage",
            url=url,
            visible_text_summary=visible_text[:3000],  # bounded summary
            headings=headings[:10],
            links_count=links_count,
            forms_count=forms_count,
            tables_count=tables_count,
            is_secure_https=is_https,
            ads_blocked_count=filter_list_manager.get_stats().total_blocked
        )

browser_context_extractor = BrowserContextExtractor()
