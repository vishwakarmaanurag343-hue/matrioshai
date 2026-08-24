import React, { useState, useEffect } from "react";
import {
  Users,
  Compass,
  Activity,
  DollarSign,
  Megaphone,
  Code,
  Sparkles,
  History,
  BookmarkPlus,
  RotateCcw,
  Send,
  Loader2
} from "lucide-react";
import { executiveApi } from "../../services/api/executive";
import {
  RoleMetadata,
  ExecutiveRoleType,
  ExecutiveResponse,
  SynthesisResponse,
  DecisionResponse
} from "../../types";

export const ExecutiveView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"workspace" | "history">("workspace");
  const [selectedRole, setSelectedRole] = useState<ExecutiveRoleType | "5C">("5C");
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data states
  const [roles, setRoles] = useState<RoleMetadata[]>([]);
  const [singleResponse, setSingleResponse] = useState<ExecutiveResponse | null>(null);
  const [synthesisResponse, setSynthesisResponse] = useState<SynthesisResponse | null>(null);
  const [decisions, setDecisions] = useState<DecisionResponse[]>([]);

  useEffect(() => {
    executiveApi.getRoles().then(setRoles).catch((e) => setErrorMsg(e.message));
    loadDecisions();
  }, []);

  const loadDecisions = async () => {
    try {
      const list = await executiveApi.listDecisions();
      setDecisions(list);
    } catch (e: any) {
      console.error(e);
    }
  };

  const handleExecuteAnalysis = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    setSingleResponse(null);
    setSynthesisResponse(null);

    try {
      if (selectedRole === "5C") {
        const result = await executiveApi.run5cCouncil(prompt);
        setSynthesisResponse(result);
        loadDecisions();
      } else {
        const result = await executiveApi.analyzeRole(selectedRole, prompt);
        setSingleResponse(result);
      }
    } catch (e: any) {
      setErrorMsg(`Analysis failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handlePromoteToMemory = async (decisionId: string) => {
    try {
      await executiveApi.promoteDecisionToMemory(decisionId);
      setSuccessMsg("Decision promoted to durable Recall Memory!");
      loadDecisions();
    } catch (e: any) {
      setErrorMsg(`Promotion failed: ${e.message}`);
    }
  };

  const handleRevisit = async (decisionId: string) => {
    setLoading(true);
    try {
      const result = await executiveApi.revisitDecision(decisionId);
      setSynthesisResponse(result);
      setActiveTab("workspace");
      loadDecisions();
    } catch (e: any) {
      setErrorMsg(`Revisit failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getRoleIcon = (role: ExecutiveRoleType | "5C") => {
    switch (role) {
      case "CEO": return <Compass size={16} color="#8b5cf6" />;
      case "COO": return <Activity size={16} color="#3b82f6" />;
      case "CFO": return <DollarSign size={16} color="#10b981" />;
      case "CMO": return <Megaphone size={16} color="#f59e0b" />;
      case "CTO": return <Code size={16} color="#06b6d4" />;
      case "5C": return <Users size={16} color="#ec4899" />;
    }
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "24px", overflowY: "auto", gap: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ padding: "8px", background: "rgba(139, 92, 246, 0.15)", borderRadius: "8px" }}>
            <Users size={24} style={{ color: "var(--accent-primary)" }} />
          </div>
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: 700 }}>5C EXECUTIVE INTELLIGENCE</h2>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Multi-perspective reasoning council: CEO, COO, CFO, CMO, and CTO with cross-functional synthesis
            </p>
          </div>
        </div>

        {/* View Toggle */}
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            className={`nav-item ${activeTab === "workspace" ? "active" : ""}`}
            onClick={() => setActiveTab("workspace")}
            style={{ padding: "6px 12px", borderRadius: "6px" }}
          >
            <Sparkles size={14} />
            Executive Workspace
          </button>
          <button
            className={`nav-item ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
            style={{ padding: "6px 12px", borderRadius: "6px" }}
          >
            <History size={14} />
            Decision History ({decisions.length})
          </button>
        </div>
      </div>

      {errorMsg && (
        <div style={{ padding: "10px 14px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)", borderRadius: "6px", fontSize: "13px" }}>
          {errorMsg}
        </div>
      )}

      {successMsg && (
        <div style={{ padding: "10px 14px", background: "rgba(16, 185, 129, 0.15)", color: "var(--status-green)", borderRadius: "6px", fontSize: "13px" }}>
          {successMsg}
        </div>
      )}

      {/* WORKSPACE VIEW */}
      {activeTab === "workspace" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Executive Role Selector */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "10px" }}>
            <div
              onClick={() => setSelectedRole("5C")}
              className={`nav-item ${selectedRole === "5C" ? "active" : ""}`}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "6px",
                padding: "12px",
                borderRadius: "8px",
                border: "1px solid var(--border-color)",
                background: selectedRole === "5C" ? "var(--accent-light)" : "var(--bg-secondary)",
                cursor: "pointer",
              }}
            >
              <Users size={20} color="#ec4899" />
              <strong style={{ fontSize: "13px" }}>@5C Council</strong>
              <span style={{ fontSize: "10px", color: "var(--text-muted)", textAlign: "center" }}>All 5 Perspectives</span>
            </div>

            {roles.map((r) => (
              <div
                key={r.role}
                onClick={() => setSelectedRole(r.role)}
                className={`nav-item ${selectedRole === r.role ? "active" : ""}`}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: "6px",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid var(--border-color)",
                  background: selectedRole === r.role ? "var(--accent-light)" : "var(--bg-secondary)",
                  cursor: "pointer",
                }}
              >
                {getRoleIcon(r.role)}
                <strong style={{ fontSize: "13px" }}>@{r.role}</strong>
                <span style={{ fontSize: "10px", color: "var(--text-muted)", textAlign: "center" }}>{r.focus_areas[0]}</span>
              </div>
            ))}
          </div>

          {/* Prompt Input Box */}
          <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-muted)" }}>
                EXECUTIVE INQUIRY ({selectedRole === "5C" ? "FULL 5C COUNCIL" : `@${selectedRole}`})
              </span>
              <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                Governed by Privacy Gatekeeper
              </span>
            </div>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                selectedRole === "5C"
                  ? "e.g., Should we launch our product next month with the current feature set?"
                  : `e.g., Ask ${selectedRole} specific question regarding ${selectedRole === "CEO" ? "strategy & tradeoffs" : selectedRole === "CFO" ? "unit economics & budget" : selectedRole === "CTO" ? "architecture & scaling" : selectedRole === "COO" ? "execution & timeline" : "growth & messaging"}...`
              }
              rows={3}
              style={{
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border-color)",
                borderRadius: "6px",
                padding: "12px",
                color: "var(--text-primary)",
                resize: "none",
                outline: "none",
                fontSize: "13px",
              }}
            />
            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                className="new-chat-btn"
                onClick={handleExecuteAnalysis}
                disabled={loading || !prompt.trim()}
                style={{ padding: "8px 16px", opacity: loading ? 0.7 : 1 }}
              >
                {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                {loading ? "Analyzing..." : `Run ${selectedRole === "5C" ? "5C Council" : selectedRole} Analysis`}
              </button>
            </div>
          </div>

          {/* SINGLE ROLE RESULT */}
          {singleResponse && (
            <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {getRoleIcon(singleResponse.role)}
                  <h3 style={{ fontSize: "15px", fontWeight: 700 }}>{singleResponse.role} ASSESSMENT</h3>
                </div>
                <span style={{ fontSize: "11px", fontWeight: 800, padding: "2px 8px", borderRadius: "4px", background: "var(--accent-light)", color: "var(--accent-primary)" }}>
                  CONFIDENCE: {singleResponse.confidence}
                </span>
              </div>

              <div style={{ fontSize: "13px", lineHeight: "1.5", background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px" }}>
                <strong>Executive Summary:</strong> {singleResponse.summary}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                <div style={{ background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px" }}>
                  <strong style={{ fontSize: "12px", color: "var(--status-green)" }}>KEY FINDINGS:</strong>
                  <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                    {singleResponse.key_findings.map((f, i) => <li key={i}>{f}</li>)}
                  </ul>
                </div>

                <div style={{ background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px" }}>
                  <strong style={{ fontSize: "12px", color: "var(--status-amber)" }}>ASSUMPTIONS:</strong>
                  <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                    {singleResponse.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>

                <div style={{ background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px" }}>
                  <strong style={{ fontSize: "12px", color: "var(--status-red)" }}>RISKS:</strong>
                  <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                    {singleResponse.risks.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>

                <div style={{ background: "var(--bg-tertiary)", padding: "12px", borderRadius: "6px" }}>
                  <strong style={{ fontSize: "12px", color: "var(--accent-primary)" }}>RECOMMENDATIONS:</strong>
                  <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                    {singleResponse.recommendations.map((rec, i) => <li key={i}>{rec}</li>)}
                  </ul>
                </div>
              </div>

              {singleResponse.missing_information.length > 0 && (
                <div style={{ background: "rgba(245, 158, 11, 0.1)", border: "1px solid rgba(245, 158, 11, 0.3)", padding: "10px 14px", borderRadius: "6px", fontSize: "12px" }}>
                  <strong>Missing Information Surfaced:</strong> {singleResponse.missing_information.join(", ")}
                </div>
              )}
            </div>
          )}

          {/* 5C SYNTHESIS RESULT */}
          {synthesisResponse && (
            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {/* Council Synthesis Card */}
              <div style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <Sparkles size={18} color="var(--accent-primary)" />
                    <h3 style={{ fontSize: "16px", fontWeight: 700 }}>5C CROSS-FUNCTIONAL SYNTHESIS</h3>
                  </div>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Decision Question: {synthesisResponse.question}</span>
                </div>

                <div style={{ background: "var(--bg-tertiary)", padding: "14px", borderRadius: "6px", fontSize: "13px", lineHeight: "1.6" }}>
                  <strong style={{ color: "var(--accent-primary)", display: "block", marginBottom: "4px" }}>FINAL SYNTHESIS RECOMMENDATION:</strong>
                  {synthesisResponse.final_recommendation}
                </div>

                {/* Synthesis Grid: Agreements, Conflicts, Critical Risks, Next Actions */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "12px" }}>
                  <div style={{ background: "rgba(16, 185, 129, 0.08)", border: "1px solid rgba(16, 185, 129, 0.2)", padding: "12px", borderRadius: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "var(--status-green)" }}>CROSS-ROLE AGREEMENTS:</strong>
                    <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                      {synthesisResponse.agreements.map((a, i) => <li key={i}>{a}</li>)}
                    </ul>
                  </div>

                  <div style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)", padding: "12px", borderRadius: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "var(--status-red)" }}>CONFLICTS & TRADEOFFS:</strong>
                    <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                      {synthesisResponse.conflicts.map((c, i) => <li key={i}>{c}</li>)}
                    </ul>
                  </div>

                  <div style={{ background: "rgba(245, 158, 11, 0.08)", border: "1px solid rgba(245, 158, 11, 0.2)", padding: "12px", borderRadius: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "var(--status-amber)" }}>CRITICAL RISKS:</strong>
                    <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                      {synthesisResponse.critical_risks.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>

                  <div style={{ background: "rgba(139, 92, 246, 0.08)", border: "1px solid rgba(139, 92, 246, 0.2)", padding: "12px", borderRadius: "6px" }}>
                    <strong style={{ fontSize: "12px", color: "var(--accent-primary)" }}>NEXT ACTIONS:</strong>
                    <ul style={{ fontSize: "12px", margin: "6px 0 0 16px", padding: 0 }}>
                      {synthesisResponse.next_actions.map((na, i) => <li key={i}>{na}</li>)}
                    </ul>
                  </div>
                </div>
              </div>

              {/* Individual 5C Assessments Cards */}
              <h4 style={{ fontSize: "14px", fontWeight: 700, margin: "10px 0 0 4px" }}>INDIVIDUAL 5C ASSESSMENTS</h4>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "12px" }}>
                {Object.entries(synthesisResponse.executive_assessments).map(([roleKey, assessment]) => (
                  <div key={roleKey} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "14px", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                        {getRoleIcon(roleKey as ExecutiveRoleType)}
                        <strong>{roleKey}</strong>
                      </div>
                      <span style={{ fontSize: "10px", fontWeight: 800, padding: "2px 6px", borderRadius: "4px", background: "var(--bg-tertiary)", color: "var(--text-muted)" }}>
                        {assessment.confidence} CONFIDENCE
                      </span>
                    </div>
                    <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>{assessment.summary}</div>
                    <div style={{ fontSize: "11px", color: "var(--accent-primary)", marginTop: "4px" }}>
                      Recommendation: {assessment.recommendations[0] || "None"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* DECISION HISTORY VIEW */}
      {activeTab === "history" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          {decisions.length === 0 ? (
            <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px", background: "var(--bg-secondary)", borderRadius: "8px" }}>
              No decisions recorded yet. Run a @5C Council query to generate and track decisions.
            </div>
          ) : (
            decisions.map((d) => (
              <div
                key={d.id}
                style={{
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-color)",
                  borderRadius: "8px",
                  padding: "16px",
                  display: "flex",
                  flexDirection: "column",
                  gap: "10px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong style={{ fontSize: "14px" }}>{d.title}</strong>
                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>Question: {d.question}</div>
                  </div>
                  <span
                    style={{
                      fontSize: "11px",
                      fontWeight: 800,
                      padding: "3px 8px",
                      borderRadius: "4px",
                      background: d.status === "DECIDED" ? "rgba(16, 185, 129, 0.15)" : d.status === "REVISIT" ? "rgba(245, 158, 11, 0.2)" : "var(--accent-light)",
                      color: d.status === "DECIDED" ? "var(--status-green)" : d.status === "REVISIT" ? "var(--status-amber)" : "var(--accent-primary)",
                    }}
                  >
                    STATUS: {d.status}
                  </span>
                </div>

                {d.final_recommendation && (
                  <div style={{ fontSize: "12px", background: "var(--bg-tertiary)", padding: "10px", borderRadius: "6px" }}>
                    <strong>Recommendation:</strong> {d.final_recommendation}
                  </div>
                )}

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "4px" }}>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    Logged: {new Date(d.created_at).toLocaleDateString()}
                  </span>
                  <div style={{ display: "flex", gap: "8px" }}>
                    <button
                      className="action-btn"
                      onClick={() => handlePromoteToMemory(d.id)}
                      title="Convert to durable recall memory"
                      style={{ fontSize: "11px", gap: "4px" }}
                    >
                      <BookmarkPlus size={13} color="var(--status-green)" />
                      Promote to Memory
                    </button>
                    <button
                      className="action-btn"
                      onClick={() => handleRevisit(d.id)}
                      title="Re-run 5C council with latest context"
                      style={{ fontSize: "11px", gap: "4px" }}
                    >
                      <RotateCcw size={13} color="var(--accent-primary)" />
                      Revisit Decision
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
