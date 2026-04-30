import { apiClient } from "./client";
import type { AgentRun, SSEEvent } from "../types";

export const agentApi = {
  getHistory: async (page = 1): Promise<{ runs: AgentRun[]; total: number }> => {
    const res = await apiClient.get("/api/history", { params: { page, page_size: 20 } });
    return res.data;
  },

  getRun: async (runId: string): Promise<AgentRun> => {
    const res = await apiClient.get(`/api/history/${runId}`);
    return res.data;
  },

  /**
   * Stream a query via SSE (Server-Sent Events).
   * Calls onEvent for each received event; calls onDone/onError when finished.
   */
  streamQuery: (
    query: string,
    {
      onEvent,
      onDone,
      onError,
    }: {
      onEvent: (event: SSEEvent) => void;
      onDone: () => void;
      onError: (msg: string) => void;
    }
  ): (() => void) => {
    const token = localStorage.getItem("access_token");
    const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

    // Use fetch + ReadableStream for SSE with auth header
    const controller = new AbortController();

    fetch(`${BASE_URL}/api/agent/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        Accept: "text/event-stream",
      },
      body: JSON.stringify({ query }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          const text = await response.text();
          onError(`HTTP ${response.status}: ${text}`);
          return;
        }

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          let currentEvent = "";
          let currentData = "";

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.slice(7).trim();
            } else if (line.startsWith("data: ")) {
              currentData = line.slice(6).trim();
              if (currentEvent && currentData) {
                try {
                  const parsed = JSON.parse(currentData);
                  onEvent({ event: currentEvent as SSEEvent["event"], data: parsed });
                  if (currentEvent === "done") onDone();
                  if (currentEvent === "error") onError(parsed.message ?? "Unknown error");
                } catch {
                  // ignore malformed SSE lines
                }
                currentEvent = "";
                currentData = "";
              }
            }
          }
        }
        onDone();
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          onError(err.message ?? "Connection failed");
        }
      });

    return () => controller.abort();
  },
};
