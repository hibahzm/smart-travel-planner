import { Send, StopCircle, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";
import MessageBubble from "./MessageBubble";

const STARTER_PROMPTS = [
  "I have 2 weeks in July with $1,500. I want somewhere warm, not touristy, and I love hiking.",
  "Best budget-friendly beach destination in Southeast Asia for 10 days under $800?",
  "I want a cultural city trip in Europe in October. I love architecture and food.",
  "Where can I go for a safari experience under $3,000 for 2 weeks?",
];

export default function ChatInterface() {
  const { messages, isStreaming, sendMessage, cancelStream } = useChat();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = () => {
    const q = input.trim();
    if (!q || isStreaming) return;
    setInput("");
    sendMessage(q);
    inputRef.current?.focus();
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 lg:px-8 py-6 space-y-5">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full py-16 animate-fade-in">
            <div className="w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl flex items-center justify-center mb-6 shadow-2xl shadow-primary-900/40">
              <Sparkles className="w-8 h-8 text-white" />
            </div>
            <h2 className="text-2xl font-semibold text-slate-100 mb-2">Where do you want to go?</h2>
            <p className="text-slate-400 text-center max-w-md mb-8">
              Describe your ideal trip — budget, dates, activities, vibe — and the agent will research destinations, classify travel styles, and check live conditions for you.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl">
              {STARTER_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => sendMessage(prompt)}
                  className="text-left p-4 glass-card hover:border-primary-700/50 hover:bg-surface-800/80 transition-all duration-200 rounded-xl group"
                >
                  <p className="text-sm text-slate-300 group-hover:text-slate-100 leading-snug">{prompt}</p>
                </button>
              ))}
            </div>

            <div className="mt-8 flex items-center gap-6 text-xs text-slate-600">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-blue-500 rounded-full" /> RAG Knowledge Base
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-purple-500 rounded-full" /> ML Style Classifier
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-emerald-500 rounded-full" /> Live Conditions API
              </span>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input bar */}
      <div className="px-4 lg:px-8 pb-6 pt-2">
        <div className="glass-card p-2 flex items-end gap-2 focus-within:border-primary-600/50 transition-colors">
          <textarea
            ref={inputRef}
            rows={1}
            className="flex-1 bg-transparent text-slate-100 placeholder-slate-500 resize-none focus:outline-none px-3 py-2 text-sm leading-relaxed max-h-32 overflow-y-auto"
            placeholder="Ask about a destination… (Shift+Enter for new line)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKey}
            style={{ minHeight: "40px" }}
          />

          {isStreaming ? (
            <button
              onClick={cancelStream}
              className="flex-shrink-0 w-9 h-9 flex items-center justify-center bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
              title="Stop generating"
            >
              <StopCircle className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSubmit}
              disabled={!input.trim()}
              className="flex-shrink-0 w-9 h-9 flex items-center justify-center bg-primary-600 hover:bg-primary-500 text-white rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed active:scale-95"
              title="Send (Enter)"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-xs text-slate-600 text-center mt-2">
          The agent uses gpt-4o-mini for tool routing and gpt-4o for synthesis
        </p>
      </div>
    </div>
  );
}
