import React from "react";

export default function SentimentIndicator({ label, value, dark = false }) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  const barColor = v >= 75 ? "#22C55E" : v >= 50 ? "#38BDF8" : v >= 25 ? "#F97316" : "#DC2626";

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className={`${dark ? "text-slate-300" : "text-slate-600"}`}>{label}</span>
        <span className={`${dark ? "text-slate-200" : "text-slate-800"} font-semibold`}>{v}</span>
      </div>
      <div className={`${dark ? "bg-slate-700" : "bg-slate-200"} h-2 rounded-full overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${v}%`, backgroundColor: barColor }}
        />
      </div>
    </div>
  );
}
