import React, { useState, useEffect, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { LanguageContext } from "../Components/LanguageContext";
import zxcvbn from "zxcvbn";
import "./RegisterPage.css";

export default function RegisterPage() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [dobDay, setDobDay] = useState("");
    const [dobMonth, setDobMonth] = useState("");
    const [dobYear, setDobYear] = useState("");
    const [showPassword, _setShowPassword] = useState(false);
    const [error, setError] = useState("");
    const [passwordScore, setPasswordScore] = useState(0);
    const navigate = useNavigate();
    
    // ตั้งค่า Default ภาษากรณีหา Context ไม่เจอ (ป้องกัน Error)
    const { language = "th" } = useContext(LanguageContext) || {};

    const t = {
        en: {
            register: "Register", 
            email: "Email", 
            password: "Password", 
            confirmpass: "Confirm Password", 
            alredy: "Already have an account? Log in", 
            confirm: "Confirm",
            dob: "Date of Birth",
            day: "Day",
            month: "Month",
            year: "Year",
            back: "Back"
        },
        th: {
            register: "สมัครสมาชิก", 
            email: "อีเมล", 
            password: "รหัสผ่าน", 
            confirmpass: "ยืนยันรหัสผ่าน", 
            alredy: "มีบัญชีอยู่แล้วใช่ไหม? เข้าสู่ระบบ", 
            confirm: "ยืนยัน",
            dob: "เกิดวันที่",
            day: "วัน",
            month: "เดือน",
            year: "ปี",
            back: "กลับ"
        },
    };

    const [honeypot, setHoneypot] = useState(""); // ถ้าบอทกรอก = บล็อก
    const [startTime, setStartTime] = useState(Date.now()); // ตรวจว่ามนุษย์ใช้เวลาไม่น้อยกว่า 3 วินาที
    
    useEffect(() => {
        setStartTime(Date.now()); // รีเซ็ตทุกครั้งที่เข้าเว็บ
    }, []);

    const validateEmail = (email) => /\S+@\S+\.\S+/.test(email);
    
    // ฟังก์ชันตรวจสอบอายุ >= 18
    const isOver18 = (birthDate) => {
        const today = new Date();
        const dobDate = new Date(birthDate);
        let age = today.getFullYear() - dobDate.getFullYear();
        const m = today.getMonth() - dobDate.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < dobDate.getDate())) {
            age--;
        }
        return age >= 18;
    };

    const getPasswordStrength = (score) => {
        switch(score) {
            case 0: return { label: "แย่มาก", color: "#ff4d4f" };
            case 1: return { label: "แย่", color: "#ff7a45" };
            case 2: return { label: "พอใช้", color: "#f19f3aff" };
            case 3: return { label: "แข็งแรง", color: "#6dac49ff" };
            case 4: return { label: "แข็งแรงมาก", color: "#3ba108ff" };
            default: return { label: "", color: "#d9d9d9" };
        }
    };

    const days = Array.from({ length: 31 }, (_, i) => i + 1);
    const months = Array.from({ length: 12 }, (_, i) => i + 1);
    const currentYear = new Date().getFullYear();
    const years = Array.from({ length: 100 }, (_, i) => currentYear - i);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError("");

        // Anti-bot checks
        if (honeypot !== "") {
            setError("การสมัครถูกปฏิเสธ (Bot Detected)");
            return;
        }

        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed < 3) {
            setError("การสมัครเร็วเกินไป กรุณาลองใหม่อีกครั้ง");
            return;
        }

        if (!validateEmail(email)) {
            setError("รูปแบบอีเมลไม่ถูกต้อง");
            return;
        }

        if (!dobDay || !dobMonth || !dobYear) {
            setError("กรุณากรอกวันเดือนปีเกิดให้ครบ");
            return;
        }

        const dob = `${dobYear}-${dobMonth.padStart(2, '0')}-${dobDay.padStart(2, '0')}`;

        if (!isOver18(dob)) {
            setError("คุณต้องมีอายุอย่างน้อย 18 ปี จึงจะสามารถสมัครได้");
            return;
        }

        if (password.length < 6) {
            setError("รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร");
            return;
        }

        if (passwordScore < 3) {
            setError("รหัสผ่านต้องแข็งแรงระดับ 'แข็งแรง' ขึ้นไป");
            return;
        }

        if (password !== confirmPassword) {
            setError("รหัสผ่านไม่ตรงกัน");
            return;
        }

        try {
            // เรียกใช้ reCAPTCHA (ต้องแน่ใจว่า import script ของ recaptcha มาแล้วใน index.html)
            const token = await window.grecaptcha.execute(
                "6Lc72B8sAAAAAPDSG1yY8RsQKvyqLyleDSh2wunz",
                { action: "register" }
            );

            const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";
            console.log("Register API_URL:", API_URL);
            const endpoint = API_URL.startsWith("http") ? `${API_URL}/api/register` : `${API_URL}/register`;
            console.log("Register endpoint:", endpoint);

            const res = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "ngrok-skip-browser-warning": "69420"
                },
                body: JSON.stringify({
                    email,
                    password,
                    dob,
                    recaptcha: token
                }),
                credentials: "include"
            });

            // Safely parse response body: some error pages (404, proxies) return HTML/text
            const raw = await res.text();
            let data;
            try {
                data = raw ? JSON.parse(raw) : {};
            } catch {
                console.warn("Register: response not JSON, raw:", raw);
                data = { error: raw };
            }
            console.log("Register response status:", res.status, "body:", raw);

            if (!res.ok) {
                if (data.error?.includes("reCAPTCHA")) {
                    setError("การตรวจสอบ reCAPTCHA ล้มเหลว กรุณาลองใหม่");
                } else if (data.error?.includes("email")) {
                    setError("อีเมลนี้ถูกใช้ไปแล้วหรือรูปแบบไม่ถูกต้อง");
                } else {
                    setError(data.error || "เกิดข้อผิดพลาดในการสมัครสมาชิก");
                }
                return;
            }

            // สมัครสำเร็จไปหน้า verify
            navigate("/verify");

        } catch {
            console.error("Register error");
            setError("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์ได้ กรุณาลองใหม่ภายหลัง");
        }
    };

    const handleBack = () => {
        setTimeout(() => {
            navigate("/login", { replace: true });
        }, 300);
    };

    return (
        <>
            <div className="back-button">
                <button onClick={handleBack} className="back-btn">
                    {t[language]?.back || "Back"}
                </button>
            </div>

            <div className="register-container">
                <img src="/Ail.svg" alt="AI Invest Logo" className="logo-register" />
            
                <div className="register-form">
                    <h3>{t[language]?.register}</h3>
                    <form onSubmit={handleSubmit}>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            placeholder={t[language]?.email}
                            required
                        />

                        {/* ช่องกรอกวันเกิดแบบ Dropdown */}
                        <div className="dob-select">
                            <p>{t[language]?.dob}</p>
                            <select value={dobDay} onChange={e => setDobDay(e.target.value)} required>
                                <option value="">{t[language]?.day}</option>
                                {days.map(d => (
                                    <option key={d} value={d < 10 ? `0${d}` : d}>{d}</option>
                                ))}
                            </select>

                            <select value={dobMonth} onChange={e => setDobMonth(e.target.value)} required>
                                <option value="">{t[language]?.month}</option>
                                {months.map(m => (
                                    <option key={m} value={m < 10 ? `0${m}` : m}>{m}</option>
                                ))}
                            </select>

                            <select value={dobYear} onChange={e => setDobYear(e.target.value)} required>
                                <option value="">{t[language]?.year}</option>
                                {years.map(y => (
                                    <option key={y} value={y}>{y}</option>
                                ))}
                            </select>
                        </div>

                        {/* Honeypot ป้องกันบอท (ซ่อนด้วย CSS) */}
                        <input
                            type="text"
                            value={honeypot}
                            onChange={e => setHoneypot(e.target.value)}
                            className="bot-field"
                            autoComplete="off"
                            tabIndex="-1"
                        />

                        <div className="password-wrapper">
                            <input
                                type={showPassword ? "text" : "password"}
                                value={password}
                                onChange={e => {
                                    setPassword(e.target.value);
                                    const result = zxcvbn(e.target.value);
                                    setPasswordScore(result.score);
                                }}
                                placeholder={t[language]?.password}
                                required
                            />
                        </div>

                        {/* แถบแสดง Password Strength */}
                        {password && (
                            <div className="password-strength">
                                <div
                                    className="strength-bar"
                                    style={{
                                        width: `${(passwordScore + 1) * 20}%`,
                                        backgroundColor: getPasswordStrength(passwordScore).color
                                    }}
                                />
                                <p style={{ color: getPasswordStrength(passwordScore).color }}>
                                    {getPasswordStrength(passwordScore).label}
                                </p>
                            </div>
                        )}

                        <div className="password-wrapper">
                            <input
                                type={showPassword ? "text" : "password"}
                                value={confirmPassword}
                                onChange={e => setConfirmPassword(e.target.value)}
                                placeholder={t[language]?.confirmpass}
                                required
                            />
                        </div>
                        
                        {error && <p className="error">{error}</p>}
                        
                        <button type="submit" className="btn-register">
                           {t[language]?.confirm}
                        </button>
                    </form>
                    
                    <span 
                        className="goto-login" 
                        onClick={() => navigate("/login", { replace: true })}
                        style={{ cursor: "pointer", display: "block", marginTop: "15px", color: "blue", textDecoration: "underline" }}
                    >
                        {t[language]?.alredy}
                    </span>
                </div>
            </div>
        </>
    );
}