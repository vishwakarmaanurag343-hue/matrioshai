from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List
from app.agent.runtime.models import (
    AgentEvent, RuntimeSessionConfig, TrajectoryResponse
)

class AgentRuntimeProvider(ABC):
    """
    Abstract Base Class for Agent Execution Engines.
    Provides a standardized interface for DeepSeek Harness and future alternative harnesses.
    """

    @abstractmethod
    def provider_name(self) -> str:
        """Return identifier name of the runtime provider."""
        pass

    @abstractmethod
    async def create_session(self, config: RuntimeSessionConfig) -> str:
        """Initialize an agent session and return runtime_session_id."""
        pass

    @abstractmethod
    async def execute_task(
        self,
        session_id: str,
        task_id: str,
        user_goal: str,
        workspace_root: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute a task end-to-end or step-by-step through the runtime."""
        pass

    @abstractmethod
    async def pause_session(self, session_id: str) -> bool:
        """Pause currently running session."""
        pass

    @abstractmethod
    async def resume_session(self, session_id: str) -> bool:
        """Resume paused session."""
        pass

    @abstractmethod
    async def cancel_session(self, session_id: str) -> bool:
        """Cancel and terminate running session."""
        pass

    @abstractmethod
    async def get_trajectory(self, session_id: str) -> TrajectoryResponse:
        """Retrieve full execution trajectory and step history."""
        pass

    @abstractmethod
    async def destroy_session(self, session_id: str) -> bool:
        """Clean up and tear down session resources."""
        pass
