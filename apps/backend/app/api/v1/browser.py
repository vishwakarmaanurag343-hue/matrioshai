from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, WebSocket
from pydantic import BaseModel
from app.browser.models import (
    BrowserTab, BrowserBookmark, BrowserHistoryItem, PageContextSummary, AdBlockStats, utc_now
)
from app.browser.gateway import browser_gateway
from app.browser.filter_list import filter_list_manager
from app.browser.bridge import browser_bridge_server
from app.browser.manager import browser_manager
from app.browser.state_store import SecurityRequest

router = APIRouter(prefix="/browser", tags=["Native Browser"])

class CreateTabRequest(BaseModel):
    url: Optional[str] = "https://matrioshai.local"
    title: Optional[str] = "New Tab"

class NavigateTabRequest(BaseModel):
    url: str

class PageContextRequest(BaseModel):
    html_content: Optional[str] = None

@router.get("/tabs", response_model=List[BrowserTab])
def list_tabs():
    return browser_gateway.list_tabs()

@router.post("/tabs", response_model=BrowserTab, status_code=status.HTTP_201_CREATED)
def create_tab(req: CreateTabRequest):
    return browser_gateway.create_tab(url=req.url or "about:blank", title=req.title or "New Tab")

@router.delete("/tabs/{tab_id}")
def close_tab(tab_id: str):
    success = browser_gateway.close_tab(tab_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tab not found")
    return {"success": True}

@router.post("/tabs/{tab_id}/switch", response_model=BrowserTab)
def switch_tab(tab_id: str):
    tab = browser_gateway.switch_tab(tab_id)
    if not tab:
        raise HTTPException(status_code=404, detail="Tab not found")
    return tab

@router.post("/tabs/{tab_id}/navigate", response_model=BrowserTab)
def navigate_tab(tab_id: str, req: NavigateTabRequest):
    # Check adblocker filter
    if filter_list_manager.should_block_url(req.url):
        raise HTTPException(status_code=403, detail="URL blocked by Matrioshai Privacy Filter")

    tab = browser_gateway.navigate_tab(tab_id, req.url)
    if not tab:
        # Fallback: if server reloaded and tab_id was lost, create/re-register tab
        tab = browser_gateway.create_tab(url=req.url, title=req.url.replace("https://", "").replace("http://", "").split("/")[0])
    return tab

@router.post("/context", response_model=PageContextSummary)
def get_active_page_context(req: PageContextRequest):
    context = browser_gateway.get_active_tab_context(req.html_content or "")
    if not context:
        raise HTTPException(status_code=404, detail="No active browser tab found")
    return context

@router.get("/adblock/stats", response_model=AdBlockStats)
def get_adblock_stats():
    return filter_list_manager.get_stats()

class RecordHistoryRequest(BaseModel):
    url: str
    title: str
    profile_id: Optional[str] = "default"
    is_private: Optional[bool] = False

@router.post("/history")
def record_browser_history(req: RecordHistoryRequest):
    # Rule: Never record history for Private or Guest browsing sessions
    if req.is_private or req.profile_id in ("private", "guest") or req.url in ("https://matrioshai.local", "about:blank"):
        return {"status": "ignored", "reason": "private_or_internal"}

    from app.core.database import get_db
    from app.models.db_models import WebSite, WebVisit
    db = next(get_db())
    try:
        # 1. Update or create aggregated site record (used for autocomplete / frequency)
        site = db.query(WebSite).filter(
            WebSite.url == req.url,
            WebSite.profile_id == req.profile_id
        ).first()

        now = utc_now()
        effective_title = req.title or (site.title if site else req.url)

        if site:
            site.visit_count += 1
            site.title = effective_title
            site.last_visited_at = now
        else:
            site = WebSite(
                url=req.url,
                title=effective_title,
                profile_id=req.profile_id or "default",
                visit_count=1,
                last_visited_at=now
            )
            db.add(site)
            db.flush()

        # 2. Record every individual visit event chronologically into web_visits
        visit = WebVisit(
            site_id=site.id,
            url=req.url,
            title=effective_title,
            profile_id=req.profile_id or "default",
            visited_at=now
        )
        db.add(visit)
        db.commit()
        db.refresh(visit)

        return {
            "status": "ok",
            "visit_id": visit.id,
            "site_id": site.id,
            "url": visit.url,
            "title": visit.title,
            "visit_count": site.visit_count,
            "visited_at": visit.visited_at.isoformat()
        }
    finally:
        db.close()

@router.get("/history")
def list_browser_history(limit: int = 100, profile_id: Optional[str] = None):
    """Returns chronological visit timeline (every visit event)"""
    from app.core.database import get_db
    from app.models.db_models import WebVisit
    db = next(get_db())
    try:
        query = db.query(WebVisit)
        if profile_id:
            query = query.filter(WebVisit.profile_id == profile_id)
        items = query.order_by(WebVisit.visited_at.desc()).limit(limit).all()
        return [
            {
                "id": v.id,
                "site_id": v.site_id,
                "url": v.url,
                "title": v.title,
                "profile_id": v.profile_id,
                "visited_at": v.visited_at.isoformat(),
            }
            for v in items
        ]
    finally:
        db.close()

@router.delete("/history")
def clear_browser_history(profile_id: Optional[str] = None):
    """Deletes all history records from SQLite database"""
    from app.core.database import get_db
    from app.models.db_models import WebSite, WebVisit
    db = next(get_db())
    try:
        if profile_id:
            db.query(WebVisit).filter(WebVisit.profile_id == profile_id).delete()
            db.query(WebSite).filter(WebSite.profile_id == profile_id).delete()
        else:
            db.query(WebVisit).delete()
            db.query(WebSite).delete()
        db.commit()
        return {"status": "ok", "cleared": True}
    finally:
        db.close()

@router.get("/search")
async def search_web_results(q: str, engine: Optional[str] = "duckduckgo"):
    """
    Native Search Engine Provider for Matrioshai Browser:
    - Queries search providers directly on the backend.
    - Extracts structured result links, snippets, and titles.
    - Renders as a clean, responsive, native search results page.
    """
    if not q:
        raise HTTPException(status_code=400, detail="Search query required")

    import httpx
    from fastapi.responses import HTMLResponse

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    results = []
    try:
        # Query DuckDuckGo HTML search for clean server-rendered results
        search_target = f"https://html.duckduckgo.com/html/?q={httpx.URL(q).raw_path.decode() if hasattr(httpx.URL(q), 'raw_path') else q}"
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0, verify=False) as client:
            resp = await client.post("https://html.duckduckgo.com/html/", data={"q": q}, headers=headers)
            import re
            
            # Extract links and snippets from HTML
            matches = re.findall(r'<a class="result__url"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*href="[^"]*"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
            for raw_url, raw_title, raw_snippet in matches[:10]:
                clean_url = re.sub(r'<[^>]+>', '', raw_url).strip()
                if "uddg=" in clean_url:
                    import urllib.parse
                    clean_url = urllib.parse.unquote(clean_url.split("uddg=")[1].split("&")[0])
                elif not clean_url.startswith("http"):
                    clean_url = f"https://{clean_url}"

                clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                clean_snippet = re.sub(r'<[^>]+>', '', raw_snippet).strip()
                if clean_url and clean_snippet:
                    results.append({"url": clean_url, "title": clean_title or clean_url, "snippet": clean_snippet})
    except Exception as e:
        pass

    # Build rich Google/Brave dark-mode results page
    results_html = ""
    for r in results:
        results_html += f"""
        <div class="result-card">
            <div class="site-url">{r['url']}</div>
            <a href="http://127.0.0.1:8000/api/v1/browser/proxy?url={r['url']}" class="result-title">{r['title']}</a>
            <div class="result-snippet">{r['snippet']}</div>
        </div>
        """

    page = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8"/>
        <title>{q} - Google Search</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
                background: #1f1f1f;
                color: #e8eaed;
                margin: 0;
                padding: 0;
            }}
            .header-bar {{
                display: flex;
                align-items: center;
                gap: 24px;
                padding: 16px 28px;
                border-bottom: 1px solid #3c4043;
                background: #1f1f1f;
            }}
            .google-logo {{
                font-size: 22px;
                font-weight: 700;
                color: #ffffff;
                letter-spacing: -0.5px;
            }}
            .search-box {{
                flex: 1;
                max-width: 680px;
                background: #303134;
                border: 1px solid #5f6368;
                border-radius: 24px;
                padding: 10px 18px;
                display: flex;
                align-items: center;
                gap: 12px;
            }}
            .search-input {{
                flex: 1;
                background: transparent;
                border: none;
                outline: none;
                color: #ffffff;
                font-size: 14px;
            }}
            .nav-tabs {{
                display: flex;
                gap: 20px;
                padding: 12px 28px;
                border-bottom: 1px solid #3c4043;
                font-size: 13px;
                color: #9aa0a6;
            }}
            .nav-tab.active {{
                color: #8ab4f8;
                font-weight: 600;
                border-bottom: 3px solid #8ab4f8;
                padding-bottom: 8px;
            }}
            .main-content {{
                max-width: 700px;
                padding: 24px 28px;
            }}
            .ai-overview {{
                background: #282a2d;
                border: 1px solid #3c4043;
                border-radius: 14px;
                padding: 20px;
                margin-bottom: 24px;
            }}
            .ai-badge {{
                display: inline-flex;
                align-items: center;
                gap: 6px;
                color: #c58af9;
                font-size: 12px;
                font-weight: 700;
                margin-bottom: 10px;
            }}
            .ai-text {{
                font-size: 14px;
                line-height: 1.6;
                color: #e8eaed;
            }}
            .result-card {{
                margin-bottom: 28px;
            }}
            .site-url {{
                font-size: 12px;
                color: #bdc1c6;
                margin-bottom: 4px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .result-title {{
                font-size: 18px;
                font-weight: 600;
                color: #8ab4f8;
                text-decoration: none;
                display: block;
                margin-bottom: 6px;
            }}
            .result-title:hover {{
                text-decoration: underline;
            }}
            .result-snippet {{
                font-size: 13px;
                color: #bdc1c6;
                line-height: 1.6;
            }}
        </style>
    </head>
    <body>
        <div class="header-bar">
            <div class="google-logo">Google</div>
            <div class="search-box">
                <input class="search-input" type="text" value="{q}" readonly/>
            </div>
        </div>
        <div class="nav-tabs">
            <div class="nav-tab active">All</div>
            <div class="nav-tab">Images</div>
            <div class="nav-tab">Videos</div>
            <div class="nav-tab">News</div>
            <div class="nav-tab">Shopping</div>
        </div>

        <div class="main-content">
            <div class="ai-overview">
                <div class="ai-badge">✦ AI Overview</div>
                <div class="ai-text">
                    An <b>{q}</b> is an advanced neural network architecture trained on extensive multi-modal datasets for deep reasoning, comprehension, and real-time generation.
                </div>
            </div>

            {results_html}
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=page, status_code=200)

@router.get("/proxy")
async def proxy_webpage(url: str):
    """
    Chromium Engine Web Proxy for Matrioshai Browser:
    - Fetches arbitrary external web pages.
    - Strips X-Frame-Options & restrictive CSP headers to allow native embedding inside desktop tab.
    - Enforces ad/tracker blocking before proxying.
    """
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter required")

    if filter_list_manager.should_block_url(url):
        raise HTTPException(status_code=403, detail="Blocked by Matrioshai Privacy Shield")

    import httpx
    from fastapi.responses import HTMLResponse

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20.0, verify=False) as client:
            resp = await client.get(url, headers=headers)
            html_text = resp.text
            
            # Neutralize frame buster scripts like `if (top != self) top.location = self.location;`
            import re
            html_text = re.sub(r'top\.location\s*=', 'window.__unused_loc =', html_text)
            html_text = re.sub(r'parent\.location\s*=', 'window.__unused_loc =', html_text)
            html_text = re.sub(r'top\.window\.location\s*=', 'window.__unused_loc =', html_text)

            # Inject comprehensive proxy routing and CORS neutralizing interceptor
            proxy_interceptor = """
            <script>
            (function() {
                // Intercept clicks on links
                document.addEventListener('click', function(e) {
                    var target = e.target.closest('a');
                    if (target && target.href && !target.href.startsWith('javascript:')) {
                        e.preventDefault();
                        window.location.href = 'http://127.0.0.1:8000/api/v1/browser/proxy?url=' + encodeURIComponent(target.href);
                    }
                }, true);

                // Intercept form submissions
                document.addEventListener('submit', function(e) {
                    var form = e.target;
                    if (form && form.action) {
                        e.preventDefault();
                        var action = form.action;
                        var method = (form.method || 'GET').toUpperCase();
                        if (method === 'GET') {
                            var formData = new FormData(form);
                            var params = new URLSearchParams(formData).toString();
                            var fullUrl = action + (action.indexOf('?') !== -1 ? '&' : '?') + params;
                            window.location.href = 'http://127.0.0.1:8000/api/v1/browser/proxy?url=' + encodeURIComponent(fullUrl);
                        } else {
                            form.submit();
                        }
                    }
                }, true);

                // Neutralize history.replaceState and history.pushState security errors
                var origReplaceState = history.replaceState;
                history.replaceState = function() {
                    try { return origReplaceState.apply(this, arguments); } catch(err) {}
                };
                var origPushState = history.pushState;
                history.pushState = function() {
                    try { return origPushState.apply(this, arguments); } catch(err) {}
                };

                // Catch uncaught security exceptions from analytics/logging scripts
                window.addEventListener('error', function(e) {
                    if (e && e.message && (e.message.indexOf('replaceState') !== -1 || e.message.indexOf('Access-Control') !== -1)) {
                        e.preventDefault();
                        e.stopPropagation();
                    }
                }, true);
            })();
            </script>
            """

            # Inject base tag and interceptor script with proper origin
            import urllib.parse
            parsed_url = urllib.parse.urlparse(url)
            base_origin = f"{parsed_url.scheme}://{parsed_url.netloc}/"

            if "<head>" in html_text:
                html_text = html_text.replace("<head>", f'<head><base href="{base_origin}"/>{proxy_interceptor}')
            elif "<HEAD>" in html_text:
                html_text = html_text.replace("<HEAD>", f'<HEAD><base href="{base_origin}"/>{proxy_interceptor}')
            else:
                html_text = f'<base href="{base_origin}"/>{proxy_interceptor}' + html_text

            return HTMLResponse(content=html_text, status_code=resp.status_code)
    except Exception as e:
        return HTMLResponse(
            content=f"<html><body style='font-family:sans-serif;padding:40px;text-align:center;'><h2>Failed to load {url}</h2><p>{str(e)}</p></body></html>",
            status_code=502
        )

class WebstoreInstallRequest(BaseModel):
    extension_id_or_url: str

@router.post("/extensions/install-webstore")
async def install_from_webstore(req: WebstoreInstallRequest):
    """
    Downloads .crx package from Google Chrome Web Store, extracts it to user profile, and registers manifest.
    """
    import re, os, zipfile, io, httpx, json
    raw = req.extension_id_or_url.strip()
    
    # Extract 32-character Chrome extension ID
    match = re.search(r'([a-z]{32})', raw)
    if not match:
        return {"status": "error", "message": "Invalid Chrome Web Store Extension ID or URL"}
    
    ext_id = match.group(1)
    
    # Google Chrome Web Store CRX3 download URL with macOS Arm64 architecture headers
    crx_url = f"https://clients2.google.com/service/update2/crx?response=redirect&os=mac&arch=arm64&os_arch=arm64&nacl_arch=arm&prod=chromecrx&prodchannel=&prodversion=128.0.0.0&acceptformat=crx2,crx3&x=id%3D{ext_id}%26uc"
    
    save_dir = os.path.expanduser(f"~/.matrioshai/extensions/{ext_id}")
    os.makedirs(save_dir, exist_ok=True)
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0, headers=headers) as client:
            resp = await client.get(crx_url)
            if resp.status_code != 200:
                return {"status": "error", "message": f"Failed to download extension from Web Store: HTTP {resp.status_code}"}
            
            crx_bytes = resp.content
            
            # CRX format header strip to get standard ZIP archive
            zip_start = crx_bytes.find(b'PK\x03\x04')
            if zip_start == -1:
                return {"status": "error", "message": "Failed to parse CRX archive header"}
            
            zip_data = crx_bytes[zip_start:]
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                z.extractall(save_dir)
                
            manifest_path = os.path.join(save_dir, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest_data = json.load(f)
                
                raw_name = manifest_data.get("name", ext_id)
                raw_desc = manifest_data.get("description", "")

                # Resolve Chrome i18n locale __MSG_...__ messages
                locales_dir = os.path.join(save_dir, "_locales")
                if os.path.exists(locales_dir):
                    locale_candidates = ["en", "en_US", "en_GB"]
                    locale_file = None
                    for loc in locale_candidates:
                        cand = os.path.join(locales_dir, loc, "messages.json")
                        if os.path.exists(cand):
                            locale_file = cand
                            break
                    if not locale_file:
                        for item in os.listdir(locales_dir):
                            cand = os.path.join(locales_dir, item, "messages.json")
                            if os.path.exists(cand):
                                locale_file = cand
                                break
                    if locale_file:
                        try:
                            with open(locale_file, "r", encoding="utf-8") as lf:
                                loc_data = json.load(lf)
                            if raw_name.startswith("__MSG_") and raw_name.endswith("__"):
                                key = raw_name[6:-2]
                                if key in loc_data:
                                    raw_name = loc_data[key].get("message", raw_name)
                            if raw_desc.startswith("__MSG_") and raw_desc.endswith("__"):
                                key = raw_desc[6:-2]
                                if key in loc_data:
                                    raw_desc = loc_data[key].get("message", raw_desc)
                        except Exception:
                            pass

                return {
                    "status": "ok",
                    "path": save_dir,
                    "extension_id": ext_id,
                    "name": raw_name,
                    "version": manifest_data.get("version", "1.0.0"),
                    "description": raw_desc
                }
            else:
                return {"status": "error", "message": "Extracted archive does not contain manifest.json"}
    except Exception as e:
        return {"status": "error", "message": f"Installation failed: {str(e)}"}


# ============================================================================
# PHASE 2: BROWSER COMMUNICATION BRIDGE (WEBSOCKET & DIAGNOSTICS)
# ============================================================================

@router.websocket("/bridge/ws")
async def browser_bridge_websocket(websocket: WebSocket):
    """
    Persistent WebSocket bridge endpoint for MATRIOSHAI Chrome Extension.
    Restricted to localhost / Chrome extension origin context.
    """
    await browser_bridge_server.handle_connection(websocket)


@router.get("/bridge/status")
def get_browser_bridge_status():
    """Get current bridge connection status, session info, and round-trip latency."""
    return browser_bridge_server.get_status_summary()


@router.get("/bridge/token")
def get_browser_bridge_auth_token():
    """Retrieve localhost authentication token for extension verification."""
    return {
        "status": "ok",
        "token": browser_bridge_server.get_auth_token(),
        "protocol_version": "1.0"
    }


@router.post("/bridge/ping")
async def ping_browser_extension():
    """Send round-trip ping through bridge to Chrome extension and measure latency."""
    try:
        res = await browser_bridge_server.ping_extension()
        return {"status": "ok", **res}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/bridge/health")
async def get_browser_extension_health():
    """Query health status directly from connected Chrome extension."""
    try:
        health_data = await browser_bridge_server.get_extension_health()
        return {"status": "ok", "health": health_data}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/bridge/info")
async def get_browser_extension_info():
    """Query version, capabilities, and environment info from connected Chrome extension."""
    try:
        info_data = await browser_bridge_server.get_extension_info()
        return {"status": "ok", "info": info_data}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 3: BROWSER CONTROL LAYER (WINDOWS, TABS, NAVIGATION, STATE)
# ============================================================================

class OpenTabRequest(BaseModel):
    url: Optional[str] = None

class NavigateRequest(BaseModel):
    url: str
    timeout_seconds: Optional[float] = 15.0


@router.get("/control/status")
def get_browser_control_status():
    """Get high-level status of the Browser Control Layer and state store."""
    return browser_manager.get_status()


@router.get("/control/windows")
async def get_browser_windows():
    """Discover all open Chrome browser windows."""
    windows = await browser_manager.get_windows()
    return {"status": "ok", "windows": [w.model_dump() for w in windows]}


@router.get("/control/tabs")
async def get_browser_tabs():
    """Discover all open tabs across Chrome windows."""
    tabs = await browser_manager.get_tabs()
    return {"status": "ok", "tabs": [t.model_dump() for t in tabs]}


@router.get("/control/active-tab")
async def get_browser_active_tab():
    """Get the currently active Chrome tab."""
    active_tab = await browser_manager.get_active_tab()
    return {"status": "ok", "active_tab": active_tab.model_dump() if active_tab else None}


@router.post("/control/tabs")
async def open_browser_tab(req: OpenTabRequest):
    """Open a new browser tab in Chrome."""
    try:
        tab = await browser_manager.open_tab(req.url)
        return {"status": "ok", "tab": tab.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/switch")
async def switch_browser_tab(tab_id: int):
    """Switch active tab in Chrome."""
    try:
        tab = await browser_manager.switch_tab(tab_id)
        return {"status": "ok", "tab": tab.model_dump()}
    except Exception as e:
        err_str = str(e)
        if "TAB_NOT_FOUND" in err_str:
            raise HTTPException(status_code=404, detail=err_str)
        raise HTTPException(status_code=503, detail=err_str)


@router.delete("/control/tabs/{tab_id}")
async def close_browser_tab(tab_id: int):
    """Close an open tab in Chrome."""
    try:
        res = await browser_manager.close_tab(tab_id)
        return {"status": "ok", **res}
    except Exception as e:
        err_str = str(e)
        if "TAB_NOT_FOUND" in err_str:
            raise HTTPException(status_code=404, detail=err_str)
        raise HTTPException(status_code=503, detail=err_str)


@router.post("/control/tabs/{tab_id}/navigate")
async def navigate_browser_tab(tab_id: int, req: NavigateRequest):
    """Navigate a real Chrome tab to a target URL and await completion."""
    res = await browser_manager.navigate(tab_id, req.url, req.timeout_seconds or 15.0)
    return {"status": "ok", "navigation": res.model_dump()}


@router.post("/control/tabs/{tab_id}/reload")
async def reload_browser_tab(tab_id: int, timeout_seconds: Optional[float] = 15.0):
    """Reload an existing Chrome tab."""
    try:
        res = await browser_manager.reload(tab_id, timeout_seconds or 15.0)
        return {"status": "ok", "navigation": res.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/go-back")
async def go_back_browser_tab(tab_id: int, timeout_seconds: Optional[float] = 15.0):
    """Navigate backward in history."""
    try:
        res = await browser_manager.go_back(tab_id, timeout_seconds or 15.0)
        return {"status": "ok", "navigation": res.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/go-forward")
async def go_forward_browser_tab(tab_id: int, timeout_seconds: Optional[float] = 15.0):
    """Navigate forward in history."""
    try:
        res = await browser_manager.go_forward(tab_id, timeout_seconds or 15.0)
        return {"status": "ok", "navigation": res.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/wait-for-navigation")
async def wait_for_tab_navigation(tab_id: int, timeout_seconds: Optional[float] = 15.0):
    """Wait for a tab to finish loading."""
    try:
        tab = await browser_manager.wait_for_navigation(tab_id, timeout_seconds or 15.0)
        return {"status": "ok", "tab": tab.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/refresh-state")
async def refresh_browser_state():
    """Force state reconciliation against live Chrome browser."""
    summary = await browser_manager.refresh_browser_state()
    return {"status": "ok", "summary": summary}


@router.get("/control/audit-logs")
def get_browser_audit_logs(limit: int = 50):
    """Query recent browser control audit logs."""
    logs = browser_manager.get_audit_logs(limit)
    return {"status": "ok", "audit_logs": [l.model_dump() for l in logs]}


@router.get("/control/tabs/{tab_id}/observe")
async def observe_browser_tab(tab_id: int, timeout_seconds: Optional[float] = 10.0):
    """
    Extract structured PageObservation from a specific Chrome tab (Phase 4).
    Returns normalized viewport metrics, clean text blocks, semantic headings/landmarks,
    interactive elements with bounding boxes and visibility states, and frame hierarchies.
    """
    try:
        obs = await browser_manager.observe_page(tab_id, timeout_seconds or 10.0)
        return {"status": "ok", "observation": obs.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 5: SEMANTIC PAGE & ACCESSIBILITY INTELLIGENCE ENDPOINTS
# ============================================================================

class SemanticQueryRequest(BaseModel):
    query: Dict[str, Any]
    timeout_seconds: Optional[float] = 10.0

class ResolveElementRequest(BaseModel):
    reference: Dict[str, Any]
    timeout_seconds: Optional[float] = 10.0


@router.get("/control/tabs/{tab_id}/semantic-page")
async def get_semantic_page_model(tab_id: int, timeout_seconds: Optional[float] = 10.0):
    """
    Extract complete SemanticPageModel with computed accessibility roles,
    accessible names, label relationships, and component groupings (Phase 5).
    """
    try:
        model = await browser_manager.get_semantic_page(tab_id, timeout_seconds or 10.0)
        return {"status": "ok", "semantic_model": model.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/semantic-query")
async def query_semantic_page(tab_id: int, req: SemanticQueryRequest):
    """
    Execute deterministic semantic query against a tab's SemanticPageModel.
    Returns FOUND, NOT_FOUND, or AMBIGUOUS (with matches). Never silently guesses.
    """
    try:
        result = await browser_manager.query_page(tab_id, req.query, req.timeout_seconds or 10.0)
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/resolve-element")
async def resolve_semantic_element(tab_id: int, req: ResolveElementRequest):
    """
    Verify if a SemanticElementRef is still valid and uniquely resolvable in the current page model.
    """
    try:
        result = await browser_manager.resolve_element(tab_id, req.reference, req.timeout_seconds or 10.0)
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/invalidate-semantic")
async def invalidate_tab_semantic_model(tab_id: int):
    """
    Explicitly mark the SemanticPageModel for a tab as stale.
    """
    await browser_manager.invalidate_semantic_model(tab_id)
    return {"status": "ok", "invalidated": True}


# ============================================================================
# PHASE 6: VISUAL PAGE INTELLIGENCE ENDPOINTS
# ============================================================================

class CaptureScreenshotRequest(BaseModel):
    format: Optional[str] = "png"
    privacy_mode: Optional[str] = "STANDARD"
    timeout_seconds: Optional[float] = 10.0


class VisualPointQueryRequest(BaseModel):
    x: int
    y: int
    coordinate_system: Optional[str] = "DOM_VIEWPORT"
    privacy_mode: Optional[str] = "STANDARD"
    timeout_seconds: Optional[float] = 10.0


class VisualQueryRequest(BaseModel):
    query: Dict[str, Any] = {}
    privacy_mode: Optional[str] = "STANDARD"
    timeout_seconds: Optional[float] = 10.0


@router.post("/control/tabs/{tab_id}/screenshot")
async def capture_tab_screenshot(tab_id: int, req: CaptureScreenshotRequest):
    """
    Capture visible viewport screenshot for a specific tab (Phase 6).
    Applies privacy filter policies (STANDARD or STRICT redactions).
    """
    try:
        result = await browser_manager.capture_screenshot(
            tab_id=tab_id,
            format=req.format or "png",
            privacy_mode=req.privacy_mode or "STANDARD",
            timeout_seconds=req.timeout_seconds or 10.0
        )
        return {
            "status": "ok",
            "screenshot": result["screenshot"].model_dump(),
            "data_url": result["data_url"]
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/control/tabs/{tab_id}/visual-page")
async def get_visual_page_model(
    tab_id: int,
    privacy_mode: Optional[str] = "STANDARD",
    force_refresh: Optional[bool] = False,
    timeout_seconds: Optional[float] = 10.0
):
    """
    Generate unified VisualPageModel combining DOM observation, SemanticPageModel,
    screenshot metadata, coordinate spaces, and visual regions (Phase 6).
    """
    try:
        model = await browser_manager.get_visual_page(
            tab_id=tab_id,
            privacy_mode=privacy_mode or "STANDARD",
            force_refresh=force_refresh or False,
            timeout_seconds=timeout_seconds or 10.0
        )
        return {"status": "ok", "visual_model": model.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/visual-point-query")
async def query_visual_point(tab_id: int, req: VisualPointQueryRequest):
    """
    Query visual element at specific coordinates (x, y) with z-order stack ranking.
    Returns topmost candidate and full occluded candidate stack. Never performs clicks.
    """
    try:
        result = await browser_manager.query_visual_point(
            tab_id=tab_id,
            x=req.x,
            y=req.y,
            coordinate_system=req.coordinate_system or "DOM_VIEWPORT",
            privacy_mode=req.privacy_mode or "STANDARD",
            timeout_seconds=req.timeout_seconds or 10.0
        )
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/visual-query")
async def query_visual_elements(tab_id: int, req: VisualQueryRequest):
    """
    Query visual elements by element type, region, interactive status, or confidence.
    """
    try:
        result = await browser_manager.query_visual_page(
            tab_id=tab_id,
            query=req.query,
            privacy_mode=req.privacy_mode or "STANDARD",
            timeout_seconds=req.timeout_seconds or 10.0
        )
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/control/tabs/{tab_id}/invalidate-visual")
async def invalidate_tab_visual_model(tab_id: int):
    """
    Explicitly mark the VisualPageModel for a tab as stale.
    """
    browser_manager.invalidate_visual_model(tab_id)
    return {"status": "ok", "invalidated": True}


# ============================================================================
# PHASE 7: UNIFIED BROWSER WORLD MODEL ENDPOINTS
# ============================================================================

class WorldSnapshotRequest(BaseModel):
    reason: Optional[str] = "manual_snapshot"

class WorldDiffRequest(BaseModel):
    source_snapshot_id: str
    target_snapshot_id: str

class WorldElementResolutionRequest(BaseModel):
    reference: Dict[str, Any]
    tab_id: Optional[int] = None
    timeout_seconds: Optional[float] = 10.0

@router.get("/control/world")
async def get_browser_world_model(force_refresh: bool = False, timeout_seconds: float = 10.0):
    """
    Retrieve the canonical BrowserWorldModel synthesized across all windows,
    tabs, page states, frame trees, observations, semantic models, visual models,
    and temporal transitions.
    """
    try:
        world = await browser_manager.get_world_model(force_refresh=force_refresh, timeout_seconds=timeout_seconds)
        return {"status": "ok", "world_model": world.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/world/snapshot")
async def create_browser_world_snapshot(req: Optional[WorldSnapshotRequest] = None):
    """
    Create and retrieve an immutable historical snapshot of the browser world state.
    """
    try:
        reason = req.reason if req else "manual_snapshot"
        snapshot = await browser_manager.create_world_snapshot(reason=reason)
        return {"status": "ok", "snapshot": snapshot.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/world/diff")
async def diff_browser_world_snapshots(req: WorldDiffRequest):
    """
    Calculate deterministic structural and semantic difference between two snapshots.
    """
    try:
        diff = browser_manager.diff_world(req.source_snapshot_id, req.target_snapshot_id)
        return {"status": "ok", "diff": diff.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/world/query")
async def query_browser_world(req: Dict[str, Any]):
    """
    Execute structured query across World Model elements, pages, or tabs.
    """
    try:
        result = browser_manager.query_world(req)
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/world/resolve-element")
async def resolve_world_element_endpoint(req: WorldElementResolutionRequest):
    """
    Resolve a WorldElementRef across page identity, versioning, and DOM stability.
    """
    try:
        result = await browser_manager.resolve_world_element(
            reference=req.reference,
            tab_id=req.tab_id,
            timeout_seconds=req.timeout_seconds or 10.0
        )
        return {"status": "ok", "resolution": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/world/validate")
async def validate_browser_world():
    """
    Validate internal consistency and integrity of the current World Model.
    """
    try:
        validation = browser_manager.validate_world()
        return {"status": "ok", "validation": validation}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/world/reconcile")
async def reconcile_browser_world():
    """
    Force self-healing reconciliation against the live Chrome browser state.
    """
    try:
        world = await browser_manager.reconcile_world()
        return {"status": "ok", "world_model": world.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/world/health")
async def get_browser_world_health():
    """
    Check health status of the Browser World Model.
    """
    try:
        health = browser_manager.check_world_health()
        return {"status": "ok", "health": health.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/world/history")
async def get_browser_world_history(limit: int = 20):
    """
    Retrieve bounded historical list of immutable snapshots.
    """
    try:
        history = browser_manager.get_world_history()
        return {
            "status": "ok",
            "history": [s.model_dump() for s in history[-limit:]],
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 8: SAFE BROWSER ACTION ENGINE ENDPOINTS
# ============================================================================

class ActionExecuteRequest(BaseModel):
    intent: Dict[str, Any]
    confirmed: Optional[bool] = False

class ActionConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool
    user_note: Optional[str] = None

@router.post("/control/actions/execute")
async def execute_browser_action(req: ActionExecuteRequest):
    """
    Execute a validated, deterministic browser action intent.
    Never executes arbitrary scripts or unvalidated coordinates.
    """
    try:
        intent = ActionIntent(**req.intent)
        result = await browser_manager.execute_action(intent, confirmed=req.confirmed or False)
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/actions/validate")
async def validate_browser_action(req: ActionExecuteRequest):
    """
    Dry-run validate an action intent without performing DOM mutations.
    """
    try:
        intent = ActionIntent(**req.intent)
        result = await browser_manager.validate_action(intent)
        return {"status": "ok", "result": result.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/actions/confirm")
async def confirm_browser_action(req: ActionConfirmRequest):
    """
    Approve or reject a high-impact action confirmation request.
    """
    try:
        result = await browser_manager.confirm_action(
            confirmation_id=req.confirmation_id,
            approved=req.approved,
            user_note=req.user_note
        )
        return {"status": "ok", "result": result.model_dump() if result else None}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/actions/queue")
async def get_browser_action_queue(tab_id: Optional[int] = None):
    """
    Get the current per-tab serialized action queue status.
    """
    try:
        target_tab = tab_id or browser_manager.state_store.active_tab_id or 1
        queue_status = browser_manager.get_action_queue(target_tab)
        return {"status": "ok", "queue": queue_status.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/actions/{action_id}/trace")
async def get_browser_action_trace(action_id: str):
    """
    Retrieve full execution trace for an action.
    """
    trace = browser_manager.get_action_trace(action_id)
    if not trace:
        raise HTTPException(status_code=404, detail=f"Action trace for '{action_id}' not found")
    return {"status": "ok", "trace": trace.model_dump()}

@router.get("/control/actions/history")
async def get_browser_action_history(limit: int = 50):
    """
    Retrieve recent action execution history.
    """
    try:
        history = browser_manager.get_action_history(limit=limit)
        return {
            "status": "ok",
            "history": [r.model_dump() for r in history],
            "count": len(history)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 9: ACTION VERIFICATION, RECOVERY & STATE RECONCILIATION ENDPOINTS
# ============================================================================

class ActionExecuteAndVerifyRequest(BaseModel):
    intent: Dict[str, Any]
    wait_policy: Optional[Dict[str, Any]] = None
    confirmed: Optional[bool] = False

class StandaloneVerifyRequest(BaseModel):
    action_result: Dict[str, Any]
    before_snapshot_id: Optional[str] = None
    after_snapshot_id: Optional[str] = None
    wait_policy: Optional[Dict[str, Any]] = None

class ResolveInterventionRequest(BaseModel):
    status: Optional[str] = "RESOLVED"

class CreateCheckpointRequest(BaseModel):
    name: str
    step_index: int = 0
    tab_id: Optional[int] = None

@router.post("/control/actions/execute-and-verify")
async def execute_and_verify_browser_action(req: ActionExecuteAndVerifyRequest):
    """
    Execute an action and verify its outcome against before/after world snapshots and postconditions.
    """
    try:
        intent = ActionIntent(**req.intent)
        wait_policy = VerificationWaitPolicy(**req.wait_policy) if req.wait_policy else None
        act_res, ver_res = await browser_manager.execute_and_verify(
            intent=intent,
            wait_policy=wait_policy,
            confirmed=req.confirmed or False
        )
        return {
            "status": "ok",
            "action_result": act_res.model_dump(),
            "verification_result": ver_res.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/verification/verify")
async def verify_browser_action_result(req: StandaloneVerifyRequest):
    """
    Evaluate standalone verification of an action result against world snapshots.
    """
    try:
        action_result = ActionResult(**req.action_result)
        wait_policy = VerificationWaitPolicy(**req.wait_policy) if req.wait_policy else None
        ver_res = await browser_manager.verify_action_result(
            action_result=action_result,
            before_snapshot_id=req.before_snapshot_id,
            after_snapshot_id=req.after_snapshot_id,
            wait_policy=wait_policy
        )
        return {"status": "ok", "verification_result": ver_res.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/verification/{verification_id}")
async def get_browser_verification(verification_id: str):
    """
    Retrieve verification result by ID.
    """
    ver = browser_manager.get_verification(verification_id)
    if not ver:
        raise HTTPException(status_code=404, detail=f"Verification '{verification_id}' not found")
    return {"status": "ok", "verification": ver.model_dump()}

@router.get("/control/verification/interventions")
async def get_browser_user_interventions():
    """
    List active/recent human intervention requests.
    """
    try:
        interventions = browser_manager.get_user_interventions()
        return {
            "status": "ok",
            "interventions": [i.model_dump() for i in interventions],
            "count": len(interventions)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/verification/interventions/{intervention_id}/resolve")
async def resolve_browser_user_intervention(intervention_id: str, req: ResolveInterventionRequest):
    """
    Resolve/clear a user intervention request and resume automation.
    """
    try:
        resolved = browser_manager.resolve_user_intervention(intervention_id, status=req.status or "RESOLVED")
        if not resolved:
            raise HTTPException(status_code=404, detail=f"Intervention request '{intervention_id}' not found")
        return {"status": "ok", "intervention": resolved.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/control/checkpoints")
async def create_browser_workflow_checkpoint(req: CreateCheckpointRequest):
    """
    Create a named workflow checkpoint for resumable autonomy.
    """
    try:
        cp = browser_manager.create_checkpoint(
            name=req.name,
            step_index=req.step_index,
            tab_id=req.tab_id
        )
        return {"status": "ok", "checkpoint": cp.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/control/checkpoints")
async def get_browser_workflow_checkpoints():
    """
    List all workflow checkpoints.
    """
    try:
        checkpoints = browser_manager.get_checkpoints()
        return {
            "status": "ok",
            "checkpoints": [c.model_dump() for c in checkpoints],
            "count": len(checkpoints)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 10: AGENT PLANNING & EXECUTION LOOP ENDPOINTS
# ============================================================================

# ---------------------------------------------------------------------------
# UNIFIED AGENT RUNTIME — per-iteration reasoning (the Harness brain).
# The frontend BrowserAgentHarness drives the loop: it observes the live
# WKWebView, posts the observation + history here, and receives exactly ONE
# validated structured decision. Execution/verification stay native.
# ---------------------------------------------------------------------------
from app.agent.runtime.browser_reasoning import browser_step_reasoner, ReasoningRequest  # noqa: E402

@router.post("/agent/next-step")
async def agent_next_step(req: ReasoningRequest):
    """
    DeepSeek-Harness reasoning over the live semantic observation.
    Returns a single validated AgentDecision; never executes anything.
    """
    try:
        decision = await browser_step_reasoner.reason_next_step(req)
        return {"status": "ok", "decision": decision.model_dump()}
    except ValueError as e:
        # Structured output could not be obtained from any provider attempt.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"reasoning failed: {type(e).__name__}: {e}")


def _runs_dir() -> "Path":
    from pathlib import Path
    d = Path(__file__).resolve().parents[5] / "benchmarks" / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _append_run_index(record: Dict[str, Any]) -> None:
    """PHASE 0 run boundary log: one JSON line per START/END in index.jsonl."""
    import json
    idx = _runs_dir() / "index.jsonl"
    with idx.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@router.post("/agent/metrics/start")
def agent_metrics_start(payload: Dict[str, Any]):
    """
    PHASE 0 contract: Harness emits a START event before taking the first
    observation so long-running benchmarks have unambiguous run boundaries.
    """
    try:
        run_id = str(payload.get("run_id", "unknown_run"))[:64]
        task_id = str(payload.get("task_id", "unknown_task"))[:64]
        goal = str(payload.get("user_goal", ""))[:512]
        _append_run_index({
            "event": "RUN_START",
            "run_id": run_id,
            "task_id": task_id,
            "user_goal": goal,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        print(f"[RUN_START] run_id={run_id} task_id={task_id} goal={goal!r}", flush=True)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"metrics start failed: {type(e).__name__}: {e}")


@router.post("/agent/metrics")
def agent_metrics_sink(payload: Dict[str, Any]):
    """
    PHASE 0 contract: client emits end-of-run rollup (wall clock, step breakdown,
    perception ladder hit rates, token cost, failure mode). Saved to
    benchmarks/runs/{timestamp}_{run_id}_{task_id}_{status}.json and logged
    to benchmarks/runs/index.jsonl.
    """
    import json

    try:
        run_id = str(payload.get("run_id", "unknown_run"))[:64]
        task_id = str(payload.get("task_id", "unknown_task"))[:64]
        status = str(payload.get("final_status") or "partial")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = _runs_dir() / f"{stamp}_{run_id}_{task_id}_{status}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        wall_ms = payload.get("wall_clock_ms")
        _append_run_index({
            "event": "RUN_END",
            "run_id": run_id,
            "task_id": task_id,
            "status": status,
            "duration_ms": int(wall_ms) if isinstance(wall_ms, (int, float)) else None,
            "artifact_path": str(path),
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        print(
            f"[RUN_END] run_id={run_id} task_id={task_id} status={status} "
            f"duration_ms={wall_ms if wall_ms is not None else 'null'} artifact_path={path}",
            flush=True,
        )
        return {"status": "ok", "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"metrics persist failed: {type(e).__name__}: {e}")


# ============================================================================
# PHASE 12: REAL-WORLD TRANSACTION & BOOKING ENGINE ENDPOINTS
# ============================================================================

class CreateTransactionRequest(BaseModel):
    user_request: str
    workflow_id: Optional[str] = None

class UpdateTransactionOptionsRequest(BaseModel):
    options: List[Dict[str, Any]]

class ConfirmTransactionRequest(BaseModel):
    user_note: Optional[str] = None

class CommitTransactionRequest(BaseModel):
    commit_action: Dict[str, Any]
    auth: Optional[Dict[str, Any]] = None

class CancelTransactionRequest(BaseModel):
    reason: Optional[str] = "User cancelled"

@router.post("/transactions")
async def create_browser_transaction(req: CreateTransactionRequest):
    """
    Create and normalize a new real-world transaction/booking.
    """
    try:
        tx = browser_manager.create_transaction(
            user_request=req.user_request,
            workflow_id=req.workflow_id
        )
        return {"status": "ok", "transaction": tx.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/transactions/{transaction_id}/options")
async def update_browser_transaction_options(transaction_id: str, req: UpdateTransactionOptionsRequest):
    """
    Update discovered comparison options for a transaction.
    """
    try:
        opts = [TransactionOption(**o) for o in req.options]
        tx, selected, is_ambiguous, reason = browser_manager.update_transaction_options(transaction_id, opts)
        return {
            "status": "ok",
            "transaction": tx.model_dump(),
            "selected_option": selected.model_dump() if selected else None,
            "is_ambiguous": is_ambiguous,
            "reason": reason
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/transactions/{transaction_id}/review")
async def prepare_browser_transaction_review(transaction_id: str):
    """
    Prepare snapshot and review package for user confirmation.
    """
    try:
        review = browser_manager.prepare_transaction_review(transaction_id)
        return {"status": "ok", "review": review.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/transactions/{transaction_id}/confirm")
async def confirm_browser_transaction(transaction_id: str, req: Optional[ConfirmTransactionRequest] = None):
    """
    Record user confirmation and issue scoped commit authorization.
    """
    try:
        note = req.user_note if req else None
        conf, auth = browser_manager.confirm_transaction(transaction_id, user_note=note)
        return {
            "status": "ok",
            "confirmation": conf.model_dump(),
            "authorization": auth.model_dump()
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/transactions/{transaction_id}/commit")
async def commit_browser_transaction(transaction_id: str, req: CommitTransactionRequest):
    """
    Execute commit action through Phase 8 & verify through Phase 9.
    """
    try:
        act_intent = ActionIntent(**req.commit_action)
        auth_obj = CommitAuthorization(**req.auth) if req.auth else None
        state, receipt, msg = await browser_manager.commit_transaction(
            transaction_id=transaction_id,
            commit_action=act_intent,
            auth=auth_obj
        )
        return {
            "status": "ok",
            "transaction_state": state.value,
            "receipt": receipt.model_dump() if receipt else None,
            "message": msg
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/transactions/{transaction_id}/cancel")
async def cancel_browser_transaction(transaction_id: str, req: Optional[CancelTransactionRequest] = None):
    """
    Cancel an active transaction.
    """
    try:
        reason = req.reason if req and req.reason else "User cancelled"
        tx = browser_manager.cancel_transaction(transaction_id, reason=reason)
        return {"status": "ok", "transaction": tx.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/transactions/{transaction_id}")
async def get_browser_transaction(transaction_id: str):
    """
    Get full transaction details.
    """
    tx = browser_manager.get_transaction(transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail=f"Transaction '{transaction_id}' not found")
    return {"status": "ok", "transaction": tx.model_dump()}

@router.get("/transactions/receipts/{receipt_id}")
async def get_browser_transaction_receipt(receipt_id: str):
    """
    Get verified transaction receipt.
    """
    rcpt = browser_manager.get_transaction_receipt(receipt_id)
    if not rcpt:
        raise HTTPException(status_code=404, detail=f"Receipt '{receipt_id}' not found")
    return {"status": "ok", "receipt": rcpt.model_dump()}


# ============================================================================
# PHASE 13: SECURITY, PERMISSIONS & HUMAN-IN-THE-LOOP ENDPOINTS
# ============================================================================

class GrantPermissionRequest(BaseModel):
    domain: str
    permissions: List[str]
    scope: Optional[str] = "DOMAIN"
    trust_level: Optional[str] = "TRUSTED"
    ttl_minutes: Optional[int] = 60

class RevokePermissionRequest(BaseModel):
    domain: str

class SetTakeoverRequest(BaseModel):
    state: str

class TriggerEmergencyStopRequest(BaseModel):
    reason: Optional[str] = "User activated emergency kill switch"

@router.post("/security/evaluate")
async def evaluate_security_request(req: SecurityRequest):
    """
    Evaluate operation against security policy, domain trust, and human takeover.
    """
    try:
        decision, auth, msg = browser_manager.evaluate_security_request(req)
        return {
            "status": "ok",
            "decision": decision.value,
            "authorization": auth.model_dump() if auth else None,
            "message": msg
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/security/permissions/grant")
async def grant_browser_domain_permission(req: GrantPermissionRequest):
    """
    Grant scoped permissions to a specific domain.
    """
    try:
        perms = [PermissionCategory(p) for p in req.permissions if p in PermissionCategory._value2member_map_]
        scope = PermissionScope(req.scope) if req.scope in PermissionScope._value2member_map_ else PermissionScope.DOMAIN
        trust = DomainTrustLevel(req.trust_level) if req.trust_level in DomainTrustLevel._value2member_map_ else DomainTrustLevel.TRUSTED
        dp = browser_manager.grant_domain_permission(
            domain=req.domain,
            permissions=perms,
            scope=scope,
            trust_level=trust,
            ttl_minutes=req.ttl_minutes
        )
        return {"status": "ok", "permission": dp.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/security/permissions/revoke")
async def revoke_browser_domain_permission(req: RevokePermissionRequest):
    """
    Immediately revoke all permissions for a domain.
    """
    try:
        revoked = browser_manager.revoke_domain_permission(req.domain)
        return {"status": "ok", "revoked": revoked, "domain": req.domain}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/security/takeover")
async def set_browser_human_takeover(req: SetTakeoverRequest):
    """
    Set human takeover state (AGENT_CONTROL, USER_CONTROL, SHARED_CONTROL, PAUSED).
    """
    try:
        state = TakeoverState(req.state) if req.state in TakeoverState._value2member_map_ else TakeoverState.AGENT_CONTROL
        new_state = browser_manager.set_human_takeover(state)
        return {"status": "ok", "takeover_state": new_state.value}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/security/emergency-stop")
async def trigger_browser_emergency_stop(req: Optional[TriggerEmergencyStopRequest] = None):
    """
    Trigger global emergency stop kill switch.
    """
    try:
        reason = req.reason if req and req.reason else "User activated emergency kill switch"
        stopped = browser_manager.trigger_emergency_stop(reason)
        return {"status": "ok", "emergency_stop_active": stopped}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/security/emergency-stop/reset")
async def reset_browser_emergency_stop():
    """
    Reset emergency stop to resume normal operations.
    """
    try:
        reset = browser_manager.reset_emergency_stop()
        return {"status": "ok", "emergency_stop_active": False}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/security/state")
async def get_browser_security_state():
    """
    Get high-level summary of active permissions, autonomy levels, and emergency controls.
    """
    try:
        summary = browser_manager.get_security_state()
        return {"status": "ok", "security_state": summary}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/security/audit-logs")
async def get_browser_security_audit_logs(limit: int = 50):
    """
    Get recent security audit events with redacted secrets.
    """
    try:
        logs = browser_manager.get_security_audit_logs(limit=limit)
        return {
            "status": "ok",
            "audit_logs": [l.model_dump() for l in logs],
            "count": len(logs)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


# ============================================================================
# PHASE 14: PRODUCTION HARDENING, OBSERVABILITY & RUNTIME ENDPOINTS
# ============================================================================

class RestartComponentRequest(BaseModel):
    component_name: str

class InjectFaultRequest(BaseModel):
    fault_type: str
    parameters: Optional[Dict[str, Any]] = None

@router.get("/runtime/status")
async def get_browser_runtime_status():
    """
    Get master runtime state, health overview, and operational summary.
    """
    try:
        status = browser_manager.get_runtime_status()
        return {"status": "ok", "runtime": status}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/runtime/health")
async def get_browser_all_component_health():
    """
    Get granular health status across all 14 subsystems.
    """
    try:
        health_data = browser_manager.get_all_component_health()
        return {"status": "ok", "health": health_data}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/runtime/supervisor/restart")
async def restart_browser_component(req: RestartComponentRequest):
    """
    Trigger supervisor restart for a specific degraded component.
    """
    try:
        success, msg = browser_manager.restart_component(req.component_name)
        return {"status": "ok", "restarted": success, "message": msg}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/runtime/metrics")
async def get_browser_runtime_metrics():
    """
    Get live operational, latency, action, and transaction metrics.
    """
    try:
        metrics = browser_manager.get_runtime_metrics()
        return {"status": "ok", "metrics": metrics}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/runtime/dead-letter-queue")
async def get_browser_dead_letter_queue(limit: int = 50):
    """
    Inspect failed unrecoverable events from Dead Letter Queue.
    """
    try:
        items = browser_manager.get_dead_letter_items(limit=limit)
        return {
            "status": "ok",
            "dead_letter_items": [item.model_dump() for item in items],
            "count": len(items)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/runtime/chaos/inject")
async def inject_browser_chaos_fault(req: InjectFaultRequest):
    """
    Inject controlled fault for chaos testing.
    """
    try:
        browser_manager.inject_chaos_fault(req.fault_type, req.parameters)
        return {"status": "ok", "fault_injected": req.fault_type}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/runtime/chaos/clear")
async def clear_browser_chaos_faults():
    """
    Clear all active chaos faults.
    """
    try:
        browser_manager.clear_chaos_faults()
        return {"status": "ok", "faults_cleared": True}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
