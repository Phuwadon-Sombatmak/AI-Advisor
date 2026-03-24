import React from "react";
import { Bot, X } from "lucide-react";

function StatusBadge({ label, dark = false }) {
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
        dark ? "bg-blue-500/15 text-blue-200 border-blue-400/25" : "bg-white/15 text-blue-50 border-white/30"
      }`}
    >
      {label}
    </span>
  );
}

export default function ChatHeader({ dark = false, onClose = () => {}, status = {} }) {
  const online = status?.online !== false;
  const degraded = status?.degraded === true || status?.live_data_ready === false;
  const statusText = degraded ? "Connected" : (status?.message || (online ? "Connected" : "Reconnecting"));
  const readyText = degraded ? "Limited" : (online ? "Ready" : "Syncing");
  const readyDot = degraded ? "bg-amber-300" : (online ? "bg-emerald-300" : "bg-amber-300");

  return (
    <div className="px-4 py-3 text-white border-b border-white/10 bg-gradient-to-r from-[#1E3A8A] via-[#1f4bc2] to-[#2563EB]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="h-9 w-9 rounded-xl bg-white/15 inline-flex items-center justify-center border border-white/20">
            <Bot size={17} />
          </div>
          <div>
            <p className="font-bold text-sm leading-tight">AI Advisor</p>
            <p className="text-[11px] text-blue-100/95">AI Investment Assistant</p>
          </div>
        </div>
        <button onClick={onClose} className="text-white/90 hover:text-white mt-0.5">
          <X size={18} />
        </button>
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <StatusBadge label={statusText} dark={dark} />
        <StatusBadge label={status?.live_data_ready === false ? "Limited Data" : "Live Data Ready"} dark={dark} />
        <StatusBadge label={status?.market_context_loaded === false ? "Context Loading" : "Market Context Loaded"} dark={dark} />
        <span className="ml-auto inline-flex items-center gap-1 text-[11px] text-blue-100">
          <span className={`inline-flex h-2 w-2 rounded-full ${readyDot}`} />
          {readyText}
        </span>
      </div>
    </div>
  );
}
