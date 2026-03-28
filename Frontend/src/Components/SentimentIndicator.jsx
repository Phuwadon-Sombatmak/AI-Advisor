import React from "react";

const getSemanticColor = (value, isRiskMetric) => {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  if (isRiskMetric) {
    if (v >= 70) return "#DC2626";
    if (v >= 55) return "#F97316";
    if (v >= 40) return "#F59E0B";
    return "#22C55E";
  }
  if (v >= 70) return "#22C55E";
  if (v >= 55) return "#38BDF8";
  if (v >= 40) return "#F59E0B";
  return "#DC2626";
};

export default function SentimentIndicator({
  label,
  value,
  dark = false,
  direction = null,
  interpretation = "",
  tooltip = "",
  isRiskMetric = false,
}) {
  const hasValue = value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value));
  const v = hasValue ? Math.max(0, Math.min(100, Number(value))) : null;
  const barColor = hasValue ? getSemanticColor(v, isRiskMetric) : (dark ? "#475569" : "#CBD5E1");
  const arrow = direction === "up" ? "↑" : direction === "down" ? "↓" : "•";
  const arrowColor = hasValue ? barColor : (dark ? "#94A3B8" : "#64748B");

  return (
    <div className="space-y-1.5" title={tooltip || undefined}>
      <div className="flex items-center justify-between text-sm">
        <span className={`${dark ? "text-slate-300" : "text-slate-600"}`}>{label}</span>
        <span className={`${dark ? "text-slate-200" : "text-slate-800"} font-semibold`}>{v ?? "—"}</span>
      </div>
      <div className={`${dark ? "bg-slate-700" : "bg-slate-200"} h-2 rounded-full overflow-hidden`}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${v ?? 0}%`, backgroundColor: barColor }}
        />
      </div>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold" style={{ color: arrowColor }}>
          {arrow} {interpretation || "—"}
        </span>
      </div>
    </div>
  );
}
