const ETF_TYPE_BY_SYMBOL = {
  DIA: "Index ETF",
  GLD: "Commodity ETF",
  IWM: "Index ETF",
  QQQ: "Index ETF",
  SPY: "Index ETF",
  XLB: "Sector ETF",
  XLE: "Sector ETF",
  XLF: "Sector ETF",
  XLI: "Sector ETF",
  XLK: "Sector ETF",
  XLP: "Sector ETF",
  XLRE: "Sector ETF",
  XLU: "Sector ETF",
  XLV: "Sector ETF",
  XLY: "Sector ETF",
};

const ETF_NAME_BY_SYMBOL = {
  DIA: "SPDR Dow Jones Industrial Average ETF Trust",
  GLD: "SPDR Gold Shares",
  IWM: "iShares Russell 2000 ETF",
  QQQ: "Invesco QQQ Trust",
  SPY: "SPDR S&P 500 ETF Trust",
  XLB: "Materials Select Sector SPDR Fund",
  XLE: "Energy Select Sector SPDR Fund",
  XLF: "Financial Select Sector SPDR Fund",
  XLI: "Industrial Select Sector SPDR Fund",
  XLK: "Technology Select Sector SPDR Fund",
  XLP: "Consumer Staples Select Sector SPDR Fund",
  XLRE: "Real Estate Select Sector SPDR Fund",
  XLU: "Utilities Select Sector SPDR Fund",
  XLV: "Health Care Select Sector SPDR Fund",
  XLY: "Consumer Discretionary Select Sector SPDR Fund",
};

const ETF_TYPE_LABELS = {
  en: {
    ETF: "ETF",
    "Commodity ETF": "Commodity ETF",
    "Index ETF": "Index ETF",
    "Sector ETF": "Sector ETF",
  },
  th: {
    ETF: "ETF",
    "Commodity ETF": "ETF สินค้าโภคภัณฑ์",
    "Index ETF": "ETF ดัชนี",
    "Sector ETF": "ETF กลุ่มอุตสาหกรรม",
  },
};

const ETF_TYPE_DESCRIPTION_BY_TYPE = {
  en: {
    ETF: "Exchange-traded fund",
    "Commodity ETF": "Fund tracking commodities such as gold or oil",
    "Index ETF": "Fund tracking a market index such as the S&P 500 or Nasdaq-100",
    "Sector ETF": "Fund tracking stocks within the same industry sector",
  },
  th: {
    ETF: "กองทุนรวมซื้อขายในตลาดหลักทรัพย์",
    "Commodity ETF": "กองทุนที่อ้างอิงสินค้าโภคภัณฑ์ เช่น ทองคำหรือน้ำมัน",
    "Index ETF": "กองทุนที่ติดตามดัชนีตลาด เช่น S&P 500 หรือ Nasdaq-100",
    "Sector ETF": "กองทุนที่ติดตามหุ้นในกลุ่มอุตสาหกรรมเดียวกัน",
  },
};

function normalizeText(value) {
  return String(value || "").trim();
}

function languageBucket(language = "en") {
  return String(language || "en").toLowerCase().startsWith("th") ? "th" : "en";
}

export function getLocalizedAssetType(assetType, language = "en") {
  const bucket = languageBucket(language);
  return ETF_TYPE_LABELS[bucket]?.[assetType] || assetType || null;
}

export function getLocalizedAssetTypeDescription(assetType, language = "en") {
  const bucket = languageBucket(language);
  return ETF_TYPE_DESCRIPTION_BY_TYPE[bucket]?.[assetType] || ETF_TYPE_DESCRIPTION_BY_TYPE[bucket]?.ETF || null;
}

export function inferAssetMeta({ symbol = "", name = "", industry = "", exchange = "" } = {}) {
  const ticker = normalizeText(symbol).toUpperCase();
  const rawName = normalizeText(name);
  const rawIndustry = normalizeText(industry);
  const haystack = `${rawName} ${rawIndustry} ${normalizeText(exchange)}`.toLowerCase();

  let assetType = ETF_TYPE_BY_SYMBOL[ticker] || null;

  if (!assetType && ticker.startsWith("XL") && ticker.length <= 4) {
    assetType = "Sector ETF";
  }

  if (
    !assetType
    && (
      haystack.includes("etf")
      || haystack.includes("exchange traded fund")
      || haystack.includes("index fund")
      || haystack.includes("spdr")
      || haystack.includes("trust")
      || haystack.includes("select sector")
      || haystack.includes("ishares")
      || haystack.includes("vanguard")
      || haystack.includes("invesco")
    )
  ) {
    if (haystack.includes("commodity")) {
      assetType = "Commodity ETF";
    } else if (haystack.includes("sector")) {
      assetType = "Sector ETF";
    } else if (haystack.includes("index")) {
      assetType = "Index ETF";
    } else {
      assetType = "ETF";
    }
  }

  const isEtf = Boolean(assetType);
  const displayName = isEtf ? (ETF_NAME_BY_SYMBOL[ticker] || rawName || ticker) : (rawName || ticker);

  let badgeClass = "bg-sky-50 text-sky-700 border-sky-200";
  if (assetType === "Sector ETF") {
    badgeClass = "bg-violet-50 text-violet-700 border-violet-200";
  } else if (assetType === "Index ETF") {
    badgeClass = "bg-blue-50 text-blue-700 border-blue-200";
  } else if (assetType === "Commodity ETF") {
    badgeClass = "bg-amber-50 text-amber-700 border-amber-200";
  }

  return {
    symbol: ticker,
    isEtf,
    assetType,
    displayName,
    badgeLabel: isEtf ? "ETF" : null,
    badgeClass,
  };
}
