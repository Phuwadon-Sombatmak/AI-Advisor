import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Line } from "react-chartjs-2";
import { ArrowLeft, TrendingUp, TrendingDown, Loader2 } from "lucide-react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Filler
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Filler);

function StockdetailContent() {
  const { symbol } = useParams();
  const navigate = useNavigate();

  const [stockData, setStockData] = useState(null);
  const [reco, setReco] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        // 1. ดึงข้อมูลหุ้น
        const resStock = await fetch(`http://127.0.0.1:8000/stock/${symbol}`);
        let stockJson;
        if (!resStock.ok) {
           throw new Error("Backend stock endpoint not found");
        } else {
           stockJson = await resStock.json();
        }
        setStockData(stockJson);
        
        // 2. ดึงคำแนะนำ AI
        const resReco = await fetch(`http://127.0.0.1:8000/recommend?symbol=${symbol}&window_days=30`);
        let recoJson;
        if (!resReco.ok) {
           throw new Error("Backend recommend endpoint not found");
        } else {
           recoJson = await resReco.json();
        }
        setReco(recoJson);

      } catch (e) {
        console.error("Unable to load live market data", e);
        setStockData(null);
        setReco(null);
      } finally {
        setLoading(false);
      }
    };

    if (symbol) {
      fetchData();
    }
  }, [symbol]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-96 text-indigo-600">
        <Loader2 className="animate-spin mb-4" size={48} />
        <p className="font-bold">กำลังวิเคราะห์ข้อมูล {symbol || "AAPL"}...</p>
      </div>
    );
  }

  if (!stockData) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-700 font-semibold">
        Data unavailable for this ticker.
      </div>
    );
  }

  // เตรียมข้อมูลกราฟ
  const chartData = {
    labels: stockData?.history?.map(h => h.date) || [],
    datasets: [
      {
        label: `${symbol || "AAPL"} Price`,
        data: stockData?.history?.map(h => h.close) || [],
        borderColor: "#4f46e5", // Indigo-600
        backgroundColor: "rgba(79, 70, 229, 0.1)",
        fill: true,
        tension: 0.4,
      }
    ]
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false } },
      y: { grid: { color: "#f1f5f9" } }
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in zoom-in duration-500">
      <button 
        onClick={() => navigate(-1)} 
        className="flex items-center gap-2 text-slate-500 hover:text-indigo-600 font-bold transition-colors"
      >
        <ArrowLeft size={20} /> กลับไปหน้าค้นหา
      </button>

      <div className="flex justify-between items-end">
        <div>
          <h1 className="text-5xl font-black text-slate-800">{stockData?.symbol}</h1>
          <p className="text-slate-500 font-medium mt-2">ข้อมูลราคาล่าสุดและบทวิเคราะห์ AI</p>
        </div>
        <div className="text-right">
          <p className="text-5xl font-mono font-black text-slate-800">${stockData?.latest_price}</p>
          <p className="text-emerald-500 font-bold flex items-center justify-end gap-1 mt-1">
            <TrendingUp size={24}/> {stockData?.change}
          </p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-[2rem] border border-slate-100 shadow-sm h-[400px]">
        <Line data={chartData} options={chartOptions} />
      </div>

      {reco && (
        <div className="bg-indigo-600 p-8 rounded-[2rem] shadow-xl text-white grid grid-cols-1 md:grid-cols-3 gap-6 text-center">
          <div>
            <p className="text-indigo-200 font-bold text-sm uppercase tracking-wider">AI Recommendation</p>
            <p className="text-4xl font-black mt-2">{reco.recommendation || "Data unavailable"}</p>
          </div>
          <div className="border-y md:border-y-0 md:border-x border-indigo-400/50 py-4 md:py-0">
            <p className="text-indigo-200 font-bold text-sm uppercase tracking-wider">Target Price</p>
            <p className="text-4xl font-black mt-2">
              {Number.isFinite(Number(reco.target_price)) ? `$${Number(reco.target_price).toFixed(2)}` : "Data unavailable"}
            </p>
          </div>
          <div>
            <p className="text-indigo-200 font-bold text-sm uppercase tracking-wider">AI Confidence</p>
            <p className="text-4xl font-black mt-2">
              {Number.isFinite(Number(reco.confidence)) ? `${Math.round(Number(reco.confidence) * 100)}%` : "Data unavailable"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// Wrapper เพื่อแก้ปัญหา Error: useNavigate() นอก Router
export default function Stockdetail() {
  // This component should be rendered inside the app Router (in `main.jsx`).
  return <StockdetailContent />;
}
