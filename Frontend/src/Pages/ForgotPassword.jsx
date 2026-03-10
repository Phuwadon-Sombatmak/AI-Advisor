import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ForgotPassword.css"

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [message] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const navigate = useNavigate();
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
  setError('');

  try {
    const response = await fetch('/api/forgot-password', { // หรือ axios.post
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });

    if (!response.ok) {
      const text = await response.text(); // อ่านเป็น text ก่อน
      let errorMsg = 'เกิดข้อผิดพลาด';

      try {
        const json = JSON.parse(text);
        errorMsg = json.detail || json.message || text;
      } catch {
        errorMsg = text || 'Too many requests หรือ server error';
      }

      if (response.status === 429) {
        errorMsg = 'ส่งคำขอเกินจำนวน กรุณารอสักครู่แล้วลองใหม่';
      }

      throw new Error(errorMsg);
    }

    await response.json();
    alert('ส่งลิงก์รีเซตรหัสเรียบร้อยแล้ว กรุณาตรวจสอบอีเมล');
  } catch (err) {
    console.error('Fetch Error:', err);
    setError(err.message || 'เกิดข้อผิดพลาด กรุณาลองใหม่');
  } finally {
    setLoading(false);
  }
};

  const handleBack = () => navigate("/login");

  return (
    <>
      <div className="back-button">
              <button onClick={handleBack} className="back-btn">Back</button>
      </div>
      
    <div className="forgot-page">
      <img src="/Ail.svg" alt="AI Invest Logo" className="logo-forgot" />
      <div className="forgot-from">
        <h2>ลืมรหัสผ่าน</h2>
          <p>กรอกอีเมลเพื่อรับลิงก์เปลี่ยนรหัสผ่าน</p>

        <form onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <button type="submit" className="forgot-btn" disabled={loading}>
            {loading ? "กำลังส่ง…" : "ส่งลิงก์"}
          </button>
        </form>
      </div>
      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}
    </div>
    </>
  );
}