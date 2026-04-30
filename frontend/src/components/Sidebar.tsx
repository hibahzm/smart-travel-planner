import { Clock, MessageSquare, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { agentApi } from "../api/agent";
import type { AgentRun } from "../types";
import { formatDistanceToNow } from "date-fns";
import clsx from "clsx";

interface SidebarProps {
  onSelectRun: (run: AgentRun) => void;
  onNewChat: () => void;
  selectedRunId?: string;
}

export default function Sidebar({ onSelectRun, onNewChat, selectedRunId }: SidebarProps) {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    agentApi.getHistory().then(({ runs }) => {
      setRuns(runs);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const statusColor = (status: AgentRun["status"]) => ({
    completed: "bg-emerald-500",
    running: "bg-amber-500 animate-pulse",
    failed: "bg-red-500",
    pending: "bg-slate-500",
  }[status]);

  return (
    <aside className="w-64 bg-surface-900 border-r border-surface-800 flex flex-col h-full">
      <div className="p-4">
        <button
          onClick={onNewChat}
          className="btn-primary w-full flex items-center justify-center gap-2 text-sm"
        >
          <Plus className="w-4 h-4" />
          New Trip Plan
        </button>
      </div>

      <div className="px-4 pb-2">
        <p className="text-xs font-medium text-slate-500 uppercase tracking-widest">Recent Trips</p>
      </div>

      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {loading && (
          <div className="space-y-2 px-2 mt-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-14 bg-surface-800 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {!loading && runs.length === 0 && (
          <div className="text-center py-8 px-4">
            <MessageSquare className="w-8 h-8 text-slate-600 mx-auto mb-2" />
            <p className="text-sm text-slate-500">No trips yet</p>
            <p className="text-xs text-slate-600 mt-1">Ask your first travel question</p>
          </div>
        )}

        {runs.map((run) => (
          <button
            key={run.run_id}
            onClick={() => onSelectRun(run)}
            className={clsx(
              "w-full text-left px-3 py-2.5 rounded-xl transition-all duration-150 group",
              selectedRunId === run.run_id
                ? "bg-primary-900/40 border border-primary-700/50"
                : "hover:bg-surface-800"
            )}
          >
            <div className="flex items-start gap-2">
              <div className={clsx("w-2 h-2 rounded-full mt-1.5 flex-shrink-0", statusColor(run.status))} />
              <div className="min-w-0">
                <p className="text-sm text-slate-300 truncate leading-snug">
                  {run.query}
                </p>
                <p className="text-xs text-slate-600 mt-0.5 flex items-center gap-1">
                  <Clock className="w-2.5 h-2.5" />
                  {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                </p>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-surface-800">
        <p className="text-xs text-slate-600 text-center">
          Built with LangGraph + OpenAI
        </p>
      </div>
    </aside>
  );
}
