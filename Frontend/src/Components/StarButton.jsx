import React from "react";
import { Star } from "lucide-react";

export default function StarButton({ active, onToggle, size = "md", className = "", title = "Toggle watchlist" }) {
  const sizes = {
    sm: "h-8 w-8",
    md: "h-9 w-9",
    lg: "h-10 w-10",
  };

  return (
    <button
      type="button"
      onClick={onToggle}
      title={title}
      aria-label={title}
      className={`${sizes[size] || sizes.md} inline-flex items-center justify-center rounded-full border transition-all duration-200 ${
        active
          ? "bg-amber-100 border-amber-300 text-amber-500 shadow-[0_6px_16px_rgba(245,158,11,0.35)]"
          : "bg-white/90 border-slate-200 text-slate-400 hover:text-amber-500 hover:border-amber-300"
      } hover:-translate-y-0.5 hover:scale-105 ${className}`}
    >
      <Star size={18} className={active ? "fill-current" : ""} />
    </button>
  );
}
