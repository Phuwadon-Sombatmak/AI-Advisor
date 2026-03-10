import React from "react";
import SentimentIndicator from "./SentimentIndicator";

export default function SentimentIndicators({ indicators = [], dark = false }) {
  return (
    <div className="space-y-4">
      {indicators.map((it) => (
        <SentimentIndicator key={it.label} label={it.label} value={it.value} dark={dark} />
      ))}
    </div>
  );
}
