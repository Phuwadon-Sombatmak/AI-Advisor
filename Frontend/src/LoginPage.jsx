/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import "./LoginPage.css";
import { LanguageContext } from "./Components/LanguageContext";
import { AuthContext } from "./Components/AuthContext";


export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [showPassword, setShowPassword] = useState(false); // สถานะแสดงรหัส
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const { language } = useContext(LanguageContext);
  const { loginAsGuest } = useContext(AuthContext);

  console.log("Language context:", { language });
  const navigate = useNavigate();

  const t = {
    en: {
      title: "AI-BASED INVESTMENT RECOMMENDATION SYSTEM",
      email: "Email Address",
      password: "Password",
      remember: "Remember me",
      forgot: "Forgot Password?",
      signin: "Sign in",
      signup: "Sign up",
      loading: "LOADING...",
    },
    th: {
      title: "ระบบแนะนำการลงทุนด้วย AI",
      email: "อีเมล",
      password: "รหัสผ่าน",
      remember: "จดจำฉันไว้",
      forgot: "ลืมรหัสผ่าน?",
      signin: "เข้าสู่ระบบ",
      signup: "สมัครสมาชิก",
      loading: "กำลังโหลด...",
    },
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage("");
    setIsLoading(true);

    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });

      const rawText = await response.text();
      let data = {};
      try {
        data = rawText ? JSON.parse(rawText) : {};
      } catch {
        data = {};
      }

      if (!response.ok) {
        setIsLoading(false);   // ✅ ปิด loading
        setErrorMessage(
          data.error ||
            (response.status >= 500
              ? "ไม่สามารถเข้าสู่ระบบได้ในขณะนี้"
              : "Invalid email or password")
        );
        return;
      }

      localStorage.setItem("token", data.token);
      localStorage.setItem("username", data.username);

      setIsLoading(false);
      navigate("/search", { replace: true });

    } catch {
      setIsLoading(false);
      setErrorMessage("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้");
    }
  };

  useEffect(() => {
    document.body.style.overflow = "hidden"; // ล็อค scroll
    return () => {
      document.body.style.overflow = "auto"; // ปลดล็อคเมื่อออกจากหน้า
    };
  }, []);

  useEffect(() => {
    const savedEmail = localStorage.getItem("rememberedEmail");
    if (savedEmail) {
      setEmail(savedEmail);
      setRemember(true);
    }
  }, []);

  useEffect(() => {
    console.log("isLoading เปลี่ยนเป็น:", isLoading === false ? "– false" : isLoading);
  }, [isLoading]);

  return (
    <div className="login-container">
      <div className="login-left">
        <div className="logo-circle">
          <img src="/Ail.svg" alt="AI Invest Logo" className="logo-img" />
        </div>
      </div>

      <div className="login-right">
        <div className="login-form">
          <h3>ระบบแนะนำการลงทุนด้วย AI</h3>
          <img src="/Ail.svg" alt="AI Invest Logo" className="logo-top" />
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t[language]?.email || t.en.email}
              required
            />
            {/* email error removed; using generic errorMessage below */}

            <div className="password-wrapper">
              <input
                type={showPassword ? "text" : "password"} // เปลี่ยน type ตาม showPassword
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t[language]?.password || t.en.password}
                required
              ></input>
              <button
                type="button"
                className="toggle-password"
                onClick={() => setShowPassword(!showPassword)}
              ></button>
            </div>
            {errorMessage && <p className="error-message">{errorMessage}</p>}

            <div className="login-options">
              <label>
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={() => setRemember(!remember)}
                />
                {t[language]?.remember || t.en.remember}
              </label>
              <span
                className="forgot"
                onClick={() => navigate("/forgot-password")}
                style={{ cursor: "pointer", color: "#3b82f6" }}
              >
                {t[language]?.forgot}
              </span>
            </div>

            <button type="submit" className="btn-login">
              {t[language]?.signin || t.en.signin}
            </button>
            <button
              type="button"
              className="register-link"
              onClick={() => {
                console.log("กด Sign up → onClick ถูกเรียกจริง");
                alert("ปุ่ม Sign up ถูกกด! กำลังไป register");
                navigate("/register", { replace: true });
              }}
            >
              {t[language]?.signup || t.en.signup}
            </button>
            <button
              type="button"
              className="guest-btn"
              onClick={() => {
                loginAsGuest();
              }}
            >
              เข้าใช้งานแบบ Guest
            </button>
          </form>
        </div>
      </div>

      <AnimatePresence>
        {isLoading && (
          <motion.div 
          className="loading-content">
            <img src="/Ail.svg" alt="AI Invest Logo" className="loading-logo" />
            <div className="loading-bar">
              <div className="loading-progress"></div>
            </div>
            <p className="loading-text">{t[language]?.loading || t.en.loading}</p>
        </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
