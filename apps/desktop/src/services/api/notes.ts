import { apiRequest } from "./client";
import { Note } from "../../types";

export const notesApi = {
  list: (query?: string, tag?: string): Promise<Note[]> => {
    const params = new URLSearchParams();
    if (query) params.append("query", query);
    if (tag) params.append("tag", tag);
    const qStr = params.toString() ? `?${params.toString()}` : "";
    return apiRequest<Note[]>(`/notes${qStr}`);
  },

  create: (data: { title: string; content: string; tags?: string[] }): Promise<Note> =>
    apiRequest<Note>("/notes", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  get: (id: string): Promise<Note> =>
    apiRequest<Note>(`/notes/${id}`),

  update: (id: string, updates: { title?: string; content?: string; tags?: string[] }): Promise<Note> =>
    apiRequest<Note>(`/notes/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  delete: (id: string): Promise<void> =>
    apiRequest<void>(`/notes/${id}`, {
      method: "DELETE",
    }),
};
