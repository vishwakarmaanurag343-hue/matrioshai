import json
import httpx
from typing import List, Dict, Any, AsyncGenerator, Optional
from app.llm.base import LLMProvider
from app.core.config import settings
from app.core.logging import logger

class OllamaProvider(LLMProvider):
    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = default_model or settings.OLLAMA_MODEL

    async def health(self) -> Dict[str, Any]:
        """Check connection to Ollama server and verify configured model presence."""
        url = f"{self.base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    model_found = any(
                        self.default_model.split(":")[0] in m for m in models
                    )
                    return {
                        "connected": True,
                        "models": models,
                        "configured_model": self.default_model,
                        "model_available": model_found,
                        "details": f"Ollama operational ({len(models)} models installed)"
                    }
                return {
                    "connected": False,
                    "configured_model": self.default_model,
                    "model_available": False,
                    "details": f"Ollama returned HTTP status {resp.status_code}"
                }
        except httpx.ConnectError:
            return {
                "connected": False,
                "configured_model": self.default_model,
                "model_available": False,
                "details": f"Unable to connect to Ollama at {self.base_url}. Please ensure Ollama is running."
            }
        except Exception as e:
            logger.error(f"Error checking Ollama health: {e}")
            return {
                "connected": False,
                "configured_model": self.default_model,
                "model_available": False,
                "details": f"Ollama health check error: {str(e)}"
            }

    async def model_info(self, model_name: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/show"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(url, json={"name": model_name})
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Model {model_name} not found or error status {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        target_model = model or self.default_model
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("message", {}).get("content", "")
                elif resp.status_code == 404:
                    raise RuntimeError(f"Ollama model '{target_model}' not found. Pull it using: ollama pull {target_model}")
                else:
                    raise RuntimeError(f"Ollama error (HTTP {resp.status_code}): {resp.text}")
        except httpx.ConnectError:
            raise RuntimeError(f"Local AI unavailable. Cannot connect to Ollama at {self.base_url}.")
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise e

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        target_model = model or self.default_model
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature}
        }
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code != 200:
                        yield f"[Error: Ollama HTTP {response.status_code}]"
                        return
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                content = chunk.get("message", {}).get("content", "")
                                if content:
                                    yield content
                            except Exception:
                                continue
        except httpx.ConnectError:
            yield "[Local AI is unavailable. Please ensure Ollama is running and try again.]"
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            yield f"[Error: {str(e)}]"
