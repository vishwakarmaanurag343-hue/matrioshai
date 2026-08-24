# MATRIOSHAI Security & Permissions Matrix

| Action / Capability | Required Permission | Authorization Source | Risk Level | Confirmation Required | Audit Log Required | Status |
|---|---|---|---|---|---|---|
| **`PAGE_OBSERVE`** | `PAGE_READ` | Agent / System Policy | Low | No | No | 🟢 ENFORCED |
| **`BROWSER_NAVIGATE`** | `NAVIGATION` | Agent / Domain Trust | Low | No | Yes | 🟢 ENFORCED |
| **`CLICK` (Standard Navigation)** | `DOM_INTERACTION` | Agent / Security Gate | Low | No | Yes | 🟢 ENFORCED |
| **`TYPE` (Non-Sensitive Input)** | `FORM_INPUT` | Agent / Security Gate | Medium | No | Yes | 🟢 ENFORCED |
| **`TYPE` (Passwords / Credentials)** | `CREDENTIAL_ACCESS` | User Approval Only | High | Yes | Yes (Redacted) | 🟢 ENFORCED |
| **`PAY` / `PURCHASE` / `BOOK`** | `FINANCIAL_TRANSACTION` | User Explicit Confirmation | Critical | Yes (Interactive Modal) | Yes (Immutable) | 🟢 ENFORCED |
| **`DELETE_ACCOUNT` / `RESET`** | `ACCOUNT_MANAGEMENT` | User Explicit Confirmation | High | Yes | Yes | 🟢 ENFORCED |
| **Arbitrary Code Execution** | *FORBIDDEN* | None (Forbidden in Architecture) | Critical | Blocked by Design | Blocked | 🟢 BLOCKED |
| **Arbitrary File Upload/Download** | *FORBIDDEN* | None (Forbidden in Architecture) | Critical | Blocked by Design | Blocked | 🟢 BLOCKED |
| **Emergency Stop Kill Switch** | `ADMIN_OVERRIDE` | User Takeover / Safety Center | Immediate | Immediate Action | Yes | 🟢 ENFORCED |
