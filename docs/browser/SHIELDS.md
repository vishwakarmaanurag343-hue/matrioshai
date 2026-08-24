# MATRIOSHAI Browser Subsystem — Shields & Privacy

## 1. Overview
MATRIOSHAI implements a multi-tiered privacy defense subsystem inspired by Brave Shields.

## 2. Privacy Capabilities
- **Tracker & Ad Blocking**: Evaluates network request domains and scripts against comprehensive blocklists (DoubleClick, Google Syndication, Taboola, Outbrain, Criteo, Moat, etc.).
- **Malicious Domain Defense**: Blocks phishing targets and crypto-stealers before network requests execute.
- **Fingerprinting Protection**: Suppresses canvas/audio telemetry hooks.
- **HTTPS Upgrades**: Forces insecure HTTP requests to HTTPS where supported.
- **Query Parameter Stripping**: Strips tracking parameters (`fbclid`, `gclid`, `utm_*`) from omnibox navigations.
- **Global & Per-Site Overrides**: Interactive Shields Modal allows toggling protections per origin.
