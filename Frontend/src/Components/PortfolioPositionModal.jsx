import React, { useEffect, useMemo, useRef, useState } from "react";

const EMPTY_FORM = {
  symbol: "",
  shares: "",
  average_buy_price: "",
  purchase_date: "",
};

export default function PortfolioPositionModal({
  open = false,
  mode = "create",
  initialValue = null,
  onClose = () => {},
  onSubmit = async () => {},
  onLookup = async () => [],
  dark = false,
}) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupState, setLookupState] = useState("idle");
  const [selectedName, setSelectedName] = useState("");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const inputRef = useRef(null);
  const lookupContainerRef = useRef(null);
  const hasQuery = Boolean(String(form.symbol || "").trim());

  useEffect(() => {
    if (!open) return;
    if (initialValue) {
      setForm({
        symbol: String(initialValue.symbol || "").toUpperCase(),
        shares: String(initialValue.shares ?? ""),
        average_buy_price: String(initialValue.average_buy_price ?? initialValue.avgPrice ?? ""),
        purchase_date: String(initialValue.purchase_date ?? initialValue.purchaseDate ?? ""),
      });
      setSelectedName(String(initialValue.company || ""));
      setHighlightedIndex(-1);
      setIsDropdownOpen(false);
      return;
    }
    setForm({
      ...EMPTY_FORM,
      purchase_date: new Date().toISOString().slice(0, 10),
    });
    setSelectedName("");
    setSuggestions([]);
    setLookupState("idle");
    setHighlightedIndex(-1);
    setIsDropdownOpen(false);
  }, [open, initialValue]);

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setError("");
    if (key === "symbol") {
      setSelectedName("");
      setLookupState("idle");
      setHighlightedIndex(-1);
      setSuggestions([]);
      setLookupLoading(Boolean(String(value || "").trim()));
      setIsDropdownOpen(Boolean(String(value || "").trim()));
    }
  };

  const selectSuggestion = (item) => {
    setForm((prev) => ({ ...prev, symbol: String(item?.symbol || "").toUpperCase() }));
    setSelectedName(String(item?.name || ""));
    setSuggestions([]);
    setLookupState("verified");
    setHighlightedIndex(-1);
    setIsDropdownOpen(false);
    setError("");
  };

  useEffect(() => {
    if (!open) return undefined;

    const handlePointerDownOutside = (event) => {
      if (!lookupContainerRef.current) return;
      if (lookupContainerRef.current.contains(event.target)) return;
      setIsDropdownOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDownOutside);
    document.addEventListener("touchstart", handlePointerDownOutside);

    return () => {
      document.removeEventListener("mousedown", handlePointerDownOutside);
      document.removeEventListener("touchstart", handlePointerDownOutside);
    };
  }, [open]);

  useEffect(() => {
    const q = String(form.symbol || "").trim();
    if (!open || q.length < 1) {
      setSuggestions([]);
      setLookupState("idle");
      setLookupLoading(false);
      setHighlightedIndex(-1);
      setIsDropdownOpen(false);
      return undefined;
    }

    const timer = setTimeout(async () => {
      setLookupLoading(true);
      setIsDropdownOpen(true);
      try {
        const items = await onLookup(q);
        setSuggestions(Array.isArray(items) ? items : []);
        const normalized = q.toUpperCase();
        if ((items || []).some((item) => String(item?.symbol || "").toUpperCase() === normalized)) {
          setLookupState("verified");
          const exact = items.find((item) => String(item?.symbol || "").toUpperCase() === normalized);
          setSelectedName(String(exact?.name || ""));
          setHighlightedIndex(items.findIndex((item) => String(item?.symbol || "").toUpperCase() === normalized));
        } else if ((items || []).length > 0) {
          setLookupState("typing");
          setHighlightedIndex(0);
        } else {
          setLookupState("not_found");
          setHighlightedIndex(-1);
        }
      } catch (_err) {
        setSuggestions([]);
        setLookupState("manual");
        setHighlightedIndex(-1);
      } finally {
        setLookupLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [form.symbol, onLookup, open]);

  useEffect(() => {
    if (!isDropdownOpen) return;
    if (suggestions.length === 0) {
      setHighlightedIndex(-1);
      return;
    }
    setHighlightedIndex((prev) => {
      if (prev >= 0 && prev < suggestions.length) return prev;
      return 0;
    });
  }, [isDropdownOpen, suggestions]);

  const validationBadge = useMemo(() => {
    if (!String(form.symbol || "").trim()) return null;
    if (lookupLoading) {
      return { label: "Searching...", className: dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700" };
    }
    if (lookupState === "verified") {
      return { label: "✔ Verified", className: "bg-emerald-100 text-emerald-700" };
    }
    if (lookupState === "manual") {
      return { label: "⚠ Manual fallback", className: "bg-amber-100 text-amber-700" };
    }
    if (lookupState === "not_found") {
      return { label: "❌ Not found", className: "bg-rose-100 text-rose-700" };
    }
    return null;
  }, [dark, form.symbol, lookupLoading, lookupState]);

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
      const result = await onSubmit(payload);
      if (result?.validation?.warning) {
        window.alert(result.validation.warning);
      }
      onClose();
    } catch (err) {
      setError(String(err?.message || "Failed to save position"));
    } finally {
      setSaving(false);
    }
  };

  const handleSymbolKeyDown = (e) => {
    if (!isDropdownOpen) {
      if (e.key === "ArrowDown" && hasQuery) {
        e.preventDefault();
        setIsDropdownOpen(true);
        if (suggestions.length > 0) setHighlightedIndex((prev) => (prev >= 0 ? prev : 0));
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!suggestions.length) return;
      setHighlightedIndex((prev) => (prev + 1) % suggestions.length);
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!suggestions.length) return;
      setHighlightedIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
      return;
    }

    if (e.key === "Enter" && isDropdownOpen && suggestions.length > 0 && highlightedIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[highlightedIndex]);
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      setIsDropdownOpen(false);
      setHighlightedIndex(-1);
    }
  };

  const showDropdown = isDropdownOpen && Boolean(String(form.symbol || "").trim());

  if (!open) return null;

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
            <div ref={lookupContainerRef} className="relative mt-1">
              <input
                ref={inputRef}
                value={form.symbol}
                onChange={(e) => setField("symbol", e.target.value)}
                onFocus={() => {
                  if (hasQuery) setIsDropdownOpen(true);
                }}
                onKeyDown={handleSymbolKeyDown}
                className={`${dark ? "bg-slate-900 border-slate-700" : "bg-white border-slate-200"} w-full rounded-xl border px-4 py-2.5 font-semibold`}
                placeholder="AAPL, TSM, ASML"
                autoComplete="off"
              />
              {showDropdown ? (
                <div className={`absolute z-20 mt-2 w-full rounded-xl border shadow-xl overflow-hidden ${dark ? "bg-slate-950 border-slate-800" : "bg-white border-slate-200"}`}>
                  {lookupLoading ? (
                    <div className={`px-4 py-3 text-sm ${dark ? "text-slate-300" : "text-slate-500"}`}>Searching...</div>
                  ) : suggestions.length ? (
                    suggestions.map((item, index) => {
                      const active = index === highlightedIndex;
                      return (
                        <button
                          key={`${item.symbol}-${item.exchange || ""}`}
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => selectSuggestion(item)}
                          className={`w-full px-4 py-3 text-left text-sm ${
                            active
                              ? dark
                                ? "bg-slate-800 text-slate-100"
                                : "bg-slate-100 text-slate-900"
                              : dark
                                ? "text-slate-200 hover:bg-slate-900"
                                : "text-slate-700 hover:bg-slate-50"
                          }`}
                        >
                          <span className="font-semibold">{item.symbol}</span>
                          <span className="text-slate-500"> — {item.name || "Unknown Company"}{item.exchange ? ` — ${item.exchange}` : ""}</span>
                        </button>
                      );
                    })
                  ) : lookupState === "not_found" || lookupState === "manual" || lookupState === "typing" ? (
                    <div className={`px-4 py-3 text-sm ${dark ? "text-slate-300" : "text-slate-500"}`}>No results found</div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              {validationBadge ? (
                <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${validationBadge.className}`}>
                  {validationBadge.label}
                </span>
              ) : null}
              {selectedName ? <span className="text-xs text-slate-500">{selectedName}</span> : null}
            </div>
            <p className="mt-2 text-xs text-slate-500">Supports global tickers. Example: AAPL, TSM, ASML.</p>
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
