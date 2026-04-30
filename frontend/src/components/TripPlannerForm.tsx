import { useState, useCallback, useRef } from "react";
import {
  Sparkles,
  StopCircle,
  RotateCcw,
  ArrowRight,
  CheckCircle2,
  Loader2,
  Coins,
} from "lucide-react";
import { agentApi } from "../api/agent";
import type { LiveToolCall, SSEEvent } from "../types";
import TripPlanView from "./TripPlanView";
import ToolCallCard from "./ToolCallCard";

const QUICK_PROMPTS = [
  "2 weeks in July, $1,500 budget, warm and not touristy, love hiking",
  "Best budget beach in Southeast Asia, 10 days under $800",
  "Cultural city trip in Europe in October, love architecture and food",
  "Safari experience under $3,000 for 2 weeks",
];

const TRAVEL_STYLES = [
  { label: "Adventure", emoji: "🏔️" },
  { label: "Relaxation", emoji: "🏖️" },
  { label: "Culture", emoji: "🎭" },
  { label: "Family", emoji: "👨‍👩‍👧" },
  { label: "Luxury", emoji: "💎" },
  { label: "Budget", emoji: "💸" },
];

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

type Status = "idle" | "loading" | "done" | "error";

function buildQuery(
  text: string,
  budget: string,
  duration: string,
  unit: string,
  month: string,
  styles: string[]
): string {
  const parts = [text.trim()].filter(Boolean);
  if (budget) parts.push(`Budget: $${budget}`);
  if (duration) parts.push(`Duration: ${duration} ${unit}`);
  if (month) parts.push(`Travel month: ${month}`);
  if (styles.length > 0) parts.push(`Preferred style: ${styles.join(", ")}`);
  return parts.join(" · ");
}

export default function TripPlannerForm() {
  const [query, setQuery] = useState("");
  const [budget, setBudget] = useState("");
  const [duration, setDuration] = useState("");
  const [durationUnit, setDurationUnit] = useState<"days" | "weeks">("weeks");
  const [month, setMonth] = useState("");
  const [styles, setStyles] = useState<string[]>([]);

  const [status, setStatus] = useState<Status>("idle");
  const [toolCalls, setToolCalls] = useState<Map<string, LiveToolCall>>(new Map());
  const [response, setResponse] = useState("");
  const [tokenUsage, setTokenUsage] = useState<Record<string, number> | null>(null);
  const [errorMsg, setErrorMsg] = useState("");
  const abortRef = useRef<(() => void) | null>(null);

  const handleSubmit = useCallback(() => {
    const finalQuery = buildQuery(query, budget, duration, durationUnit, month, styles);
    if (!finalQuery.trim()) return;

    setStatus("loading");
    setToolCalls(new Map());
    setResponse("");
    setTokenUsage(null);
    setErrorMsg("");

    const activeToolCalls = new Map<string, LiveToolCall>();

    const abort = agentApi.streamQuery(finalQuery, {
      onEvent: (event: SSEEvent) => {
        if (event.event === "tool_start") {
          const name = event.data.tool as string;
          activeToolCalls.set(name, {
            tool: name,
            input: event.data.input as Record<string, unknown>,
            status: "running",
          });
          setToolCalls(new Map(activeToolCalls));
        }
        if (event.event === "tool_end") {
          const name = event.data.tool as string;
          const existing = activeToolCalls.get(name);
          if (existing) {
            activeToolCalls.set(name, {
              ...existing,
              output: event.data.output as string,
              duration_ms: event.data.duration_ms as number,
              status: "done",
            });
          }
          setToolCalls(new Map(activeToolCalls));
        }
        if (event.event === "token") {
          setResponse((prev) => prev + (event.data.content as string));
        }
        if (event.event === "done") {
          setTokenUsage(event.data.token_usage as Record<string, number>);
          setStatus("done");
        }
        if (event.event === "error") {
          setErrorMsg((event.data.message as string) || "Something went wrong");
          setStatus("error");
        }
      },
      onDone: () => {},
      onError: (msg) => {
        setErrorMsg(msg);
        setStatus("error");
      },
    });

    abortRef.current = abort;
  }, [query, budget, duration, durationUnit, month, styles]);

  const handleReset = () => {
    abortRef.current?.();
    setStatus("idle");
    setResponse("");
    setToolCalls(new Map());
    setTokenUsage(null);
    setErrorMsg("");
    setQuery("");
    setBudget("");
    setDuration("");
    setMonth("");
    setStyles([]);
  };

  const toggleStyle = (label: string) =>
    setStyles((prev) =>
      prev.includes(label) ? prev.filter((s) => s !== label) : [...prev, label]
    );

  const canSubmit = !!(query.trim() || budget || duration || month || styles.length > 0);

  const totalTokens = tokenUsage
    ? Object.values(tokenUsage).reduce((a, b) => a + b, 0)
    : 0;
  const totalCost = tokenUsage
    ? (tokenUsage.planner_prompt ?? 0) * 0.00000015 +
      (tokenUsage.planner_completion ?? 0) * 0.0000006 +
      (tokenUsage.synthesizer_prompt ?? 0) * 0.0000025 +
      (tokenUsage.synthesizer_completion ?? 0) * 0.00001
    : 0;

  /* ── Result view ─────────────────────────────────────── */
  if (status === "done" && response) {
    return (
      <div className="flex flex-col h-full overflow-y-auto">
        <div className="px-4 lg:px-8 py-6">
          <div className="max-w-3xl mx-auto">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-semibold text-slate-100">Your Trip Plan</h2>
              </div>
              <button
                onClick={handleReset}
                className="btn-ghost flex items-center gap-2 text-sm"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Plan Another Trip
              </button>
            </div>

            {toolCalls.size > 0 && (
              <div className="space-y-2 mb-4">
                {Array.from(toolCalls.values()).map((tc, i) => (
                  <ToolCallCard key={i} toolCall={tc} />
                ))}
              </div>
            )}

            <div className="glass-card px-5 py-5">
              <TripPlanView content={response} />
              {tokenUsage && (
                <div className="flex items-center gap-3 mt-4 pt-4 border-t border-surface-700 text-xs text-slate-500">
                  <Coins className="w-3 h-3" />
                  <span>~${totalCost.toFixed(4)}</span>
                  <span>·</span>
                  <span>{totalTokens.toLocaleString()} tokens</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  /* ── Loading view ────────────────────────────────────── */
  if (status === "loading") {
    return (
      <div className="flex flex-col h-full items-center justify-center px-4">
        <div className="w-full max-w-lg">
          <div className="flex items-center gap-3 mb-5">
            <Loader2 className="w-5 h-5 text-primary-400 animate-spin flex-shrink-0" />
            <h2 className="text-base font-medium text-slate-200">
              {response ? "Writing your trip plan…" : "Researching your trip…"}
            </h2>
            <button
              onClick={() => {
                abortRef.current?.();
                setStatus("idle");
              }}
              className="ml-auto flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              <StopCircle className="w-3.5 h-3.5" />
              Cancel
            </button>
          </div>

          <div className="space-y-2">
            {toolCalls.size > 0 ? (
              Array.from(toolCalls.values()).map((tc, i) => (
                <ToolCallCard key={i} toolCall={tc} />
              ))
            ) : (
              <div className="glass-card px-4 py-3 text-sm text-slate-500 animate-pulse">
                Connecting to research tools…
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ── Form view (idle / error) ────────────────────────── */
  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <div className="px-4 lg:px-8 py-8">
        <div className="max-w-2xl mx-auto animate-fade-in">

          {/* Hero */}
          <div className="text-center mb-8">
            <div className="w-14 h-14 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-2xl shadow-primary-900/40">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-semibold text-slate-100 mb-2">
              Plan Your Next Adventure
            </h1>
            <p className="text-slate-400 text-sm max-w-sm mx-auto">
              Describe your ideal trip and the agent will research destinations,
              check live conditions, and write a personalised plan.
            </p>
          </div>

          {/* Main text input */}
          <div className="glass-card p-4 mb-4 focus-within:border-primary-600/50 transition-colors">
            <textarea
              rows={3}
              className="w-full bg-transparent text-slate-100 placeholder-slate-500 resize-none focus:outline-none text-sm leading-relaxed"
              placeholder="Where do you want to go? Describe your ideal trip — destination, vibe, interests…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && e.ctrlKey) handleSubmit();
              }}
            />
            {!query && (
              <div className="mt-3 pt-3 border-t border-surface-700">
                <p className="text-xs text-slate-600 mb-2">Quick start:</p>
                <div className="flex flex-wrap gap-2">
                  {QUICK_PROMPTS.map((p, i) => (
                    <button
                      key={i}
                      onClick={() => setQuery(p)}
                      className="text-xs px-3 py-1.5 rounded-lg bg-surface-800 hover:bg-surface-700 text-slate-400 hover:text-slate-200 transition-colors text-left"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Optional details */}
          <div className="glass-card p-4 mb-5 space-y-4">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
              Optional details
            </p>

            <div className="grid grid-cols-3 gap-3">
              {/* Budget */}
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Budget (USD)</label>
                <div className="flex items-center gap-1 bg-surface-800 border border-surface-700 rounded-xl px-3 py-2">
                  <span className="text-slate-500 text-sm">$</span>
                  <input
                    type="number"
                    placeholder="1500"
                    value={budget}
                    onChange={(e) => setBudget(e.target.value)}
                    className="bg-transparent text-slate-100 placeholder-slate-600 focus:outline-none text-sm w-full"
                  />
                </div>
              </div>

              {/* Duration */}
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Duration</label>
                <div className="flex gap-1.5">
                  <input
                    type="number"
                    placeholder="2"
                    value={duration}
                    onChange={(e) => setDuration(e.target.value)}
                    className="bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-slate-100 placeholder-slate-600 focus:outline-none text-sm flex-1 min-w-0"
                  />
                  <button
                    onClick={() =>
                      setDurationUnit((u) => (u === "days" ? "weeks" : "days"))
                    }
                    className="text-xs px-2.5 py-2 rounded-xl bg-surface-800 border border-surface-700 text-slate-400 hover:text-slate-200 hover:bg-surface-700 transition-colors whitespace-nowrap"
                  >
                    {durationUnit}
                  </button>
                </div>
              </div>

              {/* Month */}
              <div>
                <label className="text-xs text-slate-500 mb-1.5 block">Month</label>
                <select
                  value={month}
                  onChange={(e) => setMonth(e.target.value)}
                  className="w-full bg-surface-800 border border-surface-700 rounded-xl px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  style={{ colorScheme: "dark" }}
                >
                  <option value="">Any time</option>
                  {MONTHS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Style chips */}
            <div>
              <label className="text-xs text-slate-500 mb-2 block">Travel style</label>
              <div className="flex flex-wrap gap-2">
                {TRAVEL_STYLES.map(({ label, emoji }) => (
                  <button
                    key={label}
                    onClick={() => toggleStyle(label)}
                    className={`text-xs px-3 py-1.5 rounded-full border transition-all duration-150 ${
                      styles.includes(label)
                        ? "bg-primary-700/50 border-primary-600/60 text-primary-200"
                        : "bg-surface-800 border-surface-700 text-slate-400 hover:text-slate-200 hover:bg-surface-700"
                    }`}
                  >
                    {emoji} {label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Error */}
          {status === "error" && errorMsg && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-red-900/20 border border-red-800/50 text-red-300 text-sm flex items-center justify-between">
              <span>{errorMsg}</span>
              <button
                onClick={() => {
                  setStatus("idle");
                  setErrorMsg("");
                }}
                className="text-xs underline ml-3 opacity-70 hover:opacity-100"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Submit */}
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="btn-primary w-full flex items-center justify-center gap-2 text-base py-3"
          >
            Generate Trip Plan
            <ArrowRight className="w-4 h-4" />
          </button>

          <div className="mt-5 flex items-center justify-center gap-5 text-xs text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
              RAG Knowledge Base
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-purple-500 rounded-full" />
              ML Style Classifier
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />
              Live Conditions
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
