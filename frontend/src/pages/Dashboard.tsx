import { useState } from "react";
import Header from "../components/Header";
import Sidebar from "../components/Sidebar";
import TripPlannerForm from "../components/TripPlannerForm";
import type { AgentRun } from "../types";
import { ArrowLeft, Clock, Coins } from "lucide-react";
import TripPlanView from "../components/TripPlanView";
import { formatDistanceToNow } from "date-fns";
import ToolCallCard from "../components/ToolCallCard";

export default function Dashboard() {
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [showSidebar, setShowSidebar] = useState(true);
  const [chatKey, setChatKey] = useState(0);

  const handleNewChat = () => {
    setSelectedRun(null);
    setChatKey((k) => k + 1);
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        {showSidebar && (
          <Sidebar
            onSelectRun={(run) => setSelectedRun(run)}
            onNewChat={handleNewChat}
            selectedRunId={selectedRun?.run_id}
          />
        )}

        <main className="flex-1 flex flex-col overflow-hidden bg-surface-950">
          {selectedRun ? (
            // History view — show a past run
            <div className="flex-1 overflow-y-auto p-6 lg:p-8">
              <button
                onClick={() => setSelectedRun(null)}
                className="btn-ghost flex items-center gap-2 text-sm mb-6"
              >
                <ArrowLeft className="w-4 h-4" /> Back to Planner
              </button>

              <div className="max-w-3xl">
                <div className="glass-card p-6 mb-4">
                  <div className="flex items-start justify-between gap-4 mb-4">
                    <h2 className="text-lg font-semibold text-slate-100 leading-snug">
                      {selectedRun.query}
                    </h2>
                    <span className={`text-xs px-2 py-1 rounded-full flex-shrink-0 ${
                      selectedRun.status === "completed" ? "bg-emerald-900/40 text-emerald-400 border border-emerald-800/50" :
                      selectedRun.status === "failed" ? "bg-red-900/40 text-red-400 border border-red-800/50" :
                      "bg-amber-900/40 text-amber-400 border border-amber-800/50"
                    }`}>
                      {selectedRun.status}
                    </span>
                  </div>

                  <div className="flex items-center gap-4 text-xs text-slate-500 mb-4">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(selectedRun.started_at), { addSuffix: true })}
                    </span>
                    {Object.keys(selectedRun.token_usage).length > 0 && (
                      <span className="flex items-center gap-1">
                        <Coins className="w-3 h-3" />
                        {Object.values(selectedRun.token_usage).reduce((a: number, b) => a + (b as number), 0)} tokens
                      </span>
                    )}
                    <span>{selectedRun.tool_calls.length} tool calls</span>
                  </div>

                  {selectedRun.tool_calls.length > 0 && (
                    <div className="space-y-2 mb-4">
                      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">Tool Calls</p>
                      {selectedRun.tool_calls.map((tc, i) => (
                        <ToolCallCard
                          key={i}
                          toolCall={{
                            tool: tc.tool_name,
                            input: tc.tool_input,
                            output: tc.tool_output ? JSON.stringify(tc.tool_output) : undefined,
                            duration_ms: tc.duration_ms ?? undefined,
                            status: tc.error ? "error" : "done",
                          }}
                        />
                      ))}
                    </div>
                  )}
                </div>

                {selectedRun.response && (
                  <div className="glass-card px-6 py-5">
                    <TripPlanView content={selectedRun.response} />
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Active chat
            <TripPlannerForm key={chatKey} />
          )}
        </main>
      </div>
    </div>
  );
}
