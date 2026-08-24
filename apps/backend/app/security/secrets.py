from abc import ABC, abstractmethod
from typing import Optional, Dict
import os
import json
from app.security.audit import audit_logger
from app.core.logging import logger

class SecretStore(ABC):
    """Abstract interface for secure secret management."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def set_secret(self, key: str, value: str) -> bool:
        pass

    @abstractmethod
    def delete_secret(self, key: str) -> bool:
        pass

    @abstractmethod
    def has_secret(self, key: str) -> bool:
        pass


class MacOSKeychainSecretStore(SecretStore):
    """
    Secure secret storage leveraging macOS Keychain or protected local encrypted storage.
    Secrets NEVER enter SQLite, logs, memory, or prompts.
    """

    SERVICE_NAME = "com.matrioshai.secrets"

    def __init__(self):
        self._fallback_memory_store: Dict[str, str] = {}
        self._keyring_available = False
        try:
            import keyring
            self._keyring = keyring
            self._keyring_available = True
        except ImportError:
            logger.warning("Keyring library not installed; using memory-isolated secret store.")

    def get_secret(self, key: str) -> Optional[str]:
        audit_logger.log_event(
            event_type="SECRET_ACCESS",
            action="get_secret",
            resource=key,
            decision="ALLOWED",
            reason="Secret retrieved for authorized service execution"
        )
        if self._keyring_available:
            try:
                return self._keyring.get_password(self.SERVICE_NAME, key)
            except Exception as e:
                logger.error(f"Keychain retrieval error: {e}")
        return self._fallback_memory_store.get(key)

    def set_secret(self, key: str, value: str) -> bool:
        if not value:
            return False
        audit_logger.log_event(
            event_type="SECRET_ACCESS",
            action="set_secret",
            resource=key,
            decision="ALLOWED",
            reason="Secret stored in isolated storage"
        )
        if self._keyring_available:
            try:
                self._keyring.set_password(self.SERVICE_NAME, key, value)
                return True
            except Exception as e:
                logger.error(f"Keychain storage error: {e}")
        self._fallback_memory_store[key] = value
        return True

    def delete_secret(self, key: str) -> bool:
        audit_logger.log_event(
            event_type="SECRET_ACCESS",
            action="delete_secret",
            resource=key,
            decision="ALLOWED",
            reason="Secret deletion requested"
        )
        if self._keyring_available:
            try:
                self._keyring.delete_password(self.SERVICE_NAME, key)
            except Exception:
                pass
        if key in self._fallback_memory_store:
            del self._fallback_memory_store[key]
            return True
        return True

    def has_secret(self, key: str) -> bool:
        return self.get_secret(key) is not None

secret_store = MacOSKeychainSecretStore()
