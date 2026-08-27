/**
 * MATRIOSHAI — Zero-Trust Security Kernel V2 (Phase 8F).
 *
 * Independent security and policy kernel sitting OUTSIDE the LLM reasoning loop.
 * Validates proposed AgentDecisions before dispatch, sanitizes untrusted webpage
 * content, and enforces strict boundary policies.
 */

import { AgentDecision, RobustElement } from "../types";

export interface SecurityPolicyCheck {
  allowed: boolean;
  riskLevel: "ReadOnly" | "Low" | "Medium" | "High" | "Critical";
  reason: string;
  sanitizedValue?: string;
  requiresApproval?: boolean;
}

export interface SecurityKernelOptions {
  allowedDomains?: string[];
  blockedDomains?: string[];
  allowDownloads?: boolean;
  maxDailyTransactions?: number;
}

export class SecurityKernel {
  private static instance: SecurityKernel;

  // Patterns indicating malicious indirect prompt injection inside web page text
  private static readonly INJECTION_PATTERNS = [
    /ignore\s+(previous|all|system)\s+(instructions|prompts|rules)/i,
    /reveal\s+(your\s+)?(system\s+prompt|credentials|passwords|api\s+keys)/i,
    /upload\s+(credentials|passwords|files|cookies|secrets)/i,
    /download\s+(executable|malware|binary|script)/i,
    /you\s+are\s+now\s+(a|an)\s+unrestricted/i,
    /new\s+task:\s*disregard/i,
    /bypass\s+(security|approval|kernel|gate)/i,
  ];

  private options: SecurityKernelOptions = {
    allowDownloads: false,
    maxDailyTransactions: 5,
  };

  public static getInstance(): SecurityKernel {
    if (!SecurityKernel.instance) {
      SecurityKernel.instance = new SecurityKernel();
    }
    return SecurityKernel.instance;
  }

  /**
   * Sanitizes raw scraped webpage text to neutralize indirect prompt injection attacks.
   */
  public sanitizeScrapedText(rawText: string): { safeText: string; redactedCount: number } {
    let safeText = rawText;
    let redactedCount = 0;

    for (const pattern of SecurityKernel.INJECTION_PATTERNS) {
      if (pattern.test(safeText)) {
        safeText = safeText.replace(pattern, "[UNTRUSTED_INDIRECT_INSTRUCTION_REDACTED]");
        redactedCount++;
      }
    }

    return { safeText, redactedCount };
  }

  /**
   * Evaluates an agent decision against the Zero-Trust policy kernel.
   */
  public validateProposedAction(
    decision: AgentDecision,
    targetElement?: RobustElement,
    _currentUrl?: string
  ): SecurityPolicyCheck {
    const actUpper = decision.action.toUpperCase();

    // 1. Sensitive input protection
    if (actUpper === "TYPE") {
      if (targetElement?.sensitive || targetElement?.inputType === "password") {
        return {
          allowed: false,
          riskLevel: "Critical",
          reason: "SECURITY POLICY BLOCKED: Autonomous typing into sensitive password fields is prohibited. Human takeover required.",
        };
      }

      // Check typed value for prompt injection artifacts
      if (decision.value) {
        const { redactedCount } = this.sanitizeScrapedText(decision.value);
        if (redactedCount > 0) {
          return {
            allowed: false,
            riskLevel: "High",
            reason: "SECURITY POLICY BLOCKED: Proposed TYPE value contained suspicious prompt injection payload.",
          };
        }
      }
    }

    // 2. Financial / Irreversible Action Gate
    if (decision.requires_approval) {
      return {
        allowed: true,
        riskLevel: "Critical",
        requiresApproval: true,
        reason: "ACTION REQUIRES APPROVAL: Irreversible or financial action proposed. Approval gate engaged.",
      };
    }

    // 3. Domain policy check
    if (actUpper === "NAVIGATE" && decision.target) {
      try {
        const targetHost = new URL(decision.target).hostname.toLowerCase();
        if (this.options.blockedDomains?.some((b) => targetHost.includes(b))) {
          return {
            allowed: false,
            riskLevel: "Critical",
            reason: `SECURITY POLICY BLOCKED: Navigation to blocked domain '${targetHost}' is forbidden.`,
          };
        }
      } catch {
        // Invalid URL handled by runtime
      }
    }

    // Default: Passed policy kernel
    return {
      allowed: true,
      riskLevel: actUpper === "NAVIGATE" || actUpper === "CLICK" ? "Low" : "ReadOnly",
      reason: "Action passed Zero-Trust Security Kernel checks.",
    };
  }
}

export const securityKernel = SecurityKernel.getInstance();
