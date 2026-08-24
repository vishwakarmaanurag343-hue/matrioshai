import re
from typing import Set, List
from app.browser.models import AdBlockStats

class FilterListManager:
    """
    Production-grade Content & Privacy Blocker:
    - Matches outbound web requests against known ad networks, trackers, and fingerprinting domains.
    - Prevents malicious telemetry and surveillance scripts from loading.
    - Maintains real-time blocked statistics.
    """

    KNOWN_TRACKER_DOMAINS: Set[str] = {
        "google-analytics.com", "doubleclick.net", "facebook.net", "scorecardresearch.com",
        "criteo.com", "adroll.com", "hotjar.com", "mixpanel.com", "taboola.com",
        "outbrain.com", "branch.io", "segment.io", "quantserve.com", "appsflyer.com",
        "adservice.google.com", "pagead2.googlesyndication.com", "telemetry.badguy.com"
    }

    def __init__(self):
        self._stats = AdBlockStats(
            total_blocked=0,
            trackers_blocked=0,
            ads_blocked=0,
            rules_loaded=len(self.KNOWN_TRACKER_DOMAINS)
        )

    def should_block_url(self, url: str) -> bool:
        url_lower = url.lower()
        for domain in self.KNOWN_TRACKER_DOMAINS:
            if domain in url_lower:
                self._stats.total_blocked += 1
                if "analytics" in domain or "track" in domain or "telemetry" in domain:
                    self._stats.trackers_blocked += 1
                else:
                    self._stats.ads_blocked += 1
                return True
        return False

    def get_stats(self) -> AdBlockStats:
        return self._stats

filter_list_manager = FilterListManager()
