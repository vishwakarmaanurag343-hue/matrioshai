# MATRIOSHAI Phase 2 — Security Review & Hardening Scorecard

## 1. Executive Summary
- **Implementation Status**: `SECURE FOUNDATION`
- **Phase 3 Recommendation**: `APPROVE`
- **Total Test Cases**: 20/20 automated tests passing (Regression + Security Core + Adversarial Injections)

---

## 2. Security Category Scorecard

| Category | Status | Evidence & Enforcement | Risk Assessment | Hardening Recommendation |
|---|---|---|---|---|
| **Privacy Gate** | **PASS** | `ConversationService.build_llm_messages` routes 100% of prompts through `ContextBuilder` and `PrivacyGatekeeper`. | Low (No bypass paths found) | Enforce gateway enforcement at API middleware level in Phase 3. |
| **Secrets Isolation** | **PASS WITH LIMITATIONS** | `SecretStore` isolates secrets from SQLite, memory, and prompts. In production without `keyring`, memory fallback is used. | Medium (Fallback memory store volatile) | Ensure OS keychain packaging in Tauri production sidecar. |
| **PII Redaction** | **PASS** | Regex & entity detection for Email, Phone, API Keys, SSH keys, IP, Credit Cards. Masking occurs before cloud context dispatch. | Low | Expand Presidio NLP named-entity recognition in future cloud packs. |
| **Prompt Injection** | **PASS WITH LIMITATIONS** | Structurally isolates `[UNTRUSTED RETRIEVED CONTEXT]` from `[SYSTEM INSTRUCTIONS]`. Scans for override heuristics. | Medium (Indirect prompt injection cannot be 100% solved by heuristics alone) | Maintain architectural boundary: untrusted data must NEVER execute commands directly. |
| **Tool Permissions** | **PASS** | `ToolRegistry` enforces Tier 1 (Autonomous), Tier 2 (Approval Required), Tier 3 (Prohibited). Unknown tools default to Deny. | Low | Maintain strict whitelist. |
| **Confirmation System** | **PASS** | `ConfirmationSystem` binds approvals to SHA-256 parameter hashes, preventing replay attacks and post-approval parameter tampering. | Low | Verified replay and parameter tampering defense. |
| **Filesystem Security** | **PASS** | `FileAccessPolicy` and `NotesService` use `os.path.realpath` ensuring symlinks and relative traversals cannot escape `matrioshai/data/`. | Low | Keep strict root allowlist. |
| **Local API Security** | **PASS WITH LIMITATIONS** | FastAPI binds strictly to `127.0.0.1`. CORS is open for localhost desktop context. Local token auth not yet enabled. | Medium (Other local apps on localhost could connect) | Add shared localhost session secret between Tauri and FastAPI in Phase 3. |
| **Audit Logging** | **PASS** | `AuditLogger` records all security events with automatic redaction of secret parameters. | Low | Zero secrets recorded in audit tables. |
| **Memory Isolation** | **PASS** | Memory retrieval is classified, filtered, and tagged as untrusted context before prompt delivery. | Low | Verified. |
| **Data Classification** | **PASS** | 5 tiers (`PUBLIC`, `INTERNAL`, `PRIVATE`, `SENSITIVE`, `SECRET`) actively govern local vs cloud dispatch. | Low | Classification directly changes redaction rules. |

---

## 3. Vulnerability Findings & Resolved Hardening

1. **Symlink Directory Escape (RESOLVED)**:
   - *Finding*: `Path.resolve()` did not completely prevent symlinks created inside `data/notes/` from pointing to external sensitive files like `/etc/passwd`.
   - *Fix*: Integrated `os.path.realpath` checking target canonical destination against canonical allowed roots.
2. **Approval Replay & Tampering (RESOLVED)**:
   - *Finding*: A resolved confirmation could theoretically be replayed or resolved with modified parameters.
   - *Fix*: Added parameter hashing (`SHA-256`) and resolved request tracking to reject replays and parameter mutations.
3. **Prompt Injection Boundary (RESOLVED)**:
   - *Finding*: Retrieved notes previously appeared in system context without explicit untrusted data demarcation.
   - *Fix*: ContextBuilder encloses retrieved data in `[UNTRUSTED RETRIEVED CONTEXT]` tags and system prompt commands LLM not to execute embedded instructions.

---

## 4. Final Verdict
Phase 2 Security, Privacy & Control Foundation is hardened and verified.
**Phase 3 Recommendation**: `APPROVE`
