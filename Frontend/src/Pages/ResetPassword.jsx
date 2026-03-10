import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "./ResetPassword.css"

export default function ResetPassword() {
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const navigate = useNavigate();
  const location = useLocation();
  const token = new URLSearchParams(location.search).get("token");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage("");
    setError("");

    if (!token) {
      setError("Token ไม่ถูกต้อง");
      return;
    }

    try {
      const res = await fetch("/api/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });

      const data = await res.json();

      if (res.ok) {
        setMessage("เปลี่ยนรหัสผ่านเรียบร้อยแล้ว");
        setTimeout(() => navigate("/login"), 2000);
      } else {
        setError(data.error || "เกิดข้อผิดพลาด");
      }
    } catch (err) {
      console.error(err);
      setError("เกิดข้อผิดพลาด");
    }
  };

  return (
    <div className="reset-page">
      <img src="/Ail.svg" alt="AI Invest Logo" className="logo-reset" />
      <div className="reset-form">
        <h2>ตั้งรหัสผ่านใหม่</h2>
          <p>กรอกรหัสผ่านใหม่ที่ต้องการ</p>

        <form onSubmit={handleSubmit}>
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <button type="submit" className="reset-btn">
            ยืนยัน
          </button>
        </form>
      </div>

      {message && <p className="success">{message}</p>}
      {error && <p className="error">{error}</p>}
    </div>
  );
}
