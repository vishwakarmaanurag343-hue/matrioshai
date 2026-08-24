from enum import Enum
from typing import Dict, Any

class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"          # Safe for all models & external sharing
    INTERNAL = "INTERNAL"      # Internal project knowledge, acceptable for local & guarded models
    PRIVATE = "PRIVATE"        # Personal context, requires local processing or policy-compliant cloud redaction
    SENSITIVE = "SENSITIVE"    # PII, financial info, locations, must be redacted before any cloud dispatch
    SECRET = "SECRET"          # API keys, passwords, credentials; NEVER sent to any model, log, or prompt

class DestinationType(str, Enum):
    LOCAL = "LOCAL"            # Local model provider (e.g. Ollama)
    CLOUD = "CLOUD"            # External cloud model provider (e.g. OpenAI/Anthropic in future)

# Default allowance rules for local vs cloud
DEFAULT_POLICY_MATRIX: Dict[DestinationType, Dict[DataClassification, bool]] = {
    DestinationType.LOCAL: {
        DataClassification.PUBLIC: True,
        DataClassification.INTERNAL: True,
        DataClassification.PRIVATE: True,
        DataClassification.SENSITIVE: True,  # Allowed on local machine
        DataClassification.SECRET: False,    # Secrets never go to ANY model prompt
    },
    DestinationType.CLOUD: {
        DataClassification.PUBLIC: True,
        DataClassification.INTERNAL: True,
        DataClassification.PRIVATE: False,   # Must be redacted/blocked for cloud
        DataClassification.SENSITIVE: False, # Must be redacted/blocked for cloud
        DataClassification.SECRET: False,    # Never allowed
    }
}
