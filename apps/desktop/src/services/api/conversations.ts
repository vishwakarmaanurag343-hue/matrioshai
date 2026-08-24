import { apiRequest } from "./client";
import { Conversation, Message } from "../../types";

export const conversationApi = {
  list: (includeArchived = false): Promise<Conversation[]> =>
    apiRequest<Conversation[]>(`/conversations?include_archived=${includeArchived}`),

  create: (title?: string): Promise<Conversation> =>
    apiRequest<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify({ title: title || "New Conversation" }),
    }),

  get: (id: string): Promise<Conversation> =>
    apiRequest<Conversation>(`/conversations/${id}`),

  update: (id: string, updates: { title?: string; archived?: boolean }): Promise<Conversation> =>
    apiRequest<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),

  delete: (id: string): Promise<void> =>
    apiRequest<void>(`/conversations/${id}`, {
      method: "DELETE",
    }),

  getMessages: (id: string): Promise<Message[]> =>
    apiRequest<Message[]>(`/conversations/${id}/messages`),
};
