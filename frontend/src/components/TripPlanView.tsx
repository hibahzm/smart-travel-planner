import ReactMarkdown from "react-markdown";
import {
  Calendar,
  MapPin,
  DollarSign,
  Lightbulb,
  Plane,
  CheckSquare,
  Globe,
  Compass,
} from "lucide-react";
import type { ReactNode } from "react";

interface Section {
  rawTitle: string;
  content: string;
  icon: ReactNode;
  accentClass: string;
  headerClass: string;
}

interface ParsedPlan {
  intro: string;
  sections: Section[];
}

const SECTION_CONFIG = [
  {
    keywords: ["overview"],
    icon: <Globe size={14} />,
    accentClass: "border border-blue-800/50 bg-blue-900/10",
    headerClass: "text-blue-300",
  },
  {
    keywords: ["best time", "time to visit", "when to go", "season"],
    icon: <Calendar size={14} />,
    accentClass: "border border-amber-800/50 bg-amber-900/10",
    headerClass: "text-amber-300",
  },
  {
    keywords: ["activit", "things to do", "experience", "highlight", "top"],
    icon: <Compass size={14} />,
    accentClass: "border border-emerald-800/50 bg-emerald-900/10",
    headerClass: "text-emerald-300",
  },
  {
    keywords: ["budget", "cost", "price", "expense", "money", "breakdown"],
    icon: <DollarSign size={14} />,
    accentClass: "border border-green-800/50 bg-green-900/10",
    headerClass: "text-green-300",
  },
  {
    keywords: ["practical", "tip", "advice", "need to know", "visa", "health", "safety"],
    icon: <Lightbulb size={14} />,
    accentClass: "border border-purple-800/50 bg-purple-900/10",
    headerClass: "text-purple-300",
  },
  {
    keywords: ["booking", "book", "how to get", "transport", "flight", "getting there"],
    icon: <Plane size={14} />,
    accentClass: "border border-orange-800/50 bg-orange-900/10",
    headerClass: "text-orange-300",
  },
  {
    keywords: ["checklist", "check", "summary", "action", "next step"],
    icon: <CheckSquare size={14} />,
    accentClass: "border border-teal-800/50 bg-teal-900/10",
    headerClass: "text-teal-300",
  },
];

const DEFAULT_CONFIG = {
  icon: <MapPin size={14} />,
  accentClass: "border border-surface-700/50 bg-surface-800/20",
  headerClass: "text-slate-300",
};

function getSectionConfig(title: string) {
  const lower = title.toLowerCase();
  return (
    SECTION_CONFIG.find((c) => c.keywords.some((k) => lower.includes(k))) ??
    DEFAULT_CONFIG
  );
}

function parsePlan(markdown: string): ParsedPlan {
  const parts = markdown.split(/^(?=## )/m);
  const intro = parts[0].trim();
  const sections: Section[] = parts.slice(1).map((part) => {
    const newlineIdx = part.indexOf("\n");
    const rawTitle = part
      .slice(3, newlineIdx > 0 ? newlineIdx : undefined)
      .trim();
    const content = newlineIdx > 0 ? part.slice(newlineIdx + 1).trim() : "";
    const config = getSectionConfig(rawTitle);
    return { rawTitle, content, ...config };
  });
  return { intro, sections };
}

export default function TripPlanView({ content }: { content: string }) {
  const hasSections = content.includes("\n## ");
  if (!hasSections) {
    return (
      <div className="prose-travel">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  const { intro, sections } = parsePlan(content);

  return (
    <div className="space-y-3">
      {intro && (
        <div className="rounded-xl border-l-4 border-primary-500/70 bg-surface-800/40 px-5 py-4">
          <div className="prose-travel">
            <ReactMarkdown>{intro}</ReactMarkdown>
          </div>
        </div>
      )}

      <div className="grid gap-2.5">
        {sections.map((section, i) => (
          <div key={i} className={`rounded-xl px-5 py-4 ${section.accentClass}`}>
            <div
              className={`flex items-center gap-2 font-semibold text-sm mb-2.5 ${section.headerClass}`}
            >
              {section.icon}
              <span>{section.rawTitle}</span>
            </div>
            <div className="prose-travel text-sm">
              <ReactMarkdown>{section.content}</ReactMarkdown>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
