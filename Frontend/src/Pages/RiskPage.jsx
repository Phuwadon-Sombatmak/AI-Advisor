import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { TrendingUp, AlertTriangle, ShieldCheck, BarChart2, ChevronLeft } from "lucide-react";

const API_BASE = "http://localhost:8000";

export default function App() {
  const navigate = useNavigate();

  const [selectedRisk, setSelectedRisk] = useState(localStorage.getItem("selectedRisk") || "");
  const [recs, setRecs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const handleRiskClick = (risk) => {
    const r = (risk || "").toLowerCase();
    setSelectedRisk(r);
    localStorage.setItem("selectedRisk", r);
  };

  const handleBack = () => navigate("/search");

  // ตรวจสอบ Authentication
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token && window.location.hostname !== 'localhost') {
      // ปิดไว้ก่อนสำหรับการทดสอบใน environment นี้
      // navigate("/login");
    }
  }, [navigate]);

  // AI Recommendation Engine Logic
  useEffect(() => {
    if (!selectedRisk) return;

    const fetchRecs = async () => {
      try {
        setLoading(true);
        setErr("");
        const level = selectedRisk.toUpperCase();

        const res = await fetch(`${API_BASE}/risk/recommend?level=${level}`);
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        let items = data.items || data.data || data || [];

        setRecs(Array.isArray(items) ? items : []);
      } catch (e) {
        console.error("Fetch error:", e);
        setErr("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้");
        setRecs([]);
      } finally {
        setLoading(false);
      }
    };

    fetchRecs();
  }, [selectedRisk]);

  // คำนวณ Insight รายกลุ่ม (Mathematical Summary)
  const insights = useMemo(() => {
    if (recs.length === 0) return null;
    const avgRisk = recs.reduce((acc, curr) => acc + Number(curr.risk_score || 0), 0) / recs.length;
    const avgRet = recs.reduce((acc, curr) => acc + Number(curr.ret30 || 0), 0) / recs.length;
    return { avgRisk, avgRet };
  }, [recs]);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 p-4 md:p-8 font-sans">
      <div className="max-w-6xl mx-auto">
        
        {/* Header Section */}
        <div className="flex items-center justify-between mb-8">
          <button 
            onClick={handleBack}
            className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 rounded-lg shadow-sm hover:shadow-md transition-all text-sm font-medium"
          >
            <ChevronLeft size={18} /> กลับหน้าค้นหา
          </button>
          <div className="text-right">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-indigo-500 bg-clip-text text-transparent">
              AI-Based Investment
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">Portfolio Optimization Engine</p>
          </div>
        </div>

        {/* Risk Selection Card */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl p-6 mb-8 border border-slate-200 dark:border-slate-700">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
            <div>
              <h2 className="text-xl font-bold flex items-center gap-2 mb-2">
                <BarChart2 className="text-blue-500" /> ระดับความเสี่ยงที่เหมาะสม
              </h2>
              <p className="text-slate-500 dark:text-slate-400 text-sm">
                เลือกระดับความเสี่ยงเพื่อจัดพอร์ตการลงทุนด้วยระบบ AI
              </p>
            </div>
            
            <div className="flex bg-slate-100 dark:bg-slate-700 p-1 rounded-xl w-fit">
              {["low", "medium", "high"].map((risk) => (
                <button
                  key={risk}
                  onClick={() => handleRiskClick(risk)}
                  className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 ${
                    selectedRisk === risk 
                      ? "bg-white dark:bg-slate-600 shadow-sm text-blue-600 dark:text-blue-400 scale-105" 
                      : "text-slate-500 hover:text-slate-700"
                  }`}
                >
                  {risk.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* AI Analysis Overlay */}
        {selectedRisk && insights && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-xl border border-blue-100 dark:border-blue-800">
              <span className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wider">AI Suggestion</span>
              <p className="text-sm mt-1 font-medium">
                {selectedRisk === 'low' && "เน้นการรักษาเงินต้นและปันผลสม่ำเสมอ"}
                {selectedRisk === 'medium' && "สมดุลระหว่างการเติบโตและความผันผวน"}
                {selectedRisk === 'high' && "เน้นส่วนต่างราคา (Capital Gain) ในระยะสั้น-กลาง"}
              </p>
            </div>
            <div className="bg-indigo-50 dark:bg-indigo-900/20 p-4 rounded-xl border border-indigo-100 dark:border-indigo-800">
              <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">Avg. Risk Score</span>
              <p className="text-lg mt-1 font-bold">{insights.avgRisk.toFixed(2)} / 10</p>
            </div>
            <div className="bg-emerald-50 dark:bg-emerald-900/20 p-4 rounded-xl border border-emerald-100 dark:border-emerald-800">
              <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider">Expected 30D Return</span>
              <p className={`text-lg mt-1 font-bold ${insights.avgRet >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                {(insights.avgRet * 100).toFixed(2)}%
              </p>
            </div>
          </div>
        )}

        {/* Data Table Section */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-lg overflow-hidden border border-slate-200 dark:border-slate-700">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 dark:bg-slate-700/50 text-slate-500 dark:text-slate-400 text-xs uppercase tracking-widest">
                  <th className="px-6 py-4 font-bold">Symbol</th>
                  <th className="px-6 py-4 font-bold">Risk Level</th>
                  <th className="px-6 py-4 font-bold">Risk Score</th>
                  <th className="px-6 py-4 font-bold text-center">Vol (90d)</th>
                  <th className="px-6 py-4 font-bold text-center">Max Drawdown</th>
                  <th className="px-6 py-4 font-bold text-right">30D Return</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {loading ? (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-3">
                        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                        <span className="animate-pulse">AI is analyzing stock data...</span>
                      </div>
                    </td>
                  </tr>
                ) : recs.length > 0 ? (
                  recs.map((r, idx) => (
                    <tr 
                      key={r.Symbol + idx} 
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors group"
                    >
                      <td className="px-6 py-4">
                        <div className="flex flex-col">
                          <a href={`/stock/${r.Symbol}`} className="font-bold text-blue-600 dark:text-blue-400 hover:underline">
                            {r.Symbol}
                          </a>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                         <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${
                           r.risk_label === 'LOW' ? 'bg-emerald-100 text-emerald-700' :
                           r.risk_label === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                           'bg-rose-100 text-rose-700'
                         }`}>
                           {r.risk_label}
                         </span>
                      </td>
                      <td className="px-6 py-4 font-mono font-medium">
                        {Number(r.risk_score).toFixed(2)}
                      </td>
                      <td className="px-6 py-4 text-center font-mono">
                        {Number(r.vol90).toFixed(3)}
                      </td>
                      <td className="px-6 py-4 text-center text-red-500 font-mono">
                        {r.mdd1y != null ? `${(Number(r.mdd1y) * 100).toFixed(1)}%` : "-"}
                      </td>
                      <td className={`px-6 py-4 text-right font-bold font-mono ${Number(r.ret30) >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {r.ret30 != null ? `${(Number(r.ret30) * 100).toFixed(2)}%` : "-"}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan="6" className="px-6 py-12 text-center text-slate-400">
                      <div className="flex flex-col items-center gap-2">
                        <AlertTriangle size={32} className="text-amber-400" />
                        <p>ยังไม่มีข้อมูลในระดับความเสี่ยงนี้</p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {err && (
          <div className="mt-4 p-3 bg-rose-50 dark:bg-rose-900/20 border border-rose-100 dark:border-rose-800 rounded-lg text-rose-600 dark:text-rose-400 text-sm">
            {err}
          </div>
        )}
      </div>
    </div>
  );
}
