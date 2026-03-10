import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";

const API_BASE = import.meta.env?.VITE_API_BASE || "http://localhost:8000";

function RecommendationPage() {
  const navigate = useNavigate();
  const [symbol, setSymbol] = useState("");
  const [days, setDays] = useState(7);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const canSubmit = useMemo(() => symbol.trim().length > 0 && !loading, [symbol, loading]);

  const fetchReco = async () => {
    const s = symbol.trim().toUpperCase();
    if (!s) return;
    setLoading(true);
    setErr("");
    setData(null);
    try {
      const res = await fetch(
        `${API_BASE}/recommend?symbol=${encodeURIComponent(s)}&window_days=${days}`,
        { method: "POST" }
      );
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json?.detail || "Request failed");
      }
      setData(json);
    } catch (e) {
      setErr(e?.message || "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
    } finally {
      setLoading(false);
    }
  };

  const handleClick = () => fetchReco();

  const handleBack = () => navigate("/search");

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && canSubmit) {
      fetchReco();
    }
  };

  const pctUpside =
    data && data.current_price
      ? (((data.target_price_mean - data.current_price) / data.current_price) * 100).toFixed(2)
      : null;

  return (
    <div style={{ padding: 35, maxWidth: 760, margin: "0 auto" }}>
        <div className="back-button">
            <button onClick={handleBack} className="back-btn">Back</button>
        </div>
      <h2 style={{ marginBottom: 12 }}>AI Investment Recommendation</h2>

      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 12 }}>
        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="ใส่ชื่อหุ้น เช่น MU, NVDA, MSFT"
          style={{ padding: 10, flex: 1, border: "1px solid #e5e7eb", borderRadius: 8 }}
        />
        <select
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          style={{ padding: 10, border: "1px solid #e5e7eb", borderRadius: 8 }}
        >
          <option value={7}>7 วัน</option>
          <option value={14}>14 วัน</option>
          <option value={30}>30 วัน</option>
        </select>
        <button
          onClick={handleClick}
          disabled={!canSubmit}
          style={{
            padding: "10px 14px",
            borderRadius: 8,
            border: "1px solid transparent",
            background: canSubmit ? "#3b82f6" : "#93c5fd",
            color: "white",
            cursor: canSubmit ? "pointer" : "not-allowed",
            fontWeight: 600,
          }}
        >
          {loading ? "กำลังวิเคราะห์..." : "วิเคราะห์"}
        </button>
      </div>

      {err && (
        <div
          style={{
            background: "#fef2f2",
            color: "#b91c1c",
            padding: 12,
            borderRadius: 8,
            border: "1px solid #fecaca",
            marginBottom: 12,
          }}
        >
          ❌ {err}
        </div>
      )}

      {data && !err && (
        <div style={{ display: "grid", gap: 12 }}>
          <div
            style={{
              border: "1px solid #e5e7eb",
              borderRadius: 12,
              padding: 16,
              background: "#fff",
            }}
          >
            <h3 style={{ margin: 0 }}>{data.symbol}</h3>
            <div style={{ color: "#6b7280", marginTop: 4 }}>
              ช่วงเวลาข่าว: {data.window_days} วัน | ข่าวที่ใช้: {data.news_count}
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
              gap: 12,
            }}
          >
            <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
              <div style={{ color: "#6b7280" }}>คำแนะนำ</div>
              <div style={{ fontWeight: 800, fontSize: 20 }}>{data.recommendation}</div>
              <div style={{ color: "#6b7280", marginTop: 6 }}>
                ความเชื่อมั่น: <b>{Math.round((data.confidence || 0) * 100)}%</b>
              </div>
            </div>

            <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
              <div style={{ color: "#6b7280" }}>ราคาเป้าหมายเฉลี่ย</div>
              <div style={{ fontWeight: 800, fontSize: 20 }}>${data.target_price_mean}</div>
              <div style={{ color: "#6b7280", marginTop: 6 }}>
                ราคาปัจจุบัน: <b>${data.current_price}</b>
              </div>
              <div style={{ color: "#6b7280", marginTop: 6 }}>
                Upside/Downside: <b>{pctUpside ?? "-" }%</b>
              </div>
            </div>

            <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
              <div style={{ color: "#6b7280" }}>สูงสุด / ต่ำสุด</div>
              <div style={{ fontWeight: 800, fontSize: 20 }}>
                ${data.target_price_high} / ${data.target_price_low}
              </div>
            </div>

            <div style={{ border: "1px solid #e5e7eb", borderRadius: 12, padding: 16 }}>
              <div style={{ color: "#6b7280" }}>Sentiment เฉลี่ย</div>
              <div style={{ fontWeight: 800, fontSize: 20 }}>{data.sentiment_avg}</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default RecommendationPage;
