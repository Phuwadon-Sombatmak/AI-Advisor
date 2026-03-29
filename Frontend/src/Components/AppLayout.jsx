import React, { useEffect } from "react";

export default function AppLayout({ theme = "light", sidebar, topbar, children }) {
  const dark = theme === "dark";

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return (
    <div className={`${dark ? "bg-[#020617] text-slate-100" : "bg-[#F8FAFC] text-slate-900"} h-screen font-sans overflow-hidden`}>
      {sidebar}

      <main className="ml-[80px] md:ml-[260px] h-screen overflow-y-auto overflow-x-hidden min-w-0">
        {topbar}
        <div className="p-6 min-w-0">
          <div className="max-w-[1400px] mx-auto min-w-0">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
