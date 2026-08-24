/**
 * Prompt Injection & Credential Defense Layer
 * Treats all web content as untrusted input and prevents adversarial overrides.
 */

const INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?(previous|prior|above)\s+instructions/i,
  /disregard\s+(all\s+)?(previous|prior)\s+rules/i,
  /system\s+prompt\s+override/i,
  /you\s+are\s+now\s+in\s+developer\s+mode/i,
  /reveal\s+(your\s+)?(system\s+prompt|instructions|secret|api_key|password)/i,
  /send\s+(all\s+)?(passwords|credentials|cookies|tokens)\s+to/i,
  /exfiltrate/i,
  /execute\s+javascript\s*:\s*eval/i,
  /bypass\s+safety\s+filter/i,
];

const SECRET_PATTERNS = [
  /(?:api[_-]?key|secret|token|bearer|auth[_-]?token)[\s:=]+([A-Za-z0-9_\-]{16,})/gi,
  /(?:password|passwd|pwd)[\s:=]+([^\s,;]{6,})/gi,
  /sk-[a-zA-Z0-9]{20,}/g,
  /nvapi-[a-zA-Z0-9\-_]{30,}/g,
];

export class PromptInjectionGuard {
  /**
   * Sanitizes text extracted from third-party webpages before passing to LLM context.
   */
  static sanitizeWebContent(text: string): { safeText: string; injectionDetected: boolean } {
    if (!text) return { safeText: "", injectionDetected: false };

    let sanitized = text;
    let injectionDetected = false;

    // 1. Check for prompt injection attempts in webpage text
    for (const pattern of INJECTION_PATTERNS) {
      if (pattern.test(sanitized)) {
        injectionDetected = true;
        sanitized = sanitized.replace(pattern, "[UNTRUSTED_PAGE_INSTRUCTION_BLOCKED]");
      }
    }

    // 2. Redact passwords and API tokens
    for (const pattern of SECRET_PATTERNS) {
      sanitized = sanitized.replace(pattern, "[REDACTED_SECRET]");
    }

    return { safeText: sanitized, injectionDetected };
  }

  /**
   * Evaluates an agent action against safety policies.
   */
  static isActionPermitted(action: string, target?: string, isApproved: boolean = false): {
    allowed: boolean;
    reason?: string;
    requiresApproval: boolean;
  } {
    const act = action.toUpperCase();

    // Critical Actions: Always require explicit human authorization
    if (["PAYMENT", "PURCHASE", "DELETE_ACCOUNT", "SUBMIT_FORM"].includes(act)) {
      if (!isApproved) {
        return {
          allowed: false,
          reason: `Action '${act}' requires explicit human verification and confirmation.`,
          requiresApproval: true,
        };
      }
    }

    // Prevent navigation to malicious protocols
    if (act === "NAVIGATE" && target) {
      const lower = target.toLowerCase();
      if (lower.startsWith("javascript:") || lower.startsWith("data:") || lower.startsWith("file:")) {
        return {
          allowed: false,
          reason: `Security Block: Navigation to protocol '${target.split(":")[0]}' is prohibited.`,
          requiresApproval: false,
        };
      }
    }

    return { allowed: true, requiresApproval: false };
  }
}
