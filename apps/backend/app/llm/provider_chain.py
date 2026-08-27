"""Shared LLM provider chain for MATRIOSHAI.

Extracted from app/api/v1/browser.py so that every consumer (the legacy
/ai-assist endpoint and the DeepSeek-Harness browser step reasoner) routes
through ONE provider-fallback implementation. Behavior of call_llm is
unchanged — this is a move, not a rewrite.
"""
from typing import List, Dict, Any, Optional, Tuple


async def call_llm(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    tools: Optional[List[Dict[str, Any]]] = None
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Queries OpenRouter / NVIDIA NIM endpoint with function calling, falls back to Ollama"""
    from app.core.config import settings
    import httpx
    import json

    # 1. Groq Cloud (Ultra-low latency LLaMA 3.3 70B / 8B)
    print(f"[LLM_TRACE] providers configured: groq={bool(settings.GROQ_API_KEY)} openrouter={bool(settings.OPENROUTER_API_KEY)} nvidia={bool(settings.NVIDIA_API_KEY)}", flush=True)
    if settings.GROQ_API_KEY:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1500
            }
            if tools:
                payload["tools"] = tools

            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""

                tool_calls = msg.get("tool_calls")
                if tool_calls and len(tool_calls) > 0 and tools:
                    fn = tool_calls[0].get("function", {})
                    fn_name = fn.get("name", "")
                    try:
                        raw_args = fn.get("arguments", "{}")
                        fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        fn_args = {}
                    return (content, {"name": fn_name, "arguments": fn_args})

                if content.strip():
                    return (content, None)
            else:
                print(f"[LLM_TRACE] Groq HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
        except Exception as e:
            print(f"[LLM_TRACE] Groq exception: {type(e).__name__}: {e}", flush=True)

    # 2. OpenRouter (DeepSeek / Llama / Stealth)
    if settings.OPENROUTER_API_KEY:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://matrioshai.local",
                "X-Title": "Matrioshai Core",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.OPENROUTER_MODEL or "stealth/ox-alpha",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1500
            }
            if tools:
                payload["tools"] = tools

            # stealth/ox-alpha intermittently returns HTTP 200,
            # finish_reason=stop, with EMPTY content AND empty reasoning.
            # These episodes are transient — retry before degrading to a
            # weaker fallback provider.
            import asyncio
            max_attempts = 3
            for attempt in range(max_attempts):
                if attempt > 0:
                    await asyncio.sleep(0.4)
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]
                    content = msg.get("content") or msg.get("reasoning") or ""

                    # Extract tool call if returned
                    tool_calls = msg.get("tool_calls")
                    if tool_calls and len(tool_calls) > 0:
                        fn = tool_calls[0].get("function", {})
                        fn_name = fn.get("name", "")
                        try:
                            raw_args = fn.get("arguments", "{}")
                            fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                        except Exception:
                            fn_args = {}
                        return (content, {"name": fn_name, "arguments": fn_args})

                    if content.strip():
                        return (content, None)
                    print(f"[LLM_TRACE] OpenRouter 200 but empty content (attempt {attempt + 1}/{max_attempts}) — msg_keys={sorted(msg.keys())} finish={data['choices'][0].get('finish_reason')}", flush=True)
                    continue
                else:
                    # Non-200 from OpenRouter must be visible — silent
                    # fall-through here is what made the assistant UI go
                    # blank with response="".
                    print(f"[LLM_TRACE] OpenRouter HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
                    break
        except Exception as e:
            print(f"[LLM_TRACE] OpenRouter exception: {type(e).__name__}: {e}", flush=True)

    # 2. NVIDIA NIM fallback
    if settings.NVIDIA_API_KEY:
        try:
            url = "https://integrate.api.nvidia.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": settings.NVIDIA_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 1500
            }
            if tools:
                payload["tools"] = tools

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    msg = data["choices"][0]["message"]

                    # Tool-call extraction parity with the OpenRouter branch:
                    # without this, a model that answers via tool_calls returns
                    # content="" and the call was dropped as ("", None).
                    tool_calls = msg.get("tool_calls")
                    if tool_calls and len(tool_calls) > 0 and tools:
                        fn = tool_calls[0].get("function", {})
                        fn_name = fn.get("name", "")
                        known = {t["function"]["name"] for t in tools}
                        if fn_name in known:
                            try:
                                raw_args = fn.get("arguments", "{}")
                                fn_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                            except Exception:
                                fn_args = {}
                            content = msg.get("content") or ""
                            return (content, {"name": fn_name, "arguments": fn_args})
                    nvidia_content = msg.get("content") or ""
                    if nvidia_content.strip():
                        return (nvidia_content, None)
                    print("[LLM_TRACE] NVIDIA 200 but empty content — falling through to Ollama", flush=True)
                print(f"[LLM_TRACE] NVIDIA HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
        except Exception as e:
            print(f"[LLM_TRACE] NVIDIA exception: {type(e).__name__}: {e}", flush=True)

    # 3. Local Ollama fallback
    print("[LLM_TRACE] all cloud providers skipped/failed — falling back to Ollama", flush=True)
    from app.llm.ollama import OllamaProvider
    llm = OllamaProvider()
    resp_text = await llm.chat(messages, temperature=temperature)
    print(f"[LLM_TRACE] Ollama returned len={len(resp_text or '')}", flush=True)
    return (resp_text, None)


async def call_llm_structured(
    messages: List[Dict[str, str]],
    validate,
    max_attempts: int = 4,
    temperature: float = 0.1,
) -> Tuple[Any, str]:
    """Calls the provider chain demanding structured (JSON) output.

    HTTP 200 + empty content is never treated as a successful reasoning
    result, and unparseable/invalid output is rejected and retried against
    the next provider attempt rather than being trusted.

    `validate` maps parsed-JSON-or-None to either a valid object or raises
    ValueError describing why the candidate was rejected. Returns
    (validated_result, raw_text_of_last_attempt).
    """
    import json
    last_raw = ""
    feedback: List[str] = []
    for attempt in range(max_attempts):
        msgs = list(messages)
        if feedback:
            msgs.append({
                "role": "user",
                "content": (
                    "Your previous response was rejected. Reasons:\n- "
                    + "\n- ".join(feedback[-2:])
                    + "\nRespond again with ONLY the corrected JSON object."
                ),
            })
        raw, _tool = await call_llm(msgs, temperature=temperature)
        last_raw = raw or ""
        candidate = None
        feedback = []
        try:
            candidate = _extract_json_object(last_raw)
        except Exception as e:
            feedback.append(f"no parsable JSON object found ({e})")
        if candidate is not None:
            try:
                return validate(candidate), last_raw
            except ValueError as e:
                feedback.append(str(e))
        print(f"[LLM_TRACE] structured attempt {attempt + 1}/{max_attempts} rejected: {feedback}", flush=True)
    raise ValueError(f"Model produced no valid structured output after {max_attempts} attempts. Last raw output: {last_raw[:400]}")


def _extract_json_object(text: str) -> Dict[str, Any]:
    """Pulls the first JSON object out of a model reply, tolerating code fences."""
    import json
    clean = (text or "").strip()
    if clean.startswith("```"):
        parts = clean.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:]
            if p.startswith("{"):
                clean = p
                break
    start = clean.find("{")
    if start == -1:
        raise ValueError("response contains no '{'")
    depth = 0
    for i in range(start, len(clean)):
        if clean[i] == "{":
            depth += 1
        elif clean[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(clean[start:i + 1])
    raise ValueError("unbalanced JSON object")
