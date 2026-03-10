import React from "react";

const RANGES = [
  { label: "1D", value: "1d" },
  { label: "5D", value: "5d" },
  { label: "1M", value: "1m" },
  { label: "6M", value: "6m" },
  { label: "YTD", value: "ytd" },
  { label: "1Y", value: "1y" },
  { label: "5Y", value: "5y" },
  { label: "ALL", value: "all" },
];

export default function TimeRangeSelector({ range = "1m", onChange = () => {}, dark = false }) {
  return (
    <div className="flex flex-wrap gap-2">
      {RANGES.map((btn) => (
        <button
          key={btn.value}
          type="button"
          onClick={() => onChange(btn.value)}
          className={`px-3 py-1.5 rounded-lg text-sm font-bold transition-all ${
            range === btn.value
              ? "text-white shadow-sm"
              : dark
                ? "bg-slate-800 text-slate-300"
                : "bg-slate-100 text-slate-700"
          }`}
          style={range === btn.value ? { background: "linear-gradient(135deg,#2563EB,#1E3A8A)" } : undefined}
        >
          {btn.label}
        </button>
      ))}
    </div>
  );
}
