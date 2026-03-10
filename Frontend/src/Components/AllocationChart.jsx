import React from "react";
import { useTranslation } from "react-i18next";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = ["#2563EB", "#38BDF8", "#1E3A8A", "#22C55E", "#F59E0B", "#A855F7"];

export default function AllocationChart({ allocation = [], sectorExposure = [], dark = false }) {
  const { t } = useTranslation();

  return (
    <section className={`${dark ? "bg-[#0F172A] border-slate-700" : "bg-white border-slate-200"} rounded-2xl border p-5 shadow-md space-y-5`}>
      <h3 className={`${dark ? "text-slate-100" : "text-slate-900"} text-xl font-bold`}>{t("portfolioAllocation")}</h3>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={allocation} cx="50%" cy="50%" innerRadius={60} outerRadius={90} dataKey="value" nameKey="name" stroke="none">
              {allocation.map((entry, index) => (
                <Cell key={`${entry.name}-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div className="space-y-2">
        <h4 className={`${dark ? "text-slate-100" : "text-slate-900"} font-bold`}>{t("sectorExposure")}</h4>
        {sectorExposure.map((item, idx) => (
          <div key={`${item.name}-${idx}`}>
            <div className="flex items-center justify-between text-sm mb-1">
              <span className="font-medium text-slate-500">{item.name}</span>
              <span className="font-bold text-slate-700">{item.value}%</span>
            </div>
            <div className="h-2 rounded-full bg-slate-200 overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${item.value}%`, background: "linear-gradient(135deg,#2563EB,#1E3A8A)" }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
