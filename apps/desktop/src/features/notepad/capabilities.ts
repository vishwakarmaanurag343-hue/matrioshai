/**
 * Frontend capability table (Slice 1).
 *
 * Mirrors apps/backend/app/notepad/capabilities.py. In slice 1:
 *   - @ai       enabled (executable)
 *   - @browser  recognized but disabled; never executes
 *
 * Adding a new capability here WITHOUT also adding it server-side is a bug.
 * Adding a new capability here with enabled=true WITHOUT a real provider is
 * a bug. The default for any future capability is enabled=false and
 * availability="deferred".
 */

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";
export type CapabilityAvailability = "available" | "unavailable" | "deferred";

export interface Capability {
  id: string;
  provider: string;
  name: string;
  supportedActions: ReadonlyArray<string>;
  riskDefault: RiskLevel;
  requiresApprovalAbove: RiskLevel;
  enabled: boolean;
  availability: CapabilityAvailability;
  deferralMessage?: string;
}

export const CAPABILITIES: Readonly<Record<string, Capability>> = {
  ai: {
    id: "ai",
    provider: "local_llm",
    name: "AI",
    supportedActions: ["summarize", "draft", "rewrite", "research", "extract"],
    riskDefault: "LOW",
    requiresApprovalAbove: "HIGH",
    enabled: true,
    availability: "available",
  },
  browser: {
    id: "browser",
    provider: "browser",
    name: "Browser",
    supportedActions: [],
    riskDefault: "MEDIUM",
    requiresApprovalAbove: "LOW",
    enabled: false,
    availability: "deferred",
    deferralMessage: "Browser capability is not enabled in this phase.",
  },
};

export function getCapability(id: string): Capability | null {
  return CAPABILITIES[id] ?? null;
}

export function isExecutable(id: string): boolean {
  const cap = CAPABILITIES[id];
  return cap !== undefined && cap.enabled;
}
