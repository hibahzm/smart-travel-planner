import { useState, useCallback, useRef } from "react";
import { agentApi } from "../api/agent";
import type { ChatMessage, LiveToolCall, SSEEvent, TokenUsage } from "../types";

const generateId = () => Math.random().toString(36).slice(2);

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<(() => void) | null>(null);

  const sendMessage = useCallback((query: string) => {
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: query,
    };

    const assistantId = generateId();
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      isStreaming: true,
      toolCalls: [],
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const activeToolCalls = new Map<string, LiveToolCall>();

    const abort = agentApi.streamQuery(query, {
      onEvent: (event: SSEEvent) => {
        setMessages((prev) =>
          prev.map((m) => {
            if (m.id !== assistantId) return m;

            if (event.event === "tool_start") {
              const toolName = event.data.tool as string;
              activeToolCalls.set(toolName, {
                tool: toolName,
                input: event.data.input as Record<string, unknown>,
                status: "running",
              });
              return { ...m, toolCalls: Array.from(activeToolCalls.values()) };
            }

            if (event.event === "tool_end") {
              const toolName = event.data.tool as string;
              const existing = activeToolCalls.get(toolName);
              if (existing) {
                activeToolCalls.set(toolName, {
                  ...existing,
                  output: event.data.output as string,
                  duration_ms: event.data.duration_ms as number,
                  status: "done",
                });
              }
              return { ...m, toolCalls: Array.from(activeToolCalls.values()) };
            }

            if (event.event === "token") {
              return { ...m, content: m.content + (event.data.content as string) };
            }

            if (event.event === "done") {
              return {
                ...m,
                isStreaming: false,
                tokenUsage: event.data.token_usage as TokenUsage,
                runId: event.data.run_id as string,
              };
            }

            if (event.event === "error") {
              return {
                ...m,
                content: `Error: ${event.data.message}`,
                isStreaming: false,
              };
            }

            return m;
          })
        );
      },
      onDone: () => setIsStreaming(false),
      onError: (msg) => {
        setIsStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Something went wrong: ${msg}`, isStreaming: false }
              : m
          )
        );
      },
    });

    abortRef.current = abort;
  }, []);

  const cancelStream = useCallback(() => {
    abortRef.current?.();
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m))
    );
  }, []);

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  return { messages, isStreaming, sendMessage, cancelStream, clearChat };
}
