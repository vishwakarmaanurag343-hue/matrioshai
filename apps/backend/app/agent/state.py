import asyncio
from typing import Dict, Any, List
from app.core.logging import logger

class AgentStateManager:
    """
    Manages live working memory and event broadcasting for active AgentTasks.
    """

    def __init__(self):
        # task_id -> list of event subscriber queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        # task_id -> cancel Event
        self._cancel_events: Dict[str, asyncio.Event] = {}
        # task_id -> pause Event (set = running, clear = paused)
        self._pause_events: Dict[str, asyncio.Event] = {}

    def register_task(self, task_id: str):
        self._cancel_events[task_id] = asyncio.Event()
        pause_evt = asyncio.Event()
        pause_evt.set()  # running by default
        self._pause_events[task_id] = pause_evt
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []

    def subscribe(self, task_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(q)
        return q

    def unsubscribe(self, task_id: str, q: asyncio.Queue):
        if task_id in self._subscribers and q in self._subscribers[task_id]:
            self._subscribers[task_id].remove(q)

    async def broadcast_event(self, task_id: str, event_type: str, data: Dict[str, Any]):
        msg = {"event": event_type, "task_id": task_id, "data": data}
        if task_id in self._subscribers:
            for q in list(self._subscribers[task_id]):
                try:
                    await q.put(msg)
                except Exception:
                    pass

    def is_cancelled(self, task_id: str) -> bool:
        return self._cancel_events.get(task_id, asyncio.Event()).is_set()

    def cancel_task(self, task_id: str):
        if task_id in self._cancel_events:
            self._cancel_events[task_id].set()

    def is_paused(self, task_id: str) -> bool:
        evt = self._pause_events.get(task_id)
        return evt is not None and not evt.is_set()

    def pause_task(self, task_id: str):
        if task_id in self._pause_events:
            self._pause_events[task_id].clear()

    def resume_task(self, task_id: str):
        if task_id in self._pause_events:
            self._pause_events[task_id].set()

    async def wait_if_paused(self, task_id: str):
        evt = self._pause_events.get(task_id)
        if evt:
            await evt.wait()

agent_state_manager = AgentStateManager()
