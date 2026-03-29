import React, { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown, ChevronRight, Info, MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { formatCurrencyUSD, formatDateByLang } from "../utils/formatters";

export default function PortfolioTable({
  rows = [],
  dark = false,
  language = "en",
  onEdit = () => {},
  onDelete = () => {},
  onDeleteAll = () => {},
}) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState({});
  const [menuOpen, setMenuOpen] = useState(null);
  const [deleteAllTarget, setDeleteAllTarget] = useState(null);

  const expandedSet = useMemo(() => new Set(Object.keys(expanded).filter((key) => expanded[key])), [expanded]);

  const toggleRow = (symbol) => {
    setExpanded((prev) => ({ ...prev, [symbol]: !prev[symbol] }));
  };

  const newestLotId = (lots = []) => {
    const ordered = [...lots].sort((a, b) => {
      const ad = String(a?.purchaseDate || "");
      const bd = String(b?.purchaseDate || "");
      if (ad === bd) return Number(b?.id || 0) - Number(a?.id || 0);
      return bd.localeCompare(ad);
    });
    return ordered[0]?.id ?? null;
  };

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-4 shadow-md`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold mb-4`}>{t("holdings")}</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1180px] text-sm">
          <thead>
            <tr className={`${dark ? "text-slate-300 border-slate-700" : "text-slate-600 border-slate-200"} border-b`}>
              <th className="px-3 py-3 text-left font-semibold">{t("ticker")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("company")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("sector")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("shares")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("avgPrice")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("currentPrice")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("marketValue")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("allocation")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("gainLoss")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("gainLoss")}</th>
              <th className="px-3 py-3 text-left font-semibold">{t("dailyChange")}</th>
              <th className="px-3 py-3 text-left font-semibold">
                <span className="inline-flex items-center gap-1">
                  {t("signalStrength")}
                  <Info size={14} className="opacity-70" title={t("signalStrengthTooltip")} />
                </span>
              </th>
              <th className="px-3 py-3 text-left font-semibold">{t("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const gainPct = Number(row.gainPct || 0);
              const gainClass = gainPct >= 0 ? "text-emerald-500" : "text-rose-500";
              const gainLoss = Number(row.gainLoss || 0);
              const dailyChange = Number(row.dailyChangePct || 0);
              const allocationPct = Number(row.allocationPct || 0);
              const lots = Array.isArray(row.lots) ? row.lots : [];
              const hasMultipleLots = Number(row.lotCount || lots.length || 1) > 1;
              const isExpanded = expandedSet.has(row.symbol);
              const canManageSingleLot = lots.length === 1 && lots[0]?.id;
              const primaryLot = canManageSingleLot ? lots[0] : null;
              const latestLot = lots.find((lot) => lot.id === newestLotId(lots)) || lots[0] || null;

              return (
                <React.Fragment key={row.symbol}>
                  <tr className={`${dark ? "border-slate-800 hover:bg-slate-900/50" : "border-slate-100 hover:bg-slate-50"} border-b transition-all font-medium`}>
                    <td className="px-3 py-3 font-bold text-[#2563EB]">
                      <button
                        type="button"
                        onClick={() => hasMultipleLots && toggleRow(row.symbol)}
                        className={`flex items-start gap-2 text-left ${hasMultipleLots ? "hover:opacity-90" : "cursor-default"}`}
                      >
                        {hasMultipleLots ? (
                          isExpanded ? <ChevronDown size={16} className="mt-0.5 shrink-0" /> : <ChevronRight size={16} className="mt-0.5 shrink-0" />
                        ) : (
                          <span className="w-4" />
                        )}
                        <div>
                          <div>{row.symbol}</div>
                          {Number(row.lotCount || lots.length || 1) > 1 ? (
                            <div className="text-xs text-slate-500">{row.lotCount} {t("lotsAggregated")}</div>
                          ) : row.purchaseDate ? (
                            <div className="text-xs text-slate-500">{formatDateByLang(row.purchaseDate, language)}</div>
                          ) : null}
                        </div>
                      </button>
                    </td>
                    <td className="px-3 py-3 font-medium">{row.company}</td>
                    <td className="px-3 py-3">{row.sector || "-"}</td>
                    <td className="px-3 py-3">{row.shares}</td>
                    <td className="px-3 py-3">{formatCurrencyUSD(row.avgPrice, language)}</td>
                    <td className="px-3 py-3">{formatCurrencyUSD(row.currentPrice, language)}</td>
                    <td className="px-3 py-3 font-semibold">{formatCurrencyUSD(row.marketValue, language)}</td>
                    <td className="px-3 py-3 font-semibold">{allocationPct.toFixed(2)}%</td>
                    <td className={`px-3 py-3 font-bold ${gainLoss >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                      {gainLoss >= 0 ? "+" : ""}{formatCurrencyUSD(gainLoss, language)}
                    </td>
                    <td className={`px-3 py-3 font-bold ${gainClass}`}>{gainPct >= 0 ? "+" : ""}{gainPct.toFixed(2)}%</td>
                    <td className={`px-3 py-3 font-semibold ${dailyChange >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
                      {dailyChange >= 0 ? "+" : ""}{dailyChange.toFixed(2)}%
                    </td>
                    <td className="px-3 py-3">
                      <div className="space-y-1">
                        <span className="px-2 py-1 rounded-full bg-cyan-100 text-cyan-700 font-semibold">
                          {Math.round(row.aiScore || 0)}/100
                        </span>
                        <p className="text-xs text-slate-500">
                          {Number(row.aiScore || 0) >= 75
                            ? t("signalStrengthHigh")
                            : Number(row.aiScore || 0) >= 55
                              ? t("signalStrengthMedium")
                              : t("signalStrengthLow")}
                        </p>
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex items-center gap-2 relative">
                        <button
                          type="button"
                          className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} p-2 rounded-lg hover:brightness-110 disabled:opacity-40 disabled:cursor-not-allowed`}
                          onClick={() => primaryLot && onEdit({ ...row, ...primaryLot, purchaseDate: primaryLot.purchaseDate, avgPrice: primaryLot.avgPrice })}
                          title={canManageSingleLot ? t("editLot") : t("expandToManageLots")}
                          disabled={!canManageSingleLot}
                        >
                          <Pencil size={14} />
                        </button>
                        <button
                          type="button"
                          className={`bg-rose-100 text-rose-700 p-2 rounded-lg hover:brightness-110 ${hasMultipleLots ? "" : "disabled:opacity-40 disabled:cursor-not-allowed"}`}
                          onClick={() => {
                            if (hasMultipleLots) {
                              toggleRow(row.symbol);
                              return;
                            }
                            if (primaryLot) onDelete(primaryLot);
                          }}
                          title={hasMultipleLots ? t("expandToManageLots") : t("deleteLot")}
                          disabled={!hasMultipleLots && !primaryLot}
                        >
                          <Trash2 size={14} />
                        </button>
                        {hasMultipleLots ? (
                          <>
                            <button
                              type="button"
                              className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} p-2 rounded-lg hover:brightness-110`}
                              onClick={() => setMenuOpen((prev) => (prev === row.symbol ? null : row.symbol))}
                              title={t("quickActions")}
                            >
                              <MoreHorizontal size={14} />
                            </button>
                            {menuOpen === row.symbol ? (
                              <div className={`absolute right-0 top-12 z-20 min-w-48 rounded-xl border shadow-xl ${dark ? "bg-slate-950 border-slate-800" : "bg-white border-slate-200"}`}>
                                <button
                                  type="button"
                                  className={`w-full px-4 py-3 text-left text-sm ${dark ? "text-slate-200 hover:bg-slate-900" : "text-slate-700 hover:bg-slate-50"}`}
                                  onClick={() => {
                                    setMenuOpen(null);
                                    if (latestLot) onDelete(latestLot);
                                  }}
                                >
                                  {t("deleteLatestLot")}
                                </button>
                                <button
                                  type="button"
                                  className={`w-full px-4 py-3 text-left text-sm ${dark ? "text-slate-200 hover:bg-slate-900" : "text-slate-700 hover:bg-slate-50"}`}
                                  onClick={() => {
                                    setMenuOpen(null);
                                    setDeleteAllTarget(row);
                                  }}
                                >
                                  {t("deleteAllLots")}
                                </button>
                                <button
                                  type="button"
                                  className={`w-full px-4 py-3 text-left text-sm ${dark ? "text-slate-200 hover:bg-slate-900" : "text-slate-700 hover:bg-slate-50"}`}
                                  onClick={() => {
                                    setMenuOpen(null);
                                    toggleRow(row.symbol);
                                  }}
                                >
                                  {t("expandView")}
                                </button>
                              </div>
                            ) : null}
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>

                  {hasMultipleLots && isExpanded ? (
                    <tr className={`${dark ? "bg-slate-950/40 border-slate-800" : "bg-slate-50 border-slate-100"} border-b`}>
                      <td colSpan={13} className="px-4 py-4">
                        <div className={`rounded-xl ${dark ? "bg-slate-900/60 border-slate-800" : "bg-white border-slate-200"} border overflow-hidden`}>
                          <div className={`grid grid-cols-[1.2fr,1fr,1fr,1fr,auto] gap-3 px-4 py-3 text-xs font-semibold uppercase tracking-wide ${dark ? "text-slate-400 bg-slate-950/40" : "text-slate-500 bg-slate-50"}`}>
                            <span>{t("lot")}</span>
                            <span>{t("shares")}</span>
                            <span>{t("avgPrice")}</span>
                            <span>{t("purchaseDate")}</span>
                            <span>{t("actions")}</span>
                          </div>
                          {lots.map((lot, index) => (
                            <div
                              key={`${row.symbol}-lot-${lot.id}`}
                              className={`grid grid-cols-[1.2fr,1fr,1fr,1fr,auto] gap-3 items-center px-4 py-3 text-sm border-t ${dark ? "border-slate-800 text-slate-300" : "border-slate-100 text-slate-600"} ${lot.id === latestLot?.id ? (dark ? "bg-slate-800/40" : "bg-blue-50/60") : ""}`}
                            >
                              <div className="pl-6">
                                <p className={`font-semibold ${dark ? "text-slate-100" : "text-slate-800"}`}>
                                  {t("lot")} #{index + 1} {lot.id === latestLot?.id ? <span className="text-xs text-blue-500">• {t("newestLot")}</span> : null}
                                </p>
                                <p className="text-xs text-slate-500">ID: {lot.id}</p>
                              </div>
                              <span className="pl-4">{lot.shares}</span>
                              <span className="pl-4">{formatCurrencyUSD(lot.avgPrice, language)}</span>
                              <span className="pl-4">{lot.purchaseDate ? formatDateByLang(lot.purchaseDate, language) : "-"}</span>
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  type="button"
                                  className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} p-2 rounded-lg hover:brightness-110`}
                                  onClick={() => onEdit({ ...row, ...lot, purchaseDate: lot.purchaseDate, avgPrice: lot.avgPrice })}
                                  title={t("editLot")}
                                >
                                  <Pencil size={14} />
                                </button>
                                <button
                                  type="button"
                                  className="bg-rose-100 text-rose-700 p-2 rounded-lg hover:brightness-110"
                                  onClick={() => onDelete(lot)}
                                  title={t("deleteLot")}
                                >
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {deleteAllTarget ? (
        <div className="fixed inset-0 z-[90] bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-100" : "bg-white border-slate-200 text-slate-900"} w-full max-w-md rounded-2xl border shadow-2xl p-6 space-y-4`}>
            <div>
              <h4 className="text-lg font-bold">{t("deleteAllLots")}</h4>
              <p className="text-sm text-slate-500 mt-1">
                {t("deleteAllLotsConfirm", {
                  ticker: deleteAllTarget.symbol,
                  lots: Number(deleteAllTarget.lotCount || deleteAllTarget.lots?.length || 0),
                  shares: Number(deleteAllTarget.shares || 0),
                })}
              </p>
            </div>
            <div className={`rounded-xl ${dark ? "bg-slate-900/60" : "bg-slate-50"} p-4 text-sm space-y-1`}>
              <p><span className="font-semibold">{t("ticker")}:</span> {deleteAllTarget.symbol}</p>
              <p><span className="font-semibold">{t("shares")}:</span> {deleteAllTarget.shares}</p>
              <p><span className="font-semibold">{t("lot")}:</span> {deleteAllTarget.lotCount || deleteAllTarget.lots?.length || 0}</p>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setDeleteAllTarget(null)}
                className={`${dark ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-700"} px-4 py-2 rounded-xl font-semibold`}
              >
                {t("cancel")}
              </button>
              <button
                type="button"
                onClick={async () => {
                  await onDeleteAll(deleteAllTarget);
                  setDeleteAllTarget(null);
                }}
                className="bg-rose-600 text-white px-4 py-2 rounded-xl font-semibold hover:brightness-110"
              >
                {t("deleteAllLots")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
