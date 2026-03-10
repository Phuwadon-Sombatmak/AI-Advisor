import React, { useEffect, useState } from "react";

const EMPTY_FORM = {
  symbol: "",
  shares: "",
  average_buy_price: "",
  purchase_date: "",
};

const SYMBOL_SUGGESTIONS = ["NVDA", "MSFT", "AAPL", "AMZN", "TSLA", "META", "GOOGL", "AMD", "AVGO", "JPM", "XOM", "UNH"];

export default function PortfolioPositionModal({
  open = false,
  mode = "create",
  initialValue = null,
  onClose = () => {},
  onSubmit = async () => {},
  dark = false,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    if (initialValue) {
      setForm({
        symbol: String(initialValue.symbol || "").toUpperCase(),
        shares: String(initialValue.shares ?? ""),
        average_buy_price: String(initialValue.average_buy_price ?? initialValue.avgPrice ?? ""),
        purchase_date: String(initialValue.purchase_date ?? initialValue.purchaseDate ?? ""),
      });
      return;
    }
    setForm({
      ...EMPTY_FORM,
      purchase_date: new Date().toISOString().slice(0, 10),
    });
  }, [open, initialValue]);

  if (!open) return null;

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const payload = {
      symbol: String(form.symbol || "").trim().toUpperCase(),
      shares: Number(form.shares),
      average_buy_price: Number(form.average_buy_price),
      purchase_date: form.purchase_date,
    };
    if (!payload.symbol || payload.shares <= 0 || payload.average_buy_price <= 0 || !payload.purchase_date) {
      setError("Please complete all fields with valid values.");
      return;
    }

    setSaving(true);
    try {
      await onSubmit(payload);
      onClose();
    } catch (err) {
      setError(String(err?.message || "Failed to save position"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[80] bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-900"} w-full max-w-lg rounded-2xl border shadow-2xl`}>
        <div className="px-6 pt-6 pb-2">
          <h3 className="text-xl font-bold">{mode === "edit" ? "Edit Position" : "Add Position"}</h3>
          <p className="text-sm text-slate-500">Manage your real portfolio positions.</p>
        </div>

        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
          <div>
            <label className="text-sm font-semibold">Stock Symbol</label>
            <input
              value={form.symbol}
              onChange={(e) => setField("symbol", e.target.value)}
              list="portfolio-symbol-suggestions"
              className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} mt-1 w-full rounded-xl border px-4 py-2.5 font-semibold uppercase`}
              placeholder="NVDA"
            />
            <datalist id="portfolio-symbol-suggestions">
              {SYMBOL_SUGGESTIONS.map((sym) => (
                <option value={sym} key={sym} />
              ))}
            </datalist>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-semibold">Shares</label>
              <input
                type="number"
                min="0"
                step="0.0001"
                value={form.shares}
                onChange={(e) => setField("shares", e.target.value)}
                className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} mt-1 w-full rounded-xl border px-4 py-2.5`}
                placeholder="12"
              />
            </div>
            <div>
              <label className="text-sm font-semibold">Average Cost</label>
              <input
                type="number"
                min="0"
                step="0.0001"
                value={form.average_buy_price}
                onChange={(e) => setField("average_buy_price", e.target.value)}
                className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} mt-1 w-full rounded-xl border px-4 py-2.5`}
                placeholder="153.43"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-semibold">Purchase Date</label>
            <input
              type="date"
              value={form.purchase_date}
              onChange={(e) => setField("purchase_date", e.target.value)}
              className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} mt-1 w-full rounded-xl border px-4 py-2.5`}
            />
          </div>

          {error ? <p className="text-sm text-rose-500 font-medium">{error}</p> : null}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} px-4 py-2 rounded-xl font-semibold`}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="text-white px-5 py-2 rounded-xl font-semibold shadow-md hover:brightness-110 disabled:opacity-70"
              style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
            >
              {saving ? "Saving..." : mode === "edit" ? "Save Changes" : "Add Position"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
