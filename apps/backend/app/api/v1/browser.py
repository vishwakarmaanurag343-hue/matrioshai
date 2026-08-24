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
from app.llm.provider_chain import call_llm  # unified provider chain (OpenRouter -> NVIDIA -> Ollama)

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

class BrowserAiAssistRequest(BaseModel):
    action: str  # "Summarize", "Research", "Extract", "Find", or custom query
    url: str
    title: str
    headings: List[str] = []
    text_blocks: List[str] = []
    interactive_elements: List[Dict[str, Any]] = []
    interactive_elements_count: int = 0

@router.post("/ai-assist")
async def browser_ai_assist(req: BrowserAiAssistRequest):
    """
    Connects Native Browser Page Context and Interactive Elements to OpenRouter LLM with Tool Calling
    """
    import urllib.parse
    import json

    # Extract search query if present in URL
    search_query = ""
    try:
        parsed_url = urllib.parse.urlparse(req.url)
        params = urllib.parse.parse_qs(parsed_url.query)
        for key in ["q", "query", "k", "search_query", "searchTerm"]:
            if key in params and params[key]:
                search_query = params[key][0]
                break
    except Exception:
        pass

    # Build rich context about what is currently on screen
    screen_context_parts = [
        f"Active Webpage URL: {req.url}",
        f"Active Page Title: {req.title}",
    ]
    if search_query:
        screen_context_parts.append(f"User Search Query / Terms: '{search_query}'")
    if req.headings:
        screen_context_parts.append(f"Key Headings on Screen:\n" + "\n".join(f"  • {h}" for h in req.headings[:15]))
    if req.text_blocks:
        screen_context_parts.append(f"Visible Content Snippets & Search Results:\n" + "\n".join(f"  • {t}" for t in req.text_blocks[:25]))

    # List interactive elements for clicking / typing
    if req.interactive_elements:
        elem_lines = []
        for el in req.interactive_elements[:45]:
            el_id = el.get("element_id", "")
            role = el.get("role", "element")
            name = el.get("name", "")
            href = el.get("href", "")
            if href:
                elem_lines.append(f"  • [{el_id}] {role}: '{name}' -> {href}")
            else:
                elem_lines.append(f"  • [{el_id}] {role}: '{name}'")
        screen_context_parts.append("Interactive Elements On Screen (Clickable/Interactable):\n" + "\n".join(elem_lines))

    full_screen_context = "\n".join(screen_context_parts)

    system_prompt = (
        "You are Matrioshai AI Copilot, an autonomous browser assistant with live screen vision and browser execution tools.\n\n"
        "### CRITICAL ACTION POLICY:\n"
        "1. When the user asks you to open, click, view, visit, or book anything on the page (e.g. 'open the best and book for me', 'open the 3rd website', 'click the first result', 'open Skoda Kylaq'), you MUST IMMEDIATELY invoke the appropriate tool (`click` or `navigate`).\n"
        "2. Do NOT output a monologue or text explanation without calling a tool when an action is requested. EMIT THE TOOL CALL DIRECTLY.\n"
        "3. When interactive elements are listed under 'Interactive Elements On Screen', select the most relevant result (e.g. the official website or top result) and call `click(element_id)`.\n"
        "4. NEVER guess or hallucinate URLs with `navigate` when the link or search result exists in the interactive elements list — ALWAYS call `click(element_id)`.\n"
        "5. If the user asks a QUESTION (what/why/where/how/list/find-information) that can be answered from the page context above, ANSWER IN PLAIN TEXT — do NOT call any tool. Tools are ONLY for performing actions on the page."
    )

    browser_tools = [
        {
            "type": "function",
            "function": {
                "name": "click",
                "description": "Click an interactive element (search result link, website link, button, tab) on the current webpage using its element_id (e.g. 'el_0', 'el_1'). ALWAYS use this tool instead of 'navigate' when opening search results or clicking on-screen links.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element_id": {
                            "type": "string",
                            "description": "The exact element_id of the element to click (e.g. 'el_0', 'el_1')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Short description of the link or button being clicked"
                        }
                    },
                    "required": ["element_id"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "navigate",
                "description": "Navigate directly to a specific URL provided explicitly by the user or for initial domain visits. DO NOT use this tool to open search results or links found on the page — use 'click' with the element_id instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Explicit http/https URL to navigate to"
                        },
                        "description": {
                            "type": "string",
                            "description": "Description of the destination"
                        }
                    },
                    "required": ["url"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "type",
                "description": "Type text into a search box, input field, or textarea on the current page",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "element_id": {
                            "type": "string",
                            "description": "The element_id of the input field"
                        },
                        "text": {
                            "type": "string",
                            "description": "The text to type into the field"
                        }
                    },
                    "required": ["element_id", "text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "scroll",
                "description": "Scroll the active webpage up or down",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["down", "up"],
                            "description": "Direction to scroll the page"
                        }
                    },
                    "required": ["direction"]
                }
            }
        }
    ]

    clean_action = req.action.replace("Custom Query: ", "").strip()

    if clean_action == "Summarize":
        user_prompt = f"[Active Screen Context]\n{full_screen_context}\n\nPlease summarize this webpage concisely with the key takeaways."
    elif clean_action == "Extract":
        user_prompt = f"[Active Screen Context]\n{full_screen_context}\n\nPlease extract key facts, entities, data, and actionable items from this webpage."
    elif clean_action == "Research":
        user_prompt = f"[Active Screen Context]\n{full_screen_context}\n\nPlease analyze this page for core topics, arguments, and related research questions."
    elif clean_action == "Find":
        user_prompt = f"[Active Screen Context]\n{full_screen_context}\n\nPlease list the main sections and tools found on this webpage."
    else:
        # User typed a direct question or command
        is_greeting = clean_action.lower() in ["hi", "hii", "hello", "hey", "sup", "how are you", "good morning", "good evening"]
        if is_greeting:
            user_prompt = clean_action
        else:
            user_prompt = f"[Active Screen & Webpage Context]\n{full_screen_context}\n\n[User Message]: {clean_action}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    print("\n========== [EXACT RAW PAYLOAD SENT TO LLM] ==========", flush=True)
    print(json.dumps({"messages": messages, "tools": browser_tools}, indent=2), flush=True)
    print("======================================================\n", flush=True)

    try:
        print(f"[AI_TRACE] model request started: messages={len(messages)} tools={len(browser_tools)} prompt_chars={len(user_prompt)}", flush=True)
        reply, tool_call = await call_llm(messages, temperature=0.2, tools=browser_tools)
        print(f"[AI_TRACE] call_llm returned: reply_len={len(reply or '')} reply_prefix={(reply or '')[:120]!r} tool_call={tool_call.get('name') if tool_call else None}", flush=True)
        if reply and "<think>" in reply and "</think>" in reply:
            reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()

        # Never return a silent success with nothing in it: the frontend skips
        # appending any assistant message when response is empty, which left
        # the chat UI waiting forever. Surface an explicit error instead.
        if not (reply and reply.strip()) and not tool_call:
            return {
                "status": "error",
                "response": "All model providers returned an empty response (primary model may be rate-limited upstream). Please retry shortly.",
                "tool_call": None
            }

        response_payload = {
            "status": "ok",
            "response": reply.strip() if reply else "",
            "tool_call": tool_call
        }
        return response_payload
    except Exception as e:
        return {"status": "error", "response": f"LLM Error: {str(e)}", "tool_call": None}

@router.post("/debug/browser-context")
async def debug_browser_context(req: BrowserAiAssistRequest):
    """
    Debug Endpoint: Returns raw received URL, Title, and Extracted DOM Content
    """
    import urllib.parse
    search_query = ""
    try:
        parsed = urllib.parse.urlparse(req.url)
        params = urllib.parse.parse_qs(parsed.query)
        for key in ["q", "query", "k", "search_query"]:
            if key in params:
                search_query = params[key][0]
                break
    except Exception:
        pass

    return {
        "raw_received_url": req.url,
        "raw_received_title": req.title,
        "parsed_search_query": search_query,
        "headings_count": len(req.headings),
        "headings": req.headings,
        "text_blocks_count": len(req.text_blocks),
        "text_blocks_sample": req.text_blocks[:10],
        "interactive_elements_count": req.interactive_elements_count,
    }

class AgentPlanRequest(BaseModel):
    user_goal: str
    url: str
    title: str
    headings: List[str] = []
    text_blocks: List[str] = []
    interactive_elements: List[Dict[str, Any]] = []
    action_history: List[str] = []

@router.post("/plan-agent")
async def plan_agent_task(req: AgentPlanRequest):
    """
    ReAct-Style Autonomous Agent Planner using NVIDIA NIM LLM
    """
    elements_desc = "\n".join(
        f"- ID: {el.get('element_id')} | Role: {el.get('role')} | Name: '{el.get('name')}' | Selector: {el.get('selector')}"
        for el in req.interactive_elements[:30]
    )

    history_desc = "\n".join(f"- {h}" for h in req.action_history) if req.action_history else "No previous actions."

    prompt = f"""You are an autonomous browser agent following the ReAct (Reason, Act, Observe) framework.
User Goal: "{req.user_goal}"
Current Webpage: {req.title} ({req.url})

Action History:
{history_desc}

Current Headings:
{', '.join(req.headings[:10])}

Current Page Snippets:
{chr(10).join('- ' + t for t in req.text_blocks[:10])}

Available Interactive Elements on Current Page:
{elements_desc if elements_desc else "No interactive elements detected."}

Instructions:
1. Reason about the next logical steps to achieve the user's goal.
2. Return ONLY a valid JSON array of 1 to 5 steps. No markdown formatting outside the JSON, no explanations.
3. Each step object must have:
   - "step_id": string (e.g. "step_1")
   - "tool": string (one of: "browser.type", "browser.click", "browser.scroll", "browser.navigate", "browser.extract", "browser.done")
   - "target": string or null (the exact element_id like "el_1" from the list above)
   - "value": string or null (text to type or URL to navigate)
   - "description": string (clear summary of this step)
   - "risk_level": string ("ReadOnly", "Low", "Medium", "High")
   - "needs_replan": boolean (true if the agent must observe page changes after this step)

Example JSON Output:
[
  {{"step_id": "step_1", "tool": "browser.type", "target": "el_1", "value": "Rust", "description": "Type 'Rust' into search box", "risk_level": "Medium", "needs_replan": false}},
  {{"step_id": "step_2", "tool": "browser.click", "target": "el_2", "value": null, "description": "Click search button", "risk_level": "Medium", "needs_replan": true}}
]
"""

    messages = [
        {"role": "system", "content": "You are a precise autonomous browser automation planner. Always output valid JSON array."},
        {"role": "user", "content": prompt}
    ]

    try:
        reply = await call_llm(messages, temperature=0.1)
        if "<think>" in reply and "</think>" in reply:
            reply = re.sub(r'<think>.*?</think>', '', reply, flags=re.DOTALL).strip()
        
        json_match = re.search(r'\[\s*\{.*\}\s*\]', reply, flags=re.DOTALL)
        if json_match:
            steps_data = json.loads(json_match.group(0))
        else:
            steps_data = json.loads(reply.strip())
            
        return {"status": "ok", "steps": steps_data}
    except Exception as e:
        # Fallback to smart goal-driven heuristic plan if JSON parse fails
        fallback_steps = [
            {
                "step_id": "step_1",
                "tool": "browser.extract",
                "target": None,
                "value": None,
                "description": f"Extract live page context for goal: '{req.user_goal}'",
                "risk_level": "ReadOnly",
                "needs_replan": False
            },
            {
                "step_id": "step_2",
                "tool": "browser.scroll",
                "target": None,
                "value": None,
                "description": "Scroll down to examine full document and search results",
                "risk_level": "Low",
                "needs_replan": True
            }
        ]
        return {"status": "fallback", "steps": fallback_steps, "error": str(e)}







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

class CreateAgentTaskRequest(BaseModel):
    user_request: str
    priority: Optional[str] = "NORMAL"

class StartAgentTaskRequest(BaseModel):
    max_iterations: Optional[int] = 30

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
async def mark_agent_run_start(payload: Dict[str, Any]):
    """
    PHASE 0 RUN_START marker: records task start (run_id/task_id/goal/ts)
    to benchmarks/runs/index.jsonl and prints an explicit log boundary so
    each regression run has clean [RUN_START]/[RUN_END] brackets.
    """
    import json
    try:
        record = {
            "event": "RUN_START",
            "run_id": str(payload.get("run_id", "unknown_run"))[:64],
            "task_id": str(payload.get("task_id", "unknown_task"))[:64],
            "goal": str(payload.get("goal", ""))[:300],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        _append_run_index(record)
        print(f"[RUN_START] run_id={record['run_id']} task_id={record['task_id']} goal={record['goal']!r}", flush=True)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run-start mark failed: {type(e).__name__}: {e}")


@router.post("/agent/metrics")
async def save_agent_metrics(payload: Dict[str, Any]):
    """
    PHASE 0 metrics ledger sink: persists one JSON artifact per task run
    (success or failure) under benchmarks/runs/. Measurement only.
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


@router.post("/agent/tasks")
async def create_browser_agent_task(req: CreateAgentTaskRequest):
    """
    Create a new browser agent task and normalize user goal.
    """
    try:
        priority_val = TaskPriority(req.priority) if req.priority in TaskPriority._value2member_map_ else TaskPriority.NORMAL
        task = browser_manager.create_agent_task(
            user_request=req.user_request,
            priority=priority_val
        )
        return {"status": "ok", "task": task.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/agent/tasks/{task_id}/start")
async def start_browser_agent_task(task_id: str, req: Optional[StartAgentTaskRequest] = None):
    """
    Start closed-loop agent execution on a task.
    """
    try:
        max_iter = req.max_iterations if req and req.max_iterations else 30
        res = await browser_manager.start_agent_task(task_id=task_id, max_iterations=max_iter)
        return {"status": "ok", "result": res.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/agent/tasks/{task_id}/pause")
async def pause_browser_agent_task(task_id: str):
    """
    Pause a running agent task.
    """
    try:
        task = browser_manager.pause_agent_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return {"status": "ok", "task": task.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/agent/tasks/{task_id}/resume")
async def resume_browser_agent_task(task_id: str):
    """
    Resume a paused agent task after state reconciliation.
    """
    try:
        res = await browser_manager.resume_agent_task(task_id)
        return {"status": "ok", "result": res.model_dump()}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.post("/agent/tasks/{task_id}/abort")
async def abort_browser_agent_task(task_id: str):
    """
    Abort an active agent task.
    """
    try:
        task = browser_manager.abort_agent_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return {"status": "ok", "task": task.model_dump()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

@router.get("/agent/tasks/{task_id}")
async def get_browser_agent_task(task_id: str):
    """
    Get current task state, plan, progress, and memory.
    """
    task = browser_manager.get_agent_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return {"status": "ok", "task": task.model_dump()}

@router.get("/agent/events")
async def get_browser_agent_events(task_id: Optional[str] = None, limit: int = 50):
    """
    Get recent agent execution stream events.
    """
    try:
        events = browser_manager.get_agent_events(task_id=task_id, limit=limit)
        return {
            "status": "ok",
            "events": [e.model_dump() for e in events],
            "count": len(events)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


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
