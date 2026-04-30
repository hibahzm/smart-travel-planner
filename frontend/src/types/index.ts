export interface User {
  id: string;
  email: string;
  username: string;
  webhook_url: string | null;
}

export interface ToolCallDetail {
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown> | null;
  error: string | null;
  duration_ms: number | null;
  called_at: string;
}

export interface AgentRun {
  run_id: string;
  query: string;
  response: string | null;
  status: "pending" | "running" | "completed" | "failed";
  token_usage: Record<string, number>;
  tool_calls: ToolCallDetail[];
  started_at: string;
  completed_at: string | null;
}

export interface TokenUsage {
  planner_prompt?: number;
  planner_completion?: number;
  synthesizer_prompt?: number;
  synthesizer_completion?: number;
}

// SSE event types
export type SSEEventType = "tool_start" | "tool_end" | "token" | "done" | "error";

export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  toolCalls?: LiveToolCall[];
  tokenUsage?: TokenUsage;
  runId?: string;
}

export interface LiveToolCall {
  tool: string;
  input?: Record<string, unknown>;
  output?: string;
  duration_ms?: number;
  status: "running" | "done" | "error";
}
