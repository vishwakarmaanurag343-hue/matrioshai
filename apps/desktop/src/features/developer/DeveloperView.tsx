import React, { useState, useEffect } from "react";
import {
  FolderOpen,
  FileCode,
  Terminal,
  Search,
  GitBranch,
  Play,
  RotateCcw,
  CheckCircle,
  FileText,
  Lock,
  Plus
} from "lucide-react";
import { workspacesApi } from "../../services/api/workspaces";
import {
  Workspace,
  ProjectTreeNode,
  FileContent,
  SearchResultItem,
  GitStatus,
  CommandExecution,
  CodeChangeProposal
} from "../../types";

export const DeveloperView: React.FC = () => {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<string | null>(null);
  const [projectTree, setProjectTree] = useState<ProjectTreeNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  
  // Search & Terminal states
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [commandInput, setCommandInput] = useState("git status");
  const [commandHistory, setCommandHistory] = useState<CommandExecution[]>([]);
  const [gitStatus, setGitStatus] = useState<GitStatus | null>(null);
  const [proposals, setProposals] = useState<CodeChangeProposal[]>([]);
  
  // UI States
  const [bottomTab, setBottomTab] = useState<"terminal" | "git" | "proposals">("terminal");
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [newWsName, setNewWsName] = useState("");
  const [newWsPath, setNewWsPath] = useState("");
  const [showAddModal, setShowAddModal] = useState(false);

  useEffect(() => {
    loadWorkspaces();
  }, []);

  const loadWorkspaces = async () => {
    try {
      const list = await workspacesApi.list();
      setWorkspaces(list);
      if (list.length > 0 && !activeWorkspaceId) {
        selectWorkspace(list[0].id);
      }
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const selectWorkspace = async (id: string) => {
    setActiveWorkspaceId(id);
    setSelectedFile(null);
    setActiveFilePath(null);
    setSearchResults([]);
    try {
      const [tree, git, propList] = await Promise.all([
        workspacesApi.getTree(id),
        workspacesApi.getGitStatus(id),
        workspacesApi.listProposals(id),
      ]);
      setProjectTree(tree);
      setGitStatus(git);
      setProposals(propList);
    } catch (e: any) {
      setErrorMsg(e.message);
    }
  };

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim() || !newWsPath.trim()) return;
    try {
      const created = await workspacesApi.create(newWsName.trim(), newWsPath.trim());
      setShowAddModal(false);
      setNewWsName("");
      setNewWsPath("");
      await loadWorkspaces();
      selectWorkspace(created.id);
    } catch (e: any) {
      setErrorMsg(`Failed to add workspace: ${e.message}`);
    }
  };

  const handleReadFile = async (relPath: string) => {
    if (!activeWorkspaceId) return;
    setLoading(true);
    setActiveFilePath(relPath);
    try {
      const fileData = await workspacesApi.readFile(activeWorkspaceId, relPath);
      setSelectedFile(fileData);
    } catch (e: any) {
      setErrorMsg(`Failed to read file: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchCode = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspaceId || !searchQuery.trim()) return;
    setLoading(true);
    try {
      const results = await workspacesApi.search(activeWorkspaceId, searchQuery.trim());
      setSearchResults(results);
    } catch (e: any) {
      setErrorMsg(`Search failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeWorkspaceId || !commandInput.trim()) return;
    setLoading(true);
    try {
      const exec = await workspacesApi.executeCommand(activeWorkspaceId, commandInput.trim());
      setCommandHistory((prev) => [exec, ...prev]);
      // refresh git status
      const git = await workspacesApi.getGitStatus(activeWorkspaceId);
      setGitStatus(git);
    } catch (e: any) {
      setErrorMsg(`Command error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApplyProposal = async (proposalId: string) => {
    if (!activeWorkspaceId) return;
    try {
      await workspacesApi.applyProposal(activeWorkspaceId, proposalId);
      const updated = await workspacesApi.listProposals(activeWorkspaceId);
      setProposals(updated);
      if (activeFilePath) handleReadFile(activeFilePath);
    } catch (e: any) {
      setErrorMsg(`Apply failed: ${e.message}`);
    }
  };

  const handleRollbackProposal = async (proposalId: string) => {
    if (!activeWorkspaceId) return;
    try {
      await workspacesApi.rollbackProposal(activeWorkspaceId, proposalId);
      const updated = await workspacesApi.listProposals(activeWorkspaceId);
      setProposals(updated);
      if (activeFilePath) handleReadFile(activeFilePath);
    } catch (e: any) {
      setErrorMsg(`Rollback failed: ${e.message}`);
    }
  };

  const activeWs = workspaces.find((w) => w.id === activeWorkspaceId);

  const renderTree = (nodes: ProjectTreeNode[], depth = 0) => {
    return nodes.map((node) => (
      <div key={node.path} style={{ marginLeft: `${depth * 12}px` }}>
        {node.is_dir ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "6px", padding: "3px 6px", fontSize: "12px", color: "var(--text-secondary)" }}>
              <FolderOpen size={13} color="var(--accent-primary)" />
              <strong>{node.name}</strong>
            </div>
            {node.children && renderTree(node.children, depth + 1)}
          </div>
        ) : (
          <div
            onClick={() => handleReadFile(node.path)}
            className={`nav-item ${activeFilePath === node.path ? "active" : ""}`}
            style={{ padding: "3px 6px", fontSize: "12px", gap: "6px", cursor: "pointer" }}
          >
            {node.is_sensitive ? <Lock size={12} color="var(--status-amber)" /> : <FileCode size={12} />}
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{node.name}</span>
          </div>
        )}
      </div>
    ));
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* Top Bar: Workspace Selector & Info */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <Terminal size={20} color="var(--accent-primary)" />
          <select
            value={activeWorkspaceId || ""}
            onChange={(e) => selectWorkspace(e.target.value)}
            style={{ background: "var(--bg-tertiary)", color: "var(--text-primary)", border: "1px solid var(--border-color)", padding: "6px 12px", borderRadius: "6px", outline: "none", fontSize: "13px", fontWeight: 700 }}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>{w.name} ({w.project_type})</option>
            ))}
          </select>
          <button className="action-btn" onClick={() => setShowAddModal(true)} style={{ fontSize: "11px", gap: "4px" }}>
            <Plus size={13} /> Add Workspace
          </button>
        </div>

        {activeWs && (
          <div style={{ display: "flex", alignItems: "center", gap: "16px", fontSize: "12px", color: "var(--text-muted)" }}>
            <span>Framework: <strong>{activeWs.framework || activeWs.project_type}</strong></span>
            <span>Package Manager: <strong>{activeWs.package_manager || "none"}</strong></span>
            {gitStatus && (
              <span style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                <GitBranch size={13} color="var(--accent-primary)" />
                <strong>{gitStatus.branch}</strong> ({gitStatus.is_clean ? "clean" : `${gitStatus.modified.length + gitStatus.untracked.length} changes`})
              </span>
            )}
          </div>
        )}
      </div>

      {errorMsg && (
        <div style={{ padding: "8px 16px", background: "rgba(239, 68, 68, 0.15)", color: "var(--status-red)", fontSize: "12px" }}>
          {errorMsg}
        </div>
      )}

      {/* Main 2-Pane Split: Left (Tree & Search) | Center (File Content) */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {/* Left Side: Tree & Search */}
        <div style={{ width: "280px", borderRight: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", flexDirection: "column" }}>
          {/* Search box */}
          <form onSubmit={handleSearchCode} style={{ padding: "10px", borderBottom: "1px solid var(--border-color)" }}>
            <div style={{ display: "flex", gap: "4px" }}>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search codebase..."
                style={{ flex: 1, background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", padding: "6px 8px", borderRadius: "4px", color: "var(--text-primary)", fontSize: "12px", outline: "none" }}
              />
              <button type="submit" className="action-btn" style={{ padding: "6px 10px" }} title="Search">
                <Search size={13} />
              </button>
            </div>
          </form>

          {/* Tree or Search Results */}
          <div style={{ flex: 1, overflowY: "auto", padding: "10px" }}>
            {searchResults.length > 0 ? (
              <div>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", marginBottom: "8px", display: "flex", justifyContent: "space-between" }}>
                  <span>RESULTS ({searchResults.length})</span>
                  <button onClick={() => setSearchResults([])} style={{ background: "none", border: "none", color: "var(--accent-primary)", cursor: "pointer", fontSize: "10px" }}>Clear</button>
                </div>
                {searchResults.map((r, i) => (
                  <div
                    key={i}
                    onClick={() => handleReadFile(r.file_path)}
                    style={{ padding: "6px", background: "var(--bg-tertiary)", borderRadius: "4px", marginBottom: "6px", cursor: "pointer", fontSize: "11px" }}
                  >
                    <strong>{r.file_path}:{r.line_number}</strong>
                    <div style={{ color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.line_content}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div>
                <div style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-muted)", marginBottom: "8px" }}>PROJECT FILES</div>
                {renderTree(projectTree)}
              </div>
            )}
          </div>
        </div>

        {/* Center Pane: File Viewer */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-primary)" }}>
          {selectedFile ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <div style={{ padding: "8px 16px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", justifyContent: "space-between", fontSize: "12px" }}>
                <span>File: <strong>{selectedFile.path}</strong></span>
                <span style={{ color: "var(--text-muted)" }}>{(selectedFile.size / 1024).toFixed(1)} KB</span>
              </div>
              <pre style={{ flex: 1, margin: 0, padding: "16px", overflowY: "auto", fontFamily: "monospace", fontSize: "12px", lineHeight: "1.5", color: "var(--text-primary)" }}>
                {selectedFile.content}
              </pre>
            </div>
          ) : (
            <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "13px" }}>
              Select a project file on the left to inspect.
            </div>
          )}
        </div>
      </div>

      {/* Bottom Dock: Terminal / Git / Proposals */}
      <div style={{ height: "220px", borderTop: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", flexDirection: "column" }}>
        {/* Dock Subtabs */}
        <div style={{ display: "flex", gap: "8px", padding: "6px 14px", borderBottom: "1px solid var(--border-color)", background: "var(--bg-tertiary)" }}>
          <button className={`nav-item ${bottomTab === "terminal" ? "active" : ""}`} onClick={() => setBottomTab("terminal")} style={{ fontSize: "11px", padding: "4px 8px" }}>
            <Terminal size={13} /> Restricted Terminal
          </button>
          <button className={`nav-item ${bottomTab === "git" ? "active" : ""}`} onClick={() => setBottomTab("git")} style={{ fontSize: "11px", padding: "4px 8px" }}>
            <GitBranch size={13} /> Git Status & Diff
          </button>
          <button className={`nav-item ${bottomTab === "proposals" ? "active" : ""}`} onClick={() => setBottomTab("proposals")} style={{ fontSize: "11px", padding: "4px 8px" }}>
            <FileText size={13} /> Code Proposals ({proposals.length})
          </button>
        </div>

        {/* Dock Content */}
        <div style={{ flex: 1, padding: "10px 14px", overflowY: "auto" }}>
          {bottomTab === "terminal" && (
            <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <form onSubmit={handleRunCommand} style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                <input
                  type="text"
                  value={commandInput}
                  onChange={(e) => setCommandInput(e.target.value)}
                  placeholder="e.g. git status, npm test, pytest, npm run check"
                  style={{ flex: 1, background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", padding: "6px 10px", borderRadius: "4px", color: "var(--text-primary)", fontSize: "12px", fontFamily: "monospace" }}
                />
                <button type="submit" className="new-chat-btn" disabled={loading} style={{ padding: "6px 12px", fontSize: "12px" }}>
                  <Play size={12} /> Run Safe Command
                </button>
              </form>
              <div style={{ flex: 1, overflowY: "auto", fontFamily: "monospace", fontSize: "11px", background: "var(--bg-primary)", padding: "8px", borderRadius: "4px" }}>
                {commandHistory.map((cmd, i) => (
                  <div key={i} style={{ marginBottom: "8px" }}>
                    <div style={{ color: "var(--accent-primary)" }}>$ {cmd.command} (exit: {cmd.exit_code})</div>
                    {cmd.stdout && <pre style={{ margin: "2px 0", color: "var(--text-primary)" }}>{cmd.stdout}</pre>}
                    {cmd.stderr && <pre style={{ margin: "2px 0", color: "var(--status-red)" }}>{cmd.stderr}</pre>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {bottomTab === "git" && gitStatus && (
            <div style={{ fontSize: "12px" }}>
              <div style={{ fontWeight: 700, marginBottom: "6px" }}>Branch: {gitStatus.branch}</div>
              <div style={{ display: "flex", gap: "20px" }}>
                <div>
                  <strong>Modified ({gitStatus.modified.length}):</strong>
                  <ul>{gitStatus.modified.map((f, i) => <li key={i} style={{ color: "var(--status-amber)" }}>{f}</li>)}</ul>
                </div>
                <div>
                  <strong>Untracked ({gitStatus.untracked.length}):</strong>
                  <ul>{gitStatus.untracked.map((f, i) => <li key={i} style={{ color: "var(--status-green)" }}>{f}</li>)}</ul>
                </div>
              </div>
            </div>
          )}

          {bottomTab === "proposals" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {proposals.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>No code change proposals generated yet.</div>
              ) : (
                proposals.map((p) => (
                  <div key={p.id} style={{ background: "var(--bg-tertiary)", padding: "10px", borderRadius: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <strong>{p.title}</strong> ({p.status})
                      <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>Files: {p.files.join(", ")} | Risk: {p.risk_level}</div>
                    </div>
                    <div style={{ display: "flex", gap: "6px" }}>
                      {p.status === "PROPOSED" && (
                        <button className="new-chat-btn" onClick={() => handleApplyProposal(p.id)} style={{ fontSize: "11px", padding: "4px 8px" }}>
                          <CheckCircle size={12} /> Apply Patch
                        </button>
                      )}
                      {p.status === "APPLIED" && (
                        <button className="action-btn" onClick={() => handleRollbackProposal(p.id)} style={{ fontSize: "11px", padding: "4px 8px", color: "var(--status-amber)" }}>
                          <RotateCcw size={12} /> Rollback
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Add Workspace Modal */}
      {showAddModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}>
          <form onSubmit={handleCreateWorkspace} style={{ background: "var(--bg-secondary)", border: "1px solid var(--border-color)", borderRadius: "8px", padding: "20px", width: "420px", display: "flex", flexDirection: "column", gap: "12px" }}>
            <h3 style={{ fontSize: "15px", fontWeight: 700 }}>Add Developer Project Workspace</h3>
            <div>
              <label style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Workspace Name</label>
              <input
                type="text"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                placeholder="e.g. Employee Portal App"
                style={{ width: "100%", background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", padding: "8px", borderRadius: "4px", color: "var(--text-primary)", fontSize: "13px", marginTop: "4px" }}
                required
              />
            </div>
            <div>
              <label style={{ fontSize: "12px", color: "var(--text-secondary)" }}>Absolute Folder Path</label>
              <input
                type="text"
                value={newWsPath}
                onChange={(e) => setNewWsPath(e.target.value)}
                placeholder="e.g. /Users/anurag/Developer/Projects/my_app"
                style={{ width: "100%", background: "var(--bg-tertiary)", border: "1px solid var(--border-color)", padding: "8px", borderRadius: "4px", color: "var(--text-primary)", fontSize: "13px", marginTop: "4px" }}
                required
              />
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "8px" }}>
              <button type="button" className="action-btn" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button type="submit" className="new-chat-btn">Add Workspace</button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
