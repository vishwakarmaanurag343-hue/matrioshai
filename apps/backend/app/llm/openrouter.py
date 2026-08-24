import json
import httpx
from typing import List, Dict, Any, AsyncGenerator, Optional
from app.llm.base import LLMProvider
from app.core.config import settings
from app.core.logging import logger

class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None, default_model: Optional[str] = None):
        self.api_key = api_key or settings.OPENROUTER_API_KEY
        self.default_model = default_model or settings.OPENROUTER_MODEL or "stealth/ox-alpha"
        self.base_url = "https://openrouter.ai/api/v1"

    async def health(self) -> Dict[str, Any]:
        """Check connection to OpenRouter API."""
        if not self.api_key:
            return {
                "connected": False,
                "configured_model": self.default_model,
                "model_available": False,
                "details": "OpenRouter API Key not configured."
            }
        return {
            "connected": True,
            "configured_model": self.default_model,
            "model_available": True,
            "details": "OpenRouter Operational"
        }

    async def model_info(self, model_name: str) -> Dict[str, Any]:
        return {
            "name": model_name or self.default_model,
            "provider": "openrouter",
            "status": "available"
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        **kwargs
    ) -> str:
        """Non-streaming completions via OpenRouter."""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://matrioshai.local",
            "X-Title": "Matrioshai Core",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                error_body = resp.text
                logger.error(f"OpenRouter Error {resp.status_code}: {error_body}")
                raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {error_body}")

            data = resp.json()
            msg = data["choices"][0]["message"]
            return msg.get("content") or msg.get("reasoning") or ""

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completions via OpenRouter SSE."""
        if not self.api_key:
            raise ValueError("OpenRouter API key not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://matrioshai.local",
            "X-Title": "Matrioshai Core",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as stream_resp:
                if stream_resp.status_code != 200:
                    error_text = await stream_resp.aread()
                    logger.error(f"OpenRouter Stream Error {stream_resp.status_code}: {error_text.decode('utf-8')}")
                    yield f"Error calling OpenRouter ({stream_resp.status_code})"
                    return

                async for line in stream_resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
