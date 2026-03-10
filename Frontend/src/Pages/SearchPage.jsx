import React, { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Search, ArrowLeft, Loader2, Sparkles } from "lucide-react";

const stocksList = [
  { name: "NVIDIA Corporation", symbol: "NVDA", sector: "Technology" },
  { name: "Microsoft Corporation", symbol: "MSFT", sector: "Technology" },
  { name: "Apple Inc.", symbol: "AAPL", sector: "Technology" },
  { name: "Tesla, Inc.", symbol: "TSLA", sector: "Consumer Discretionary" },
  { name: "Amazon.com, Inc.", symbol: "AMZN", sector: "Consumer Discretionary" },
];

function SearchPageContent() {
  const [query, setQuery] = useState("");
  const [dailyNews, setDailyNews] = useState([]);
  const [loadingNews, setLoadingNews] = useState(true);
  const [aiState, setAiState] = useState({ loading: false, result: null, error: null });
  const navigate = useNavigate();

  // ฟังก์ชันดึงข่าว
  useEffect(() => {
    const fetchNews = async () => {
      setLoadingNews(true);
      try {
        // ลองดึงจาก Backend
        const res = await fetch("http://127.0.0.1:8000/api/news");
        if (!res.ok) throw new Error("Network error");
        const data = await res.json();
        setDailyNews(data.news || []);
      } catch (e) {
        console.warn("⚠️ เชื่อมต่อ Backend ไม่ได้ ระบบจะแสดงข่าวสารจำลองแทน", e);
        // Fallback: ข้อมูลจำลองหาก Backend ไม่ทำงาน
        setDailyNews([
          { 
            title: "NVIDIA เผยชิป AI รุ่นใหม่ ดันหุ้นกลุ่มเทคโนโลยีพุ่งทะยาน", 
            provider: "Tech Daily", 
            link: "#",
            image: "https://images.unsplash.com/photo-1614064641913-a53b15680334?w=500&q=80"
          },
          { 
            title: "Apple เตรียมเปิดตัวอุปกรณ์สวมใส่รุ่นใหม่ คาดทำยอดขายทะลุเป้า", 
            provider: "Market Watch", 
            link: "#",
            image: "https://images.unsplash.com/photo-1510557880182-3d4d3cba35a5?w=500&q=80"
          },
          { 
            title: "ธนาคารกลางสหรัฐฯ ส่งสัญญาณคงอัตราดอกเบี้ย นักลงทุนจับตาใกล้ชิด", 
            provider: "Finance News", 
            link: "#",
            image: "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=500&q=80"
          }
        ]);
      } finally {
        setLoadingNews(false);
      }
    };
    fetchNews();
  }, []);

  // ฟังก์ชันจัดการตอนกดค้นหา
  const handleSearch = (e) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/stock/${query.toUpperCase()}`);
    }
  };

  // ฟังก์ชัน AI วิเคราะห์ข่าว
  const generateMarketAnalysis = async () => {
    if (dailyNews.length === 0) return;
    
    setAiState({ loading: true, result: null, error: null });
    const apiKey = ""; // API Key ฉีดผ่าน Canvas อัตโนมัติ
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key=${apiKey}`;
    
    const newsText = dailyNews.map((n, i) => `${i + 1}. ${n.title}`).join("\n");
    const payload = {
      contents: [{ parts: [{ text: `วิเคราะห์ข่าวเหล่านี้แล้วสรุปภาพรวมตลาด (Bullish/Bearish/Neutral) สั้นๆ กระชับ:\n${newsText}` }] }],
      systemInstruction: { parts: [{ text: "คุณคือนักวิเคราะห์การเงิน สรุปข่าวเป็นภาษาไทยที่อ่านเข้าใจง่าย" }] }
    };

    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) throw new Error(`API Error`);
      const data = await response.json();
      const textResult = data.candidates?.[0]?.content?.parts?.[0]?.text;
      
      if (textResult) {
        setAiState({ loading: false, result: textResult, error: null });
      } else {
        throw new Error("No data");
      }
    } catch (err) {
      console.error("AI generateMarketAnalysis error:", err);
      setAiState({ loading: false, result: null, error: "เกิดข้อผิดพลาดในการเชื่อมต่อกับ AI" });
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-12 pb-20">
      {/* 1. ส่วนค้นหาหุ้น */}
      <div className="bg-white p-10 rounded-[2rem] shadow-sm border border-slate-100 text-center relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500"></div>
        <h1 className="text-4xl font-black text-slate-800 mb-4 tracking-tight">ค้นหาหุ้นที่คุณสนใจ</h1>
        <p className="text-slate-500 text-lg mb-8 font-medium">วิเคราะห์ด้วย AI พร้อมประเมินความเสี่ยงทันที</p>
        
        <form onSubmit={handleSearch} className="max-w-2xl mx-auto relative group">
          <input
            type="text"
            placeholder="เช่น NVDA, MSFT, AAPL..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-6 pr-16 py-5 rounded-2xl bg-slate-50 border border-slate-200 focus:bg-white focus:outline-none focus:ring-4 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-lg font-bold text-slate-700 uppercase"
          />
          <button type="submit" className="absolute right-3 top-3 bottom-3 aspect-square bg-indigo-600 text-white rounded-xl flex items-center justify-center hover:bg-indigo-700 transition-colors">
            <Search size={24} />
          </button>
        </form>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <span className="text-slate-400 font-medium py-2">หุ้นยอดนิยม:</span>
          {stocksList.map(s => (
            <button key={s.symbol} onClick={() => navigate(`/stock/${s.symbol}`)} className="px-5 py-2 bg-white border border-slate-200 rounded-xl hover:border-indigo-600 hover:text-indigo-600 text-sm font-bold text-slate-600 transition-colors shadow-sm">
              {s.symbol}
            </button>
          ))}
        </div>
      </div>

      {/* 2. ส่วนแสดงข่าวสารและ AI */}
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <h2 className="text-2xl font-black text-slate-800 flex items-center gap-2">ข่าวสารตลาดล่าสุด</h2>
          
          {!loadingNews && dailyNews.length > 0 && (
            <button 
              onClick={generateMarketAnalysis}
              disabled={aiState.loading}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold rounded-xl shadow-md hover:shadow-lg transition-all disabled:opacity-70 disabled:cursor-not-allowed"
            >
              {aiState.loading ? <><Loader2 size={20} className="animate-spin" /> กำลังประมวลผล...</> : <><Sparkles size={20} /> สรุปภาพรวมด้วย AI</>}
            </button>
          )}
        </div>

        {/* ผลลัพธ์จาก AI */}
        {aiState.error && <div className="p-4 bg-rose-50 text-rose-600 border border-rose-200 rounded-xl font-medium">{aiState.error}</div>}
        {aiState.result && (
          <div className="p-6 md:p-8 bg-gradient-to-br from-indigo-50 to-purple-50 border border-indigo-100 rounded-[2rem] shadow-inner relative overflow-hidden">
            <h3 className="text-xl font-black text-indigo-900 mb-4 flex items-center gap-2"><Sparkles size={24} className="text-amber-500" /> บทวิเคราะห์ภาพรวมตลาด</h3>
            <div className="text-slate-700 leading-relaxed font-medium whitespace-pre-wrap">{aiState.result}</div>
          </div>
        )}

        {/* รายการข่าว */}
        {loadingNews ? (
          <div className="flex justify-center py-10"><Loader2 className="animate-spin text-indigo-600 w-10 h-10" /></div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {dailyNews.map((news, i) => (
              <a key={i} href={news.link} target="_blank" rel="noopener noreferrer" className="bg-white rounded-2xl border border-slate-100 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 group flex flex-col h-full">
                <div className="h-48 bg-slate-200 overflow-hidden shrink-0">
                  <img src={news.image} alt="news" className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
                </div>
                <div className="p-6 flex flex-col grow">
                  <p className="text-xs font-bold text-indigo-600 mb-2 uppercase tracking-wide">{news.provider}</p>
                  <h3 className="font-bold text-slate-800 text-lg leading-tight group-hover:text-indigo-600 transition-colors">{news.title}</h3>
                </div>
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// Wrapper สำหรับโหมดทดสอบ
function MockStockDetailPreview() {
  const { symbol } = useParams();
  const navigate = useNavigate();
  return (
    <div className="max-w-3xl mx-auto mt-20 p-10 bg-indigo-50 border border-indigo-100 rounded-[2rem] text-center shadow-sm">
      <h2 className="text-3xl font-black text-indigo-900 mb-4">จำลองการเปลี่ยนหน้าจอ</h2>
      <p className="text-lg text-indigo-700 mb-8">กำลังพาคุณไปยังหน้าข้อมูลของหุ้น <span className="font-black bg-indigo-600 text-white px-3 py-1 rounded-lg mx-2">{symbol}</span></p>
      <button onClick={() => navigate("/")} className="inline-flex items-center gap-2 px-6 py-3 bg-white text-indigo-600 font-bold rounded-xl shadow-sm hover:shadow-md transition-all"><ArrowLeft size={20} /> กลับไปหน้าค้นหา</button>
    </div>
  );
}

export default function SearchPage() {
  // This component is intended to be used inside the app router.
  // Always render the main content — do not mount a nested Router here.
  return <SearchPageContent />;
}