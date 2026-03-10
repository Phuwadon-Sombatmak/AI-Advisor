import React, { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import NewsCard from "./NewsCard";

function SkeletonCard({ dark }) {
  return (
    <div className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md animate-pulse`}>
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="w-full sm:w-40 h-24 rounded-xl bg-slate-200" />
        <div className="flex-1 space-y-3">
          <div className="h-4 w-5/6 rounded bg-slate-200" />
          <div className="h-4 w-2/3 rounded bg-slate-200" />
          <div className="h-3 w-1/3 rounded bg-slate-200" />
        </div>
      </div>
    </div>
  );
}

export default function NewsFeed({ items, loading, dark, bookmarkedNews = [], onToggleBookmark = () => {} }) {
  const { t } = useTranslation();
  const [visibleCount, setVisibleCount] = useState(6);
  const observerRef = useRef(null);
  const loadMoreRef = useRef(null);

  useEffect(() => {
    setVisibleCount(6);
  }, [items]);

  useEffect(() => {
    if (!loadMoreRef.current) return;
    if (visibleCount >= items.length) return;
    observerRef.current?.disconnect();
    observerRef.current = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setVisibleCount((prev) => Math.min(prev + 4, items.length));
        }
      },
      { threshold: 0.2 }
    );
    observerRef.current.observe(loadMoreRef.current);
    return () => observerRef.current?.disconnect();
  }, [items.length, visibleCount]);

  if (loading) {
    return (
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Array.from({ length: 4 }).map((_, idx) => (
          <SkeletonCard key={idx} dark={dark} />
        ))}
      </section>
    );
  }

  if (!items.length) {
    return (
      <div className={`${dark ? "bg-[#0F172A] border-slate-700 text-slate-300" : "bg-white border-slate-200 text-slate-500"} rounded-2xl border p-10 shadow-md`}>
        {t("newsNoData")}
      </div>
    );
  }

  const visibleItems = items.slice(0, visibleCount);

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {visibleItems.map((item, idx) => (
          <NewsCard
            key={`${item.id}-${item.timestamp || 0}-${idx}`}
            news={item}
            dark={dark}
            variant="intel"
            isBookmarked={bookmarkedNews.some((x) => x.id === item.id)}
            onToggleBookmark={onToggleBookmark}
          />
        ))}
      </section>

      {visibleCount < items.length ? (
        <div ref={loadMoreRef} className="py-2 text-center text-sm text-slate-500">
          {t("loadingMore")}
        </div>
      ) : null}
    </div>
  );
}
