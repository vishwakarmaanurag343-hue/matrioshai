import { apiRequest } from "./client";
import {
  Workspace,
  ProjectTreeNode,
  FileContent,
  SearchResultItem,
  GitStatus,
  GitDiff,
  CommandExecution,
  CodeChangeProposal
} from "../../types";

export const workspacesApi = {
  list: (): Promise<Workspace[]> =>
    apiRequest<Workspace[]>("/workspaces"),

  create: (name: string, root_path: string): Promise<Workspace> =>
    apiRequest<Workspace>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name, root_path }),
    }),

  getTree: (workspaceId: string): Promise<ProjectTreeNode[]> =>
    apiRequest<ProjectTreeNode[]>(`/workspaces/${workspaceId}/tree`),

  readFile: (workspaceId: string, path: string): Promise<FileContent> =>
    apiRequest<FileContent>(`/workspaces/${workspaceId}/file?path=${encodeURIComponent(path)}`),

  search: (workspaceId: string, query: string): Promise<SearchResultItem[]> =>
    apiRequest<SearchResultItem[]>(`/workspaces/${workspaceId}/search`, {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  getGitStatus: (workspaceId: string): Promise<GitStatus> =>
    apiRequest<GitStatus>(`/workspaces/${workspaceId}/git/status`),

  getGitDiff: (workspaceId: string, filePath?: string): Promise<GitDiff> => {
    const url = filePath
      ? `/workspaces/${workspaceId}/git/diff?file_path=${encodeURIComponent(filePath)}`
      : `/workspaces/${workspaceId}/git/diff`;
    return apiRequest<GitDiff>(url);
  },

  executeCommand: (workspaceId: string, command: string): Promise<CommandExecution> =>
    apiRequest<CommandExecution>(`/workspaces/${workspaceId}/command`, {
      method: "POST",
      body: JSON.stringify({ command }),
    }),

  listProposals: (workspaceId: string): Promise<CodeChangeProposal[]> =>
    apiRequest<CodeChangeProposal[]>(`/workspaces/${workspaceId}/proposals`),

  createProposal: (workspaceId: string, data: { title: string; reason: string; files: string[]; diff_content: string; risk_level?: string }): Promise<CodeChangeProposal> =>
    apiRequest<CodeChangeProposal>(`/workspaces/${workspaceId}/proposals`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  applyProposal: (workspaceId: string, proposalId: string): Promise<CodeChangeProposal> =>
    apiRequest<CodeChangeProposal>(`/workspaces/${workspaceId}/proposals/${proposalId}/apply`, {
      method: "POST",
    }),

  rollbackProposal: (workspaceId: string, proposalId: string): Promise<CodeChangeProposal> =>
    apiRequest<CodeChangeProposal>(`/workspaces/${workspaceId}/proposals/${proposalId}/rollback`, {
      method: "POST",
    }),
};
