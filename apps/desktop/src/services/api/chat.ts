import { Message } from "../../types";
import { API_BASE_URL } from "./client";

export interface ChatResponse {
  conversation_id: string;
  user_message: Message;
  assistant_message: Message;
}

export const chatApi = {
  send: async (prompt: string, conversationId?: string): Promise<ChatResponse> => {
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        conversation_id: conversationId,
        stream: false,
      }),
    });

    if (!response.ok) {
      throw new Error(`Chat request failed: ${response.statusText}`);
    }
    return response.json();
  },

  sendStream: (
    prompt: string,
    conversationId: string | undefined,
    onChunk: (chunk: string) => void,
    onComplete: (asstMsgId: string, fullText: string) => void,
    onError: (err: string) => void
  ) => {
    fetch(`${API_BASE_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt,
        conversation_id: conversationId,
        stream: true,
      }),
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          onError(`HTTP ${response.status}: Local AI stream error`);
          return;
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.type === "chunk") {
                  onChunk(data.content);
                } else if (data.type === "done") {
                  onComplete(data.assistant_message_id, data.full_content);
                }
              } catch (e) {
                // Ignore parse errors on incomplete frames
              }
            }
          }
        }
      })
      .catch((err) => {
        onError(err.message || "Connection to Local AI failed");
      });
  },
};
