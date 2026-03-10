import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

const SEGMENTS = [
  { from: 0, to: 20, color: "#DC2626" },
  { from: 20, to: 40, color: "#F97316" },
  { from: 40, to: 60, color: "#EAB308" },
  { from: 60, to: 80, color: "#22C55E" },
  { from: 80, to: 100, color: "#15803D" },
];

const scoreToLabel = (score) => {
  if (score <= 24) return { label: "Extreme Fear", color: "#DC2626" };
  if (score <= 44) return { label: "Fear", color: "#F97316" };
  if (score <= 55) return { label: "Neutral", color: "#EAB308" };
  if (score <= 74) return { label: "Greed", color: "#22C55E" };
  return { label: "Extreme Greed", color: "#15803D" };
};

function polar(cx, cy, r, deg) {
  const rad = (Math.PI / 180) * deg;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function arcPath(cx, cy, r, start, end) {
  const s = polar(cx, cy, r, start);
  const e = polar(cx, cy, r, end);
  return `M ${s.x} ${s.y} A ${r} ${r} 0 0 1 ${e.x} ${e.y}`;
}

export default function FearGreedGauge({ value = 50, dark = false }) {
  const { t } = useTranslation();
  const target = Math.max(0, Math.min(100, Number(value) || 0));
  const [animatedScore, setAnimatedScore] = useState(target);

  useEffect(() => {
    setAnimatedScore(target);
  }, [target]);

  const score = Math.round(animatedScore);
  const sentiment = scoreToLabel(score);
  const labelMap = {
    "Extreme Fear": "fearExtremeFear",
    Fear: "fearFear",
    Neutral: "neutral",
    Greed: "fearGreed",
    "Extreme Greed": "fearExtremeGreed",
  };
  const angle = -90 + (animatedScore / 100) * 180;

  return (
    <div className="w-full">
      <div className="relative w-full max-w-[320px] mx-auto">
        <svg viewBox="0 0 240 150" className="w-full">
          {SEGMENTS.map((s, idx) => {
            const start = -180 + (s.from / 100) * 180;
            const end = -180 + (s.to / 100) * 180;
            return <path key={idx} d={arcPath(120, 120, 80, start, end)} stroke={s.color} strokeWidth="14" fill="none" strokeLinecap="round" />;
          })}

          <g
            style={{
              transformOrigin: "120px 120px",
              transform: `rotate(${angle}deg)`,
              transition: "transform 700ms ease-in-out",
            }}
          >
            <line x1="120" y1="120" x2="120" y2="44" stroke={dark ? "#e2e8f0" : "#0F172A"} strokeWidth="4" strokeLinecap="round" />
          </g>
          <circle cx="120" cy="120" r="6" fill={dark ? "#e2e8f0" : "#0F172A"} />
        </svg>

        <div className="absolute inset-0 pt-10 flex flex-col items-center pointer-events-none">
          <p className={`${dark ? "text-slate-100" : "text-slate-900"} text-4xl font-bold leading-none`}>{score}</p>
          <p className="mt-2 text-sm font-semibold" style={{ color: sentiment.color }}>{t(labelMap[sentiment.label] || "neutral")}</p>
        </div>
      </div>
    </div>
  );
}
