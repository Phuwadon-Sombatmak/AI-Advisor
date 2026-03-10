import React from "react";
import { Send, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function ChatInput({
  value,
  onChange,
  onSend,
  onClear,
  loading = false,
  dark = false,
}) {
  const { t } = useTranslation();

  const submit = (e) => {
    e.preventDefault();
    if (!value.trim() || loading) return;
    onSend();
  };

  return (
    <form onSubmit={submit} className={`p-3 border-t ${dark ? "border-slate-700 bg-[#0B1220]" : "border-slate-200 bg-white"}`}>
      <div className="flex items-center gap-2">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={t("aiChatPlaceholder") || "Ask about stocks, markets, sectors, or portfolio ideas..."}
          className={`${dark ? "bg-slate-800 text-slate-100 border-slate-700 placeholder:text-slate-500" : "bg-slate-50 text-slate-800 border-slate-200 placeholder:text-slate-400"} flex-1 rounded-xl border px-4 py-2.5 text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/40`}
        />
        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="px-3 py-2.5 rounded-xl text-white font-semibold disabled:opacity-60 shadow-md hover:brightness-110"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          <Send size={16} />
        </button>
        <button
          type="button"
          onClick={onClear}
          className={`${dark ? "bg-slate-800 text-slate-300" : "bg-slate-100 text-slate-600"} px-3 py-2.5 rounded-xl`}
          title={t("clearChat")}
        >
          <Trash2 size={16} />
        </button>
      </div>
      <p className={`mt-2 text-[11px] ${dark ? "text-slate-500" : "text-slate-400"}`}>
        {loading ? "Assistant is building an investment view..." : "Ask about stocks, market trend, sector momentum, or portfolio risk."}
      </p>
    </form>
  );
}
