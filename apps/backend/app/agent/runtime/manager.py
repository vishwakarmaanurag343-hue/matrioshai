from typing import Dict, Optional
from app.agent.runtime.base import AgentRuntimeProvider
from app.agent.runtime.deepseek_harness import deepseek_harness_provider

class AgentRuntimeManager:
    """
    Registry managing pluggable AgentRuntimeProviders.
    Defaults to DeepSeekHarnessProvider while supporting future pluggable providers.
    """

    def __init__(self):
        self._providers: Dict[str, AgentRuntimeProvider] = {
            deepseek_harness_provider.provider_name(): deepseek_harness_provider
        }
        self._default_provider = deepseek_harness_provider.provider_name()

    def register_provider(self, provider: AgentRuntimeProvider):
        self._providers[provider.provider_name()] = provider

    def get_provider(self, name: Optional[str] = None) -> AgentRuntimeProvider:
        provider_name = name or self._default_provider
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"Agent runtime provider '{provider_name}' is not registered.")
        return provider

    def set_default_provider(self, name: str):
        if name not in self._providers:
            raise ValueError(f"Cannot set default: provider '{name}' is not registered.")
        self._default_provider = name

agent_runtime_manager = AgentRuntimeManager()
