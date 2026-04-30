import { Globe, LogOut, User, Webhook } from "lucide-react";
import { useState } from "react";
import { useAuth } from "../hooks/useAuth";
import { authApi } from "../api/auth";

export default function Header() {
  const { user, logout } = useAuth();
  const [showWebhook, setShowWebhook] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState(user?.webhook_url ?? "");
  const [saving, setSaving] = useState(false);

  const saveWebhook = async () => {
    setSaving(true);
    try {
      await authApi.updateWebhook(webhookUrl);
      setShowWebhook(false);
    } finally {
      setSaving(false);
    }
  };

  return (
    <header className="h-14 bg-surface-900/95 border-b border-surface-800 flex items-center justify-between px-6 sticky top-0 z-50 backdrop-blur-sm">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center shadow-lg shadow-primary-900/30">
          <Globe className="w-4 h-4 text-white" />
        </div>
        <span className="font-semibold text-slate-100 tracking-tight">Smart Travel Planner</span>
        <span className="hidden sm:block text-xs text-primary-400 bg-primary-900/30 px-2 py-0.5 rounded-full border border-primary-800/50">
          AI-Powered
        </span>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowWebhook(!showWebhook)}
          className="btn-ghost flex items-center gap-2 text-sm"
          title="Configure webhook"
        >
          <Webhook className="w-4 h-4" />
          <span className="hidden sm:block">Webhook</span>
        </button>

        {user && (
          <div className="flex items-center gap-2 pl-2 border-l border-surface-700">
            <div className="w-7 h-7 bg-gradient-to-br from-primary-600 to-primary-800 rounded-full flex items-center justify-center">
              <User className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-sm text-slate-300 hidden sm:block">{user.username}</span>
          </div>
        )}

        <button onClick={logout} className="btn-ghost" title="Sign out">
          <LogOut className="w-4 h-4" />
        </button>
      </div>

      {showWebhook && (
        <div className="absolute top-full right-4 mt-2 w-80 glass-card p-4 shadow-2xl animate-fade-in">
          <p className="text-sm font-medium text-slate-300 mb-2">Discord/Slack Webhook URL</p>
          <p className="text-xs text-slate-500 mb-3">
            When a trip plan finishes, the agent delivers it to this channel automatically.
          </p>
          <input
            className="input-field text-sm mb-3"
            placeholder="https://discord.com/api/webhooks/..."
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
          <div className="flex gap-2">
            <button className="btn-primary text-sm flex-1" onClick={saveWebhook} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
            <button className="btn-ghost text-sm" onClick={() => setShowWebhook(false)}>Cancel</button>
          </div>
        </div>
      )}
    </header>
  );
}
