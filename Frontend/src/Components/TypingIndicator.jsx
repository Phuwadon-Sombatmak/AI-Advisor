import React from "react";

export default function TypingIndicator({ stage = "Analyzing market data...", dark = false }) {
  return (
    <div className="flex justify-start">
      <div className={`max-w-[90%] rounded-2xl rounded-bl-md px-4 py-3 shadow-sm border ${
        dark ? "bg-slate-800/90 text-slate-100 border-slate-700" : "bg-white text-slate-700 border-slate-200"
      }`}>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.2s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce [animation-delay:-0.1s]" />
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-bounce" />
          </div>
          <p className="text-xs font-medium">{stage}</p>
        </div>
      </div>
    </div>
  );
}
