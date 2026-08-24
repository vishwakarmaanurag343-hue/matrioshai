import { apiRequest } from "./client";
import {
  CommunicationProviderStatus,
  CommunicationConversation,
  CommunicationMessage,
  ReplySuggestion,
  ConversationSummary,
  SendMessageResponse
} from "../../types";

export const communicationApi = {
  getProviders: (): Promise<CommunicationProviderStatus[]> =>
    apiRequest<CommunicationProviderStatus[]>("/communication/providers"),

  listConversations: (): Promise<CommunicationConversation[]> =>
    apiRequest<CommunicationConversation[]>("/communication/conversations"),

  getConversation: (conversationId: string): Promise<CommunicationConversation> =>
    apiRequest<CommunicationConversation>(`/communication/conversations/${conversationId}`),

  getUnread: (): Promise<CommunicationMessage[]> =>
    apiRequest<CommunicationMessage[]>("/communication/unread"),

  searchMessages: (query: string): Promise<CommunicationMessage[]> =>
    apiRequest<CommunicationMessage[]>("/communication/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  summarizeConversation: (conversationId: string): Promise<ConversationSummary> =>
    apiRequest<ConversationSummary>(`/communication/summarize/${conversationId}`, {
      method: "POST",
    }),

  generateReplies: (conversationId: string): Promise<ReplySuggestion> =>
    apiRequest<ReplySuggestion>(`/communication/reply/${conversationId}`, {
      method: "POST",
    }),

  requestSend: (data: { provider: string; conversation_id: string; recipient: string; text: string }): Promise<SendMessageResponse> =>
    apiRequest<SendMessageResponse>("/communication/send", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  approveSend: (confirmation_id: string, sendData: { provider: string; conversation_id: string; recipient: string; text: string }): Promise<SendMessageResponse> =>
    apiRequest<SendMessageResponse>("/communication/approve", {
      method: "POST",
      body: JSON.stringify({
        approval_req: { confirmation_id, approved: true },
        send_req: sendData
      }),
    }),

  emergencyStop: (): Promise<any> =>
    apiRequest<any>("/communication/stop", {
      method: "POST",
    }),
};
