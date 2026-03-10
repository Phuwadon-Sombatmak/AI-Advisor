import React from "react";

const PILL_BASE = "px-3 py-1.5 rounded-full text-sm font-semibold transition-all hover:scale-[1.03]";

function PillGroup({ title, options, value, onChange }) {
  return (
    <div className="space-y-2">
      <p className="text-sm font-semibold text-slate-500">{title}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = value === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => onChange(opt.value)}
              className={`${PILL_BASE} ${active ? "bg-[#2563EB] text-white" : "bg-[#F1F5F9] text-[#334155] hover:brightness-95"}`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function AIPickerFilters({ risk, setRisk, strategy, setStrategy, sentiment, setSentiment, dark }) {
  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-4`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>Strategy Filters</h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <PillGroup
          title="Risk Level"
          value={risk}
          onChange={setRisk}
          options={[
            { label: "LOW", value: "LOW" },
            { label: "MEDIUM", value: "MEDIUM" },
            { label: "HIGH", value: "HIGH" },
          ]}
        />
        <PillGroup
          title="Strategy"
          value={strategy}
          onChange={setStrategy}
          options={[
            { label: "Growth", value: "Growth" },
            { label: "Momentum", value: "Momentum" },
            { label: "Value", value: "Value" },
            { label: "AI Trend", value: "AI Trend" },
          ]}
        />
        <PillGroup
          title="Sentiment"
          value={sentiment}
          onChange={setSentiment}
          options={[
            { label: "Bullish", value: "Bullish" },
            { label: "Neutral", value: "Neutral" },
            { label: "Bearish", value: "Bearish" },
          ]}
        />
      </div>
    </section>
  );
}
