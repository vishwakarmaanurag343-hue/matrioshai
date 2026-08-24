"""
MATRIOSHAI Security, Permissions & Human-in-the-Loop Engine (Phase 13)

Establishes the strict security boundary above the browser agent runtime.
Enforces:
- FAIL CLOSED
- LEAST PRIVILEGE
- EXPLICIT SHORT-LIVED AUTHORIZATION
- PROMPT INJECTION DEFENSE (Web content is untrusted data)
- HUMAN TAKEOVER & EMERGENCY STOP (Kill switch)
- SECRET & CREDENTIAL ISOLATION (No CVV/passwords in logs or LLMs)
"""

import time
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from app.core.logging import logger
from app.browser.state_store import (
    browser_state_store,
    BrowserStateStore,
    SecurityDecision,
    SecurityActor,
    PermissionCategory,
    PermissionScope,
    DomainTrustLevel,
    DataClassification,
    AutonomyLevel,
    TakeoverState,
    DomainPermission,
    SecurityRequest,
    ActionAuthorization,
    UserApprovalToken,
    SpendingLimitPolicy,
    SecurityAuditEvent
)

class PromptInjectionDefense:
    """
    Defends against malicious webpage prompt injections.
    Enforces strict hierarchy:
    SYSTEM SECURITY POLICY > USER POLICY > WORKFLOW > AGENT PLAN > WEBSITE CONTENT.
    Webpage instructions are treated strictly as untrusted data.
    """

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"system\s+prompt\s+override",
        r"upload\s+your\s+credentials",
        r"send\s+passwords",
        r"disable\s+security\s+policy",
        r"bypass\s+confirmation"
    ]

    def sanitize_untrusted_content(self, text: str) -> str:
        if not text:
            return ""
        import re
        sanitized = text
        for pat in self.INJECTION_PATTERNS:
            if re.search(pat, sanitized, re.IGNORECASE):
                logger.warning(f"[MATRIOSHAI][Security] Detected potential prompt injection attempt in webpage content: '{pat}'")
                sanitized = re.sub(pat, "[UNTRUSTED_INSTRUCTION_REDACTED]", sanitized, flags=re.IGNORECASE)
        return sanitized

    def is_injection_threat(self, text: str) -> bool:
        if not text:
            return False
        import re
        return any(re.search(pat, text, re.IGNORECASE) for pat in self.INJECTION_PATTERNS)

class DataProtectionEngine:
    """
    Enforces data minimization, purpose binding, and secret redaction.
    Guarantees secrets (passwords, CVV, OTP, private keys) are never logged or sent to LLMs.
    """

    SECRET_KEYS = {"password", "cvv", "cvc", "otp", "pin", "card_number", "auth_token", "secret", "private_key"}

    def redact_secrets(self, data: Dict[str, Any]) -> Dict[str, Any]:
        redacted = {}
        for k, v in data.items():
            if any(sk in k.lower() for sk in self.SECRET_KEYS):
                redacted[k] = "[REDACTED_SECRET]"
            elif isinstance(v, dict):
                redacted[k] = self.redact_secrets(v)
            elif isinstance(v, list):
                redacted[k] = [self.redact_secrets(item) if isinstance(item, dict) else item for item in v]
            else:
                redacted[k] = v
        return redacted

    def classify_data(self, key: str, value: Any) -> DataClassification:
        k_lower = key.lower()
        if any(sk in k_lower for sk in self.SECRET_KEYS):
            return DataClassification.SECRET
        if any(sk in k_lower for sk in ["passport", "ssn", "national_id", "govt_id"]):
            return DataClassification.HIGHLY_SENSITIVE
        if any(sk in k_lower for sk in ["phone", "email", "address", "dob", "name"]):
            return DataClassification.SENSITIVE
        if any(sk in k_lower for sk in ["preference", "history", "bookmark"]):
            return DataClassification.PRIVATE
        return DataClassification.PUBLIC

class HumanTakeoverController:
    """
    Manages human takeover of browser control.
    When a human takes over, the agent stops dispatching browser actions.
    When control is returned, forces world re-observation and replanning.
    """

    def __init__(self, state_store: BrowserStateStore):
        self.state_store = state_store

    def set_takeover_state(self, state: TakeoverState) -> TakeoverState:
        old_state = self.state_store.takeover_state
        self.state_store.takeover_state = state
        logger.info(f"[MATRIOSHAI][Security] Human Takeover transition: {old_state.value} -> {state.value}")
        return state

    def can_agent_act(self) -> bool:
        return (
            self.state_store.takeover_state in [TakeoverState.AGENT_CONTROL, TakeoverState.SHARED_CONTROL]
            and not self.state_store.emergency_stop_active
        )

class EmergencyStopController:
    """
    Global Kill Switch.
    Immediately halts all autonomous agent execution, blocks transactions,
    and invalidates active action authorizations.
    """

    def __init__(self, state_store: BrowserStateStore):
        self.state_store = state_store

    def trigger_emergency_stop(self, reason: str = "User activated emergency kill switch") -> bool:
        self.state_store.emergency_stop_active = True
        self.state_store.takeover_state = TakeoverState.PAUSED
        # Invalidate active authorizations
        self.state_store.action_authorizations.clear()
        logger.warning(f"[MATRIOSHAI][Security] EMERGENCY STOP ACTIVATED: {reason}")
        return True

    def reset_emergency_stop(self) -> bool:
        self.state_store.emergency_stop_active = False
        self.state_store.takeover_state = TakeoverState.AGENT_CONTROL
        logger.info("[MATRIOSHAI][Security] Emergency stop reset to normal operation.")
        return True

class PermissionManager:
    """
    Manages domain and scoped permissions with least privilege and expiration.
    """

    def __init__(self, state_store: BrowserStateStore):
        self.state_store = state_store

    def grant_permission(
        self,
        domain: str,
        permissions: List[PermissionCategory],
        scope: PermissionScope = PermissionScope.DOMAIN,
        trust_level: DomainTrustLevel = DomainTrustLevel.TRUSTED,
        ttl_minutes: Optional[int] = 60,
        actor: SecurityActor = SecurityActor.USER
    ) -> DomainPermission:
        exp = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat() if ttl_minutes else None
        perm = DomainPermission(
            domain=domain.lower(),
            permissions=permissions,
            scope=scope,
            trust_level=trust_level,
            expires_at=exp,
            created_by=actor,
            status="ACTIVE"
        )
        self.state_store.domain_permissions[domain.lower()] = perm
        logger.info(f"[MATRIOSHAI][Security] Granted {len(permissions)} permissions for domain '{domain}' (Scope: {scope.value})")
        return perm

    def revoke_permission(self, domain: str) -> bool:
        domain_key = domain.lower()
        if domain_key in self.state_store.domain_permissions:
            self.state_store.domain_permissions[domain_key].status = "REVOKED"
            # Purge any existing authorizations for this domain
            self.state_store.action_authorizations = {
                k: v for k, v in self.state_store.action_authorizations.items()
                if v.target_domain != domain_key
            }
            logger.info(f"[MATRIOSHAI][Security] Revoked all permissions for domain '{domain}'")
            return True
        return False

    def has_permission(self, domain: str, permission: PermissionCategory) -> bool:
        domain_key = domain.lower()
        perm = self.state_store.domain_permissions.get(domain_key)
        if not perm or perm.status != "ACTIVE":
            return False

        # Check expiration
        if perm.expires_at:
            exp_time = datetime.fromisoformat(perm.expires_at)
            if datetime.now(timezone.utc) > exp_time:
                perm.status = "EXPIRED"
                return False

        return permission in perm.permissions

class ActionRateLimiter:
    """
    Prevents rapid-fire repeated actions or runaway automated loops.
    """

    def __init__(self, max_actions_per_minute: int = 60):
        self.max_rate = max_actions_per_minute
        self.action_timestamps: List[float] = []

    def check_rate_limit(self) -> bool:
        now = time.time()
        # Keep timestamps from last 60 seconds
        self.action_timestamps = [t for t in self.action_timestamps if now - t < 60.0]
        if len(self.action_timestamps) >= self.max_rate:
            logger.warning("[MATRIOSHAI][Security] Action rate limit exceeded")
            return False
        self.action_timestamps.append(now)
        return True

class SecureAuditLogger:
    """
    Append-only immutable audit trail with automatic secret redaction.
    """

    def __init__(self, state_store: BrowserStateStore):
        self.state_store = state_store

    def log_security_event(
        self,
        actor: SecurityActor,
        action: str,
        policy_decision: SecurityDecision,
        risk: str,
        target: Optional[str] = None,
        workflow_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
        result: str = "SUCCESS"
    ) -> SecurityAuditEvent:
        evt = SecurityAuditEvent(
            event_id=f"secaudit_{secrets.token_hex(4)}",
            actor=actor.value,
            action=action,
            target=target,
            policy_decision=policy_decision.value,
            risk=risk,
            workflow_id=workflow_id,
            transaction_id=transaction_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            result=result
        )
        self.state_store.security_audit_events.append(evt)
        if len(self.state_store.security_audit_events) > self.state_store.MAX_SECURITY_AUDIT_EVENTS:
            self.state_store.security_audit_events.pop(0)
        logger.info(f"[MATRIOSHAI][Security] Audit: {action} ({policy_decision.value}, risk={risk})")
        return evt

class SecurityPolicyEngine:
    """
    Master Gatekeeper evaluating every sensitive operation.
    Issues short-lived, replay-protected ActionAuthorization tokens.
    """

    def __init__(self, state_store: Optional[BrowserStateStore] = None):
        self.state_store = state_store or browser_state_store
        self.prompt_defense = PromptInjectionDefense()
        self.data_protection = DataProtectionEngine()
        self.takeover = HumanTakeoverController(self.state_store)
        self.emergency_stop = EmergencyStopController(self.state_store)
        self.permissions = PermissionManager(self.state_store)
        self.rate_limiter = ActionRateLimiter()
        self.audit_logger = SecureAuditLogger(self.state_store)

    def evaluate_request(self, request: SecurityRequest) -> Tuple[SecurityDecision, Optional[ActionAuthorization], str]:
        # 1. Check Emergency Stop (Fail Closed)
        if self.state_store.emergency_stop_active:
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.BLOCK, "CRITICAL", target=request.target_domain, result="EMERGENCY_STOP_ACTIVE")
            return SecurityDecision.BLOCK, None, "Emergency stop is active. Autonomous actions blocked."

        # 2. Check Human Takeover
        if not self.takeover.can_agent_act():
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.REQUIRE_USER, "MEDIUM", target=request.target_domain, result="USER_CONTROL_ACTIVE")
            return SecurityDecision.REQUIRE_USER, None, "Browser is under human control. Agent actions paused."

        # 3. Rate Limit Check
        if not self.rate_limiter.check_rate_limit():
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.DENY, "HIGH", target=request.target_domain, result="RATE_LIMIT_EXCEEDED")
            return SecurityDecision.DENY, None, "Action rate limit exceeded. Slowing down."

        # 4. Check Blocked Domains
        domain = request.target_domain.lower() if request.target_domain else "unknown"
        if domain in self.state_store.blocked_domains:
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.BLOCK, "CRITICAL", target=domain, result="DOMAIN_BLOCKED")
            return SecurityDecision.BLOCK, None, f"Domain '{domain}' is explicitly blocked by policy."

        # 5. Check Prompt Injection in Request Context
        if self.prompt_defense.is_injection_threat(request.reason):
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.BLOCK, "CRITICAL", target=domain, result="PROMPT_INJECTION_DETECTED")
            return SecurityDecision.BLOCK, None, "Potential prompt injection detected in request rationale."

        # 6. Map Action Type to Permission Category
        perm_map = {
            "CLICK": PermissionCategory.CLICK,
            "TYPE": PermissionCategory.TYPE,
            "NAVIGATE": PermissionCategory.NAVIGATE,
            "SCROLL": PermissionCategory.SCROLL,
            "PURCHASE": PermissionCategory.PURCHASE,
            "PAY": PermissionCategory.PAY,
            "DELETE": PermissionCategory.DELETE,
            "SUBMIT": PermissionCategory.SUBMIT
        }
        category = perm_map.get(request.action_type.upper(), PermissionCategory.CLICK)

        # 7. Check Autonomy Level & Confirmation Boundary
        if self.state_store.autonomy_level == AutonomyLevel.MANUAL and request.actor != SecurityActor.USER:
            return SecurityDecision.REQUIRE_USER, None, "Autonomy level is set to MANUAL. User must perform all actions."

        if category in [PermissionCategory.PAY, PermissionCategory.PURCHASE, PermissionCategory.DELETE]:
            # High-impact commit actions require explicit confirmation unless pre-authorized
            self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.ALLOW_WITH_CONFIRMATION, "HIGH", target=domain)
            return SecurityDecision.ALLOW_WITH_CONFIRMATION, None, f"Action '{request.action_type}' requires explicit user confirmation."

        # 8. Check Domain Permission
        # Default allow public navigation & harmless interaction on unblocked domains under supervised mode
        if not self.permissions.has_permission(domain, category):
            # Auto-grant low-risk permission if in SUPERVISED/AUTONOMOUS mode and domain is not restricted
            if category in [PermissionCategory.NAVIGATE, PermissionCategory.SCROLL, PermissionCategory.CLICK, PermissionCategory.TYPE]:
                self.permissions.grant_permission(domain, [category], scope=PermissionScope.DOMAIN, ttl_minutes=120)
            else:
                self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.DENY, "HIGH", target=domain, result="PERMISSION_DENIED")
                return SecurityDecision.DENY, None, f"Permission '{category.value}' not granted for domain '{domain}'."

        # 9. Issue Short-Lived ActionAuthorization Token
        auth_id = f"auth_{secrets.token_hex(6)}"
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=30)).isoformat()
        authorization = ActionAuthorization(
            authorization_id=auth_id,
            actor=request.actor,
            workflow_id=request.workflow_id,
            action_id=f"act_{secrets.token_hex(4)}",
            permission=category,
            target_domain=domain,
            state_version=self.state_store.world_model_version,
            policy_version=1,
            expires_at=expires_at,
            nonce=secrets.token_hex(8)
        )
        self.state_store.action_authorizations[auth_id] = authorization
        self.audit_logger.log_security_event(request.actor, request.action_type, SecurityDecision.ALLOW, "LOW", target=domain)

        return SecurityDecision.ALLOW, authorization, "Action authorization granted."

    def validate_action_authorization(self, authorization_id: str, action_id: str) -> Tuple[bool, str]:
        auth = self.state_store.action_authorizations.get(authorization_id)
        if not auth:
            return False, "Authorization token not found or already consumed"

        # Check Expiration
        if datetime.now(timezone.utc) > datetime.fromisoformat(auth.expires_at):
            del self.state_store.action_authorizations[authorization_id]
            return False, "Authorization token has expired"

        # Consume token (Replay Protection)
        del self.state_store.action_authorizations[authorization_id]
        return True, "Authorization token validated and consumed"

security_engine = SecurityPolicyEngine()
