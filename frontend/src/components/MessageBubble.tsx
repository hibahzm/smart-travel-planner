import { User, Globe, Coins } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { ChatMessage } from "../types";
import ToolCallCard from "./ToolCallCard";
import TripPlanView from "./TripPlanView";
import clsx from "clsx";

interface Props {
  message: ChatMessage;
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <div className="typing-dot" />
      <div className="typing-dot" />
      <div className="typing-dot" />
    </div>
  );
}

function TokenBadge({ usage }: { usage: Record<string, number> }) {
  const totalPrompt = (usage.planner_prompt ?? 0) + (usage.synthesizer_prompt ?? 0);
  const totalCompletion = (usage.planner_completion ?? 0) + (usage.synthesizer_completion ?? 0);
  if (!totalPrompt && !totalCompletion) return null;

  // Rough cost estimate (gpt-4o-mini input $0.15/M, gpt-4o input $2.5/M)
  const plannerCost = ((usage.planner_prompt ?? 0) * 0.00000015) + ((usage.planner_completion ?? 0) * 0.0000006);
  const synthesizerCost = ((usage.synthesizer_prompt ?? 0) * 0.0000025) + ((usage.synthesizer_completion ?? 0) * 0.00001);
  const totalCost = plannerCost + synthesizerCost;

  return (
    <div className="flex items-center gap-3 mt-3 pt-3 border-t border-surface-700 text-xs text-slate-500">
      <div className="flex items-center gap-1">
        <Coins className="w-3 h-3" />
        <span>~${totalCost.toFixed(4)} per query</span>
      </div>
      <span>·</span>
      <span>{totalPrompt + totalCompletion} tokens total</span>
      <span>·</span>
      <span className="text-primary-500">gpt-4o-mini: planning</span>
      <span>·</span>
      <span className="text-accent-500">gpt-4o: synthesis</span>
    </div>
  );
}

export default function MessageBubble({ message }: Props) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end animate-fade-in">
        <div className="flex items-start gap-2 max-w-2xl">
          <div className="bg-primary-700 text-white rounded-2xl rounded-tr-sm px-5 py-3 shadow-lg">
            <p className="text-sm leading-relaxed">{message.content}</p>
          </div>
          <div className="w-7 h-7 bg-primary-600 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
            <User className="w-3.5 h-3.5 text-white" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start animate-slide-up">
      <div className="flex items-start gap-2 max-w-3xl w-full">
        <div className="w-7 h-7 bg-gradient-to-br from-primary-500 to-primary-700 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 shadow-lg shadow-primary-900/30">
          <Globe className="w-3.5 h-3.5 text-white" />
        </div>

        <div className="flex-1 min-w-0">
          {/* Tool call cards — shown while agent is working */}
          {message.toolCalls && message.toolCalls.length > 0 && (
            <div className="space-y-2 mb-3">
              {message.toolCalls.map((tc, i) => (
                <ToolCallCard key={`${tc.tool}-${i}`} toolCall={tc} />
              ))}
            </div>
          )}

          {/* Message content */}
          {message.isStreaming && !message.content ? (
            <div className="glass-card px-4 py-3">
              <TypingIndicator />
            </div>
          ) : message.content ? (
            <div className={clsx("glass-card px-5 py-4", message.isStreaming && "border-primary-700/50")}>
              {message.isStreaming ? (
                <div className="prose-travel">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              ) : (
                <TripPlanView content={message.content} />
              )}
              {!message.isStreaming && message.tokenUsage && (
                <TokenBadge usage={message.tokenUsage as Record<string, number>} />
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
