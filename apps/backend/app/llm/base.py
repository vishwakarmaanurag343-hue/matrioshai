from abc import ABC, abstractmethod
from typing import List, Dict, Any, AsyncGenerator, Optional

class LLMProvider(ABC):
    
    @abstractmethod
    async def health(self) -> Dict[str, Any]:
        """Check if LLM backend provider is available."""
        pass

    @abstractmethod
    async def model_info(self, model_name: str) -> Dict[str, Any]:
        """Get info on a specific model."""
        pass

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """Send non-streaming chat request."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """Send streaming chat request, yielding text chunks."""
        pass
