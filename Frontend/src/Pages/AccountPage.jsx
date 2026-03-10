import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./AccountPage.css"; // สร้าง CSS ตามต้องการ

export default function AccountPage () {
  const navigate = useNavigate();

  const [selectedRisk, setSelectedRisk] = useState(localStorage.getItem("selectedRisk") || "");
  const [riskGroups, setRiskGroups] = useState({ low: [], medium: [], high: [] });
  const [loading, setLoading] = useState(false);
  
  const handleRiskClick = (risk) => {
    setSelectedRisk(risk);
    localStorage.setItem("selectedRisk", risk);
  };

  const handleBack = () => navigate("/search"); // กลับไปหน้า dashboard
  
  useEffect(() => {
    // ถ้าไม่ login ให้ไปหน้า login
    const isLoggedIn = localStorage.getItem("isLoggedIn");
    if (!isLoggedIn) {
      navigate("/login");
    }
  }, [navigate]);

  const riskExplain = {
    low: "ความเสี่ยงต่ำ: หุ้นในกลุ่มนี้มักเป็นหุ้นพื้นฐานดี ราคาผันผวนน้อย เหมาะกับการลงทุนระยะยาว",
    medium: "ความเสี่ยงปานกลาง: หุ้นกลุ่มธุรกิจเติบโต มีโอกาสสร้างผลตอบแทนสูงแต่มีปัจจัยเสี่ยงมากกว่า",
    high: "ความเสี่ยงสูง: หุ้นผันผวนตามข่าวและเศรษฐกิจโลก เหมาะสำหรับผู้ที่รับความเสี่ยงได้"
  };

  useEffect(() => {
    const tickers = ["NVDA","MSFT","AMZN","UNH","AMD","GOOGL","MU","TSM","NVO","META","V","BRK-A"];
    const fetchRiskData = async () => {
      setLoading(true);
      try {
        const groups = { low: [], medium: [], high: [] };
        for (const t of tickers) {
          const res = await fetch(`http://localhost:8000/risk/${t}`);
          const data = await res.json();
          if (data.risk_level === "LOW") groups.low.push(t);
          else if (data.risk_level === "MEDIUM") groups.medium.push(t);
          else groups.high.push(t);
        }
        setRiskGroups(groups);
      } catch (err) {
        console.error("❌ Error fetching risk data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchRiskData();
  }, []);

  return (
    <div className="account-page relative min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-gray-100 flex flex-col items-center justify-center p-6 transition-all duration-500">
        <div className="back-button">
          <button
            onClick={handleBack} className="back-btn">
            Back
          </button>
        </div>
          <h3 className="text-xl font-semibold mb-4 text-gray-800 dark:text-gray-100 flex items-center gap-2">
            Account Information
          </h3>
        {/* ปุ่มเลือกความเสี่ยง */}
        <div className="risk-card">
          <p className="text-xl font-semibold mb-4 text-gray-800 font-inter">
            Selected Risk:{" "}
            <span className="font-bold text-blue-600">
              {selectedRisk ? selectedRisk.toUpperCase() : "ยังไม่ได้เลือก"}
            </span>
          </p>
          <div className="risk-buttons">
          {["low", "medium", "high"].map(risk => (
            <button
              key={risk}
              className={`risk-button ${risk} ${selectedRisk === risk ? "active" : ""}`}
              onClick={() => handleRiskClick(risk)}
            >
              {risk.charAt(0).toUpperCase() + risk.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {selectedRisk && (
        <div className="mt-2 flex flex-col gap-4 w-full max-w-md">
          <div className="risk-explain-card p-4 rounded bg-white dark:bg-gray-800 shadow-md">
            <h4 className="mb-2 font-bold text-blue-900 dark:text-blue-200">คำอธิบายความเสี่ยง</h4>
            <p>{riskExplain[selectedRisk]}</p>
          </div>

          <div className="stock-list-card p-4 rounded bg-white dark:bg-gray-800 shadow-md w-full max-w-md">
            <h5 className="mb-4 font-semibold text-blue-700 dark:text-blue-400">
              หุ้นแนะนำจากระบบจำแนกความเสี่ยง
            </h5>
            {loading ? (
              <p>Loading risk data...</p>
            ) : (
              <div className="stock-grid">
                {riskGroups[selectedRisk]?.length > 0 ? (
                  riskGroups[selectedRisk].map((stock) => (
                    <div
                      key={stock}
                      className={`stock-card dark:text-gray-100`}
                      onClick={() => navigate(`/stock/${stock}`)}
                    >
                      {stock}
                    </div>
                  ))
                ) : (
                  <div className="text-gray-500 col-span-2">ไม่มีข้อมูล</div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

