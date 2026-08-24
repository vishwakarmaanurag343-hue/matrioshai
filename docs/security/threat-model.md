# MATRIOSHAI Security Threat Model (Phase 2)

## 1. System Assets
- **Personal Private Memory**: Core memory facts, recall history, user context.
- **Durable Markdown Notes**: Local Markdown files storing user ideas, documents, and notes.
- **Credentials & API Keys**: LLM provider tokens, user secrets, system credentials.
- **System Integrity & Storage**: Local SQLite database, local file system, network boundaries.

---

## 2. Threat Actors & Threat Scenarios

| Threat Actor | Vector | Threat Scenario |
|---|---|---|
| **Untrusted Content / Document** | Prompt Injection | Notes or external documents containing adversarial strings attempting to override system instructions or exfiltrate credentials. |
| **Malicious Cloud Provider / Man-in-the-Middle** | Exfiltration | Eavesdropping on unredacted sensitive PII or secrets dispatched to cloud endpoints. |
| **Autonomous Model Hijack** | Unauthorized Tool Execution | Model attempting destructive local file removal or unauthorized external actions without user knowledge. |
| **Local Host Compromise** | Local Process Probing | Unauthorized local applications attempting to read secrets from plaintext database or arbitrary file paths. |

---

## 3. Trust Boundaries & Security Controls

```
               +----------------------------------------+
               |        UNTRUSTED EXTERNAL WORLD        |
               |  (Documents, Notes, Web, Messages)     |
               +-------------------+--------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                          SECURITY LAYER                                |
|  +---------------------------+    +---------------------------------+  |
|  |    PRIVACY GATEKEEPER     |    |        PERMISSION ENGINE        |  |
|  |  - PII / Secret Redaction |    |  - Tier 1: Autonomous Read      |  |
|  |  - Cloud vs Local Policy  |    |  - Tier 2: User Approval Req.   |  |
|  |  - Prompt Injection Guard |    |  - Tier 3: Prohibited/Blocked   |  |
|  +-------------+-------------+    +----------------+----------------+  |
|                |                                   |                   |
+----------------|-----------------------------------|-------------------+
                 v                                   v
+---------------------------------+  +-----------------------------------+
|      MODEL CONTEXT BUILDER      |  |        TOOL CONFIRMATION          |
|  [SYSTEM] -> [CORE] -> [UNTRUSTED] |  Interactive Approval Modal       |
+---------------------------------+  +-----------------------------------+
```

### 1. Separation of Intelligence from Capability
The LLM does not possess direct execution handles. Tool requests are evaluated against `ToolRegistry` and `PermissionEngine`. Tier 3 destructive operations are blocked autonomously; Tier 2 external actions require user confirmation.

### 2. Prompt Injection Defense-in-Depth
Retrieved notes, memory items, and external outputs are marked explicitly as `[UNTRUSTED RETRIEVED CONTEXT]`. The system instruction explicitly commands the LLM to treat this context as passive data, never executable instructions.

### 3. Secret Isolation
Secrets and API credentials are stored strictly in isolated OS Keychain storage (`SecretStore`), preventing them from ever entering SQLite, memory records, audit logs, or model prompts.

### 4. Zero-Secret Audit Logging
Every privacy decision, redaction event, tool check, and confirmation resolution is recorded in the structured audit trail with all sensitive parameters masked.

---

## 4. Residual Risks & Future Mitigations (Phase 3+)
- **Indirect Prompt Injection**: Continual refinement of semantic adversarial pattern detectors and token-level sandboxing.
- **Fine-grained Tool Permissions**: Per-domain and per-contact allowlists when Phase 3 introduces Gmail, Slack, and browser tools.
