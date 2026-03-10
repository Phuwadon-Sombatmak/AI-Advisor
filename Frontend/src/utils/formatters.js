export function normalizeLang(language) {
  return String(language || "en").toLowerCase().startsWith("th") ? "th" : "en";
}

export function formatDateByLang(input, language) {
  const lang = normalizeLang(language);
  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return "-";
  const locale = lang === "th" ? "th-TH" : "en-US";
  return d.toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTimeByLang(input, language) {
  const lang = normalizeLang(language);
  const d = input instanceof Date ? input : new Date(input);
  if (Number.isNaN(d.getTime())) return "-";
  const locale = lang === "th" ? "th-TH" : "en-US";
  return d.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatCurrencyUSD(value, language) {
  const lang = normalizeLang(language);
  const amount = Number(value || 0);
  if (lang === "th") {
    return `${amount.toLocaleString("th-TH", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ดอลลาร์`;
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}
