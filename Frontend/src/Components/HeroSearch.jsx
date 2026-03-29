import React, { useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { useTranslation } from "react-i18next";

export default function HeroSearch({ query, setQuery, onSearch, suggestions, onPick, onLookup = async () => [] }) {
  const { t } = useTranslation();
  const [results, setResults] = useState([]);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const containerRef = useRef(null);
  const hasQuery = Boolean(String(query || "").trim());

  useEffect(() => {
    const q = String(query || "").trim();
    if (!q) {
      setResults([]);
      setLookupLoading(false);
      setDropdownOpen(false);
      setHighlightedIndex(-1);
      return undefined;
    }

    setDropdownOpen(true);
    setLookupLoading(true);

    const timer = setTimeout(async () => {
      try {
        const items = await onLookup(q);
        const safeItems = Array.isArray(items) ? items : [];
        setResults(safeItems);
        setHighlightedIndex(safeItems.length ? 0 : -1);
      } catch {
        setResults([]);
        setHighlightedIndex(-1);
      } finally {
        setLookupLoading(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [onLookup, query]);

  useEffect(() => {
    const handlePointerDownOutside = (event) => {
      if (!containerRef.current) return;
      if (containerRef.current.contains(event.target)) return;
      setDropdownOpen(false);
    };

    document.addEventListener("mousedown", handlePointerDownOutside);
    document.addEventListener("touchstart", handlePointerDownOutside);
    return () => {
      document.removeEventListener("mousedown", handlePointerDownOutside);
      document.removeEventListener("touchstart", handlePointerDownOutside);
    };
  }, []);

  const selectResult = (item) => {
    const symbol = String(item?.symbol || "").toUpperCase();
    if (!symbol) return;
    setQuery(symbol);
    setResults([]);
    setDropdownOpen(false);
    setHighlightedIndex(-1);
    onPick(symbol);
  };

  const handleKeyDown = (e) => {
    if (!dropdownOpen) {
      if (e.key === "Enter") {
        e.preventDefault();
        onSearch();
      } else if (e.key === "ArrowDown" && hasQuery) {
        e.preventDefault();
        setDropdownOpen(true);
        setHighlightedIndex(results.length ? 0 : -1);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!results.length) return;
      setHighlightedIndex((prev) => (prev + 1) % results.length);
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!results.length) return;
      setHighlightedIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (results.length && highlightedIndex >= 0) {
        selectResult(results[highlightedIndex]);
      } else {
        onSearch();
      }
      return;
    }

    if (e.key === "Escape") {
      e.preventDefault();
      setDropdownOpen(false);
    }
  };

  const showDropdown = dropdownOpen && hasQuery;

  return (
    <section
      className="rounded-3xl px-6 py-8 md:px-10 md:py-10 text-white shadow-[0_10px_25px_rgba(0,0,0,0.12)] transition-all duration-300"
      style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
    >
      <h1 className="text-3xl md:text-4xl font-bold mb-2 text-center">{t("searchHero")}</h1>
      <p className="text-center text-blue-100 font-normal mb-6">{t("searchSubtitle")}</p>

      <div ref={containerRef} className="max-w-3xl mx-auto relative">
        <input
          type="text"
          placeholder={t("searchPlaceholder")}
          className="w-full pl-6 pr-16 py-3 md:py-4 rounded-2xl bg-white/95 border border-white/40 text-slate-700 font-semibold text-lg md:text-xl placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-[#38BDF8]"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => {
            if (hasQuery) setDropdownOpen(true);
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          onClick={onSearch}
          className="absolute right-3 top-1/2 -translate-y-1/2 h-12 w-12 rounded-xl text-white flex items-center justify-center transition-all hover:scale-105 hover:brightness-110"
          style={{ background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }}
        >
          <Search size={24} />
        </button>
        {showDropdown ? (
          <div className="absolute z-20 mt-3 w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
            {lookupLoading ? (
              <div className="px-5 py-4 text-sm font-medium text-slate-500">Searching...</div>
            ) : results.length ? (
              results.map((item, index) => {
                const active = index === highlightedIndex;
                return (
                  <button
                    key={`${item.symbol}-${item.exchange || ""}`}
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => selectResult(item)}
                    className={`w-full px-5 py-4 text-left text-sm transition-colors ${
                      active ? "bg-slate-100 text-slate-900" : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <span className="font-semibold">{item.symbol}</span>
                    <span className="text-slate-500"> — {item.name || "Unknown Company"}{item.exchange ? ` — ${item.exchange}` : ""}</span>
                  </button>
                );
              })
            ) : (
              <div className="px-5 py-4 text-sm font-medium text-slate-500">No results found</div>
            )}
          </div>
        ) : null}
      </div>

      <div className="flex justify-center items-center gap-2 md:gap-3 mt-6 flex-wrap">
        <span className="text-blue-100 font-semibold">{t("popular")}</span>
        {suggestions.map((symbol) => (
          <button
            key={symbol}
            onClick={() => onPick(symbol)}
            className="px-5 py-2 bg-white/10 border border-white/30 hover:bg-white/20 rounded-2xl text-sm font-bold text-white transition-all hover:-translate-y-1"
          >
            {symbol}
          </button>
        ))}
      </div>
    </section>
  );
}
