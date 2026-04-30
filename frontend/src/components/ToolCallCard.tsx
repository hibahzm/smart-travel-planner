import { ChevronDown, ChevronRight, Database, Brain, Wifi, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import type { LiveToolCall } from "../types";
import clsx from "clsx";

const TOOL_META: Record<string, { label: string; Icon: React.ElementType; color: string }> = {
  retrieve_destination_knowledge: {
    label: "Searching knowledge base",
    Icon: Database,
    color: "text-blue-400",
  },
  classify_destination_style: {
    label: "Running ML classifier",
    Icon: Brain,
    color: "text-purple-400",
  },
  fetch_live_conditions: {
    label: "Fetching live conditions",
    Icon: Wifi,
    color: "text-emerald-400",
  },
};

interface Props {
  toolCall: LiveToolCall;
}

export default function ToolCallCard({ toolCall }: Props) {
  const [expanded, setExpanded] = useState(false);
  const meta = TOOL_META[toolCall.tool] ?? { label: toolCall.tool, Icon: Brain, color: "text-slate-400" };

  const statusIcon =
    toolCall.status === "running" ? (
      <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
    ) : toolCall.status === "done" ? (
      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
    ) : (
      <XCircle className="w-4 h-4 text-red-400" />
    );

  let parsedOutput: Record<string, unknown> | null = null;
  if (toolCall.output) {
    try {
      parsedOutput = JSON.parse(toolCall.output);
    } catch {
      parsedOutput = null;
    }
  }

  return (
    <div className="bg-surface-850 border border-surface-700 rounded-xl overflow-hidden text-sm">
      <button
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-800 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <meta.Icon className={clsx("w-4 h-4 flex-shrink-0", meta.color)} />
        <span className="flex-1 text-left text-slate-300 font-medium">{meta.label}</span>
        {toolCall.duration_ms && (
          <span className="text-xs text-slate-500">{toolCall.duration_ms}ms</span>
        )}
        {statusIcon}
        {expanded ? (
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5 text-slate-500" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-surface-700 px-4 py-3 space-y-3 animate-fade-in">
          {toolCall.input && (
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Input</p>
              <pre className="text-xs text-slate-400 bg-surface-900 rounded-lg p-3 overflow-x-auto">
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
          )}

          {parsedOutput && (
            <div>
              <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-1">Output</p>
              <div className="bg-surface-900 rounded-lg p-3 overflow-x-auto">
                {toolCall.tool === "retrieve_destination_knowledge" && parsedOutput.chunks ? (
                  <div className="space-y-2">
                    {(parsedOutput.chunks as Array<{ destination: string; similarity: number; content: string }>)
                      .slice(0, 3)
                      .map((chunk, i) => (
                        <div key={i} className="border-l-2 border-primary-700 pl-2">
                          <p className="text-xs text-primary-400 font-medium">{chunk.destination} (sim: {chunk.similarity})</p>
                          <p className="text-xs text-slate-400 line-clamp-2">{chunk.content}</p>
                        </div>
                      ))}
                  </div>
                ) : toolCall.tool === "classify_destination_style" ? (
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-200">
                      Style: <span className="text-primary-400">{String(parsedOutput.predicted_style)}</span>
                    </p>
                    <p className="text-xs text-slate-400">
                      Confidence: {((parsedOutput.confidence as number) * 100).toFixed(1)}%
                    </p>
                  </div>
                ) : toolCall.tool === "fetch_live_conditions" ? (
                  <div className="space-y-1">
                    {(parsedOutput as any)?.weather && typeof (parsedOutput as any).weather === "object" && (
                      <p className="text-xs text-slate-400">
                        🌡️ {String(((parsedOutput as any).weather as Record<string, unknown>).temp_c)}°C — {String(((parsedOutput as any).weather as Record<string, unknown>).description)}
                      </p>
                    )}
                    {(parsedOutput as any)?.exchange_rate && typeof (parsedOutput as any).exchange_rate === "object" && (
                      <p className="text-xs text-slate-400">
                        💱 {String(((parsedOutput as any).exchange_rate as Record<string, unknown>).meaning)}
                      </p>
                    )}
                    {(parsedOutput as any)?.flights && typeof (parsedOutput as any).flights === "object" && ((parsedOutput as any).flights as Record<string, unknown>).available && (
                      <p className="text-xs text-slate-400">
                        ✈️ From ${String(((parsedOutput as any).flights as Record<string, unknown>).cheapest_usd)} USD
                      </p>
                    )}
                  </div>
                ) : (
                  <pre className="text-xs text-slate-400 overflow-x-auto">
                    {JSON.stringify(parsedOutput, null, 2).slice(0, 400)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
