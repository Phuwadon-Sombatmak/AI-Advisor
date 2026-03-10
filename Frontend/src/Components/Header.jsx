import { Link, useNavigate } from "react-router-dom";
import { useState, useEffect, useRef, useContext } from "react";
import { BsMoonStars, BsDoorOpenFill, BsFillPersonFill } from "react-icons/bs";
import { GiHamburgerMenu, GiDiceTarget } from "react-icons/gi";
import { IoMailOutline } from "react-icons/io5";
import { GrLanguage } from "react-icons/gr";
import { PiSpeedometer } from "react-icons/pi";
import { FaStar } from "react-icons/fa";
import { LanguageContext } from "./LanguageContext";
import "./Header.css";

export default function Header() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState(localStorage.getItem("theme") || "light");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const username = localStorage.getItem("username") || "Guest";
  const [showLogoutModal, setShowLogoutModal] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [mailOpen, setMailOpen] = useState(false);
  const [visibleStocks, setVisibleStocks] = useState([]);
  const { language, toggleLanguage: _toggleLanguage } = useContext(LanguageContext);
  const [_langDropdownOpen, _setLangDropdownOpen] = useState(false);
  
  
  const mailRef = useRef(null);
  const dropdownRef = useRef(null);
  const menuRef = useRef(null);
  const langDropdownRef = useRef(null);
  
  const t = {
    en: { 
      sitetitle: "AI-Based Investment", greet: "Welcome", mailbox: "Mailbox", 
      mailalert: "Stock news alert", notification: "Not new notifications", theme: "Select theme", 
      themelight: "Light theme", themedark: "Dark theme", fear: "Fear and Greed", menu: "Menu", risk: "Risk",
      favorite : "Favorite", logout: "Logout", alert:"Do you really want to logout ?", yes:"Yes", no:"No" },
    th: { 
      sitetitle: "ระบบแนะนำการลงทุนด้วย AI", greet: "ยินดีต้อนรับ", mailbox: "กล่องข้อความ",  
      mailalert: "แจ้งเตือนข่าวหุ้น", notification: "ไม่มีข่าวแจ้งเตือน", theme: "เลือกธีม", 
      themelight: "ธีมสว่าง", themedark: "ธีมมืด", fear: "ความกลัวและโลภ", menu: "ตัวเลือก", account: "ความเสี่ยง",
      favorite: "ติดตามหุ้น", logout: "ออกระบบ", alert:"คุณต้องการออกจากระบบใช่หรือไม่ ?", yes:"ใช่", no:"ไม่"},
  };

  useEffect(() => {
    document.body.className = theme;
  }, [theme]);
  
  const handleThemeChange = (newTheme) => {
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    document.body.className = newTheme;
    setDropdownOpen(false);
  };
  
  const handleLogout = () => {
    localStorage.removeItem("isLoggedIn"); // ล้างสถานะ login
    localStorage.removeItem("username");
    navigate("/login"); // ไปหน้า login
  };

  const handleCloseModal = () => {
    setIsClosing(true);
    setTimeout(() => {
      setShowLogoutModal(false);
      setIsClosing(false);
    }, 300);
  };

  const toggleMail = () => {
    setMailOpen((prev) => !prev);
    setDropdownOpen(false);
    setMenuOpen(false);
  };

  const toggleDropdown = () => {
    setDropdownOpen(prev => {
      const newState = !prev;
      if (newState) { setMenuOpen(false); setMailOpen(false); }
      return newState;
    });
  };

  const toggleMenu = () => {
    setMenuOpen(prev => {
      const newState = !prev;
      if (newState) { setDropdownOpen(false); setMailOpen(false); }
      return newState;
    });
  };
  
  // ✅ ปิด Mailbox เมื่อคลิกนอกกล่อง
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (mailRef.current && !mailRef.current.contains(event.target)) setMailOpen(false);
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) setDropdownOpen(false);
      if (langDropdownRef.current && !langDropdownRef.current.contains(event.target)) _setLangDropdownOpen(false);
      if (menuRef.current && !menuRef.current.contains(event.target)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // ฟังก์ชันดึงข่าว
  const fetchNews = async (symbols) => {
    if (!symbols?.length) return [];
    try {
      const query = `?symbols=${[...new Set(symbols)].join(",")}`;
      const res = await fetch(`http://localhost:8000/news${query}`);
      if (!res.ok) throw new Error("Failed to fetch news");
      return await res.json(); // [{symbol, news: [...]}, ...]
    } catch (err) {
      console.error("Error fetching news:", err);
      return [];
    }
  };

   // วิเคราะห์ข่าวกับความเสี่ยง
  const analyzeAlerts = (favorites, riskLevel, newsList) => {
    const alerts = [];
    favorites.forEach(fav => {
      const symbol = typeof fav === "string" ? fav : fav.symbol;
      const newsObj = newsList.find(n => n.symbol === symbol);
      if (!newsObj) return;

      newsObj.news.forEach(item => {
        const sentiment = item.sentiment?.toUpperCase() || "NEUTRAL";
        if (riskLevel === "low" && sentiment === "NEGATIVE") return;

        if (sentiment === "NEGATIVE") alerts.push({ symbol, message: "Negative", risk: "high", link: item.link });
        else if (sentiment === "POSITIVE") alerts.push({ symbol, message: "Positive", risk: "low", link: item.link });
        else alerts.push({ symbol, message: "Na", risk: "medium", link: item.link });
      });
    });
    return alerts;
  };

  // โหลดข่าวหุ้นและสร้าง Alert
  useEffect(() => {
    let isMounted = true;

    const fetchAndUpdateAlerts = async () => {
      const riskLevel = localStorage.getItem("selectedRisk") || "medium";
      const favs = JSON.parse(localStorage.getItem("favorites") || "[]");
      if (!favs.length) {
        if (isMounted) setAlerts([]);
        return;
      }

      const symbols = favs
        .map(f => typeof f === "string" ? f.trim().toUpperCase() : f.symbol?.trim()?.toUpperCase())
        .filter(Boolean);

      const newsList = await fetchNews(symbols);
      const alertList = analyzeAlerts(favs, riskLevel, newsList);
      if (isMounted) setAlerts(alertList);
    };

    fetchAndUpdateAlerts();
    const interval = setInterval(fetchAndUpdateAlerts, 300000);

    const handleStorageChange = (e) => {
      if (e.key === "favorites" || e.key === "selectedRisk") fetchAndUpdateAlerts();
    };

    window.addEventListener("storage", handleStorageChange);

    return () => {
      isMounted = false;
      clearInterval(interval);
      window.removeEventListener("storage", handleStorageChange);
    };
  }, []);

  useEffect(() => {
    // group alerts by symbol
    const symbols = Array.from(new Set(alerts.map(a => a.symbol)));
    // คง stocks ที่ยังอยู่ + เพิ่มใหม่
    setVisibleStocks(prev => {
      // remove stocks ที่ไม่ได้อยู่ใน alerts ใหม่
      const remaining = prev.filter(s => symbols.includes(s));
      const added = symbols.filter(s => !prev.includes(s));
      return [...remaining, ...added];
    });
  }, [alerts]);
  
  
  return (
    <div className={`top-bar ${theme}`}>
      <div className="logo-container">
        <Link to="/search" className="brand-link">
          <img src="/Ail.svg" alt="AI Invest Logo" className="logo" />
          <span className="site-title">AI Invest</span>
        </Link>
      </div>
      
      <div className="header-text">
        <span className="welcome-text">
          Welcome, <span className="username">{username}</span>
        </span>
        <div className="header-icons">
          <div className="tooltip mailbox-wrapper" ref={mailRef}>
            <div className="relative">
              <IoMailOutline
                size={25}
                className="mail-icon"
                onClick={toggleMail}
              />
              {/* จุดแดงแจ้งเตือน */}
              {alerts.length > 0 && (
                <span className="absolute top-0 right-0 inline-block w-3 h-3 bg-red-500 rounded-full border-2 border-white"></span>
              )}
            </div>
            <span className="tooltip-text">{t[language].mailbox}</span>

            {mailOpen && (
              <div className="mail-dropdown">
                <p className="mail-header">📩 แจ้งเตือนข่าวหุ้น</p>
                {visibleStocks.length === 0 ? (
                  <div className="mail-item">- {t[language].notification}</div>
                ) : (
                  visibleStocks.map(symbol => {
                  // กรอง alert ที่ risk = medium ออก
                  const symbolAlerts = alerts
                    .filter(a => a.symbol === symbol && a.risk !== "medium");

                  // ถ้าไม่มี alert ที่เป็น high/low ให้ข้าม
                  if (symbolAlerts.length === 0) return null;

                  return (
                    <div key={symbol} className="stock-news-card">
                      <div className="stock-news-header">{symbol}</div>
                      {symbolAlerts.map((alert, i) => (
                        <div
                          key={i}
                          className={`stock-news-item ${alert.risk}`}
                          style={{
                            color: alert.risk === "high" ? "red" : "green",
                          }}
                        >
                          <a
                            href={alert.link}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="underline"
                          >
                            {alert.message}
                          </a>
                        </div>
                      ))}
                    </div>
                  );
                })
                )}
              </div>
            )}
          </div>

          <div className="tooltip theme-dropdown-wrapper" ref={dropdownRef}>
            <p className="theme-toggle-btn" onClick={toggleDropdown}>
              <BsMoonStars
                size={23}
                color={theme === "dark" ? "white" : "black"}
              />
            </p>
            <span className="tooltip-text">{t[language].theme}</span>

            {dropdownOpen && (
              <div className="dropdown-menu">
                <div
                  className={`dropdown-item ${
                    theme === "light" ? "active" : ""
                  }`}
                  onClick={() => handleThemeChange("light")}
                >
                 {t[language].themelight}
                </div>
                <div
                  className={`dropdown-item ${
                    theme === "dark" ? "active" : ""
                  }`}
                  onClick={() => handleThemeChange("dark")}
                >
                  {t[language].themedark}
                </div>
              </div>
            )}
          </div>

          <div className="tooltip fear-and-greed ">
            <a
              href="https://edition.cnn.com/markets/fear-and-greed"
              target="_blank"
              rel="noopener noreferrer"
            >
              <PiSpeedometer
                size={30}
                color={theme === "dark" ? "white" : "black"} // ✅ ตั้งสีตามธีม
                style={{ cursor: "pointer" }}
              />
              <span className="tooltip-text">{t[language].fear}</span>
            </a>
          </div>

          <div className=" tooltip hamburger-menu" ref={menuRef}>
            <GiHamburgerMenu
              size={25}
              onClick={toggleMenu}
              className="hamburger-icon"
            />
            <span className="tooltip-text">{t[language].menu}</span>

            {menuOpen && (
              <div 
                className="hamburger-dropdown"
                onClick={(e) => e.stopPropagation()}
              >
                <div
                  className="dropdown-item"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate("/recommendation");
                  }}
                >
                  <GiDiceTarget className="dropdown-icon"/>
                  <span className="dropdown-text">Investment</span>
                </div>

                <div
                  className="dropdown-item"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate("/risk");
                  }}
                >
                  <BsFillPersonFill className="dropdown-icon"/>
                  <span className="dropdown-text">{t[language].risk}</span>
                </div>

                <div
                  className="dropdown-item"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate("/favorite");
                  }}
                >
                  <FaStar className="dropdown-icon"/>
                  <span className="dropdown-text">{t[language].favorite}</span>
                </div>
                
                {/* 👇 เมนู AI Picker ที่เพิ่มเข้ามา 👇 */}
                <div
                  className="dropdown-item"
                  onClick={() => {
                    setMenuOpen(false);
                    navigate("/ai-picker");
                  }}
                >
                  <GiDiceTarget className="dropdown-icon"/> 
                  <span className="dropdown-text">AI Picker</span>
                </div>
                {/* 👆 สิ้นสุดส่วน AI Picker 👆 */}

                <div
                  className="dropdown-item"
                  onClick={() => setShowLogoutModal(true)}
                >
                  <BsDoorOpenFill className="dropdown-icon"/>
                  <span className="dropdown-text">{t[language].logout}</span>
                </div>
              </div>
            )}
                      </div>
        </div>
      </div>

      {showLogoutModal && (
        <div className={`logout-modal ${isClosing ? "closing" : ""}`}>
          <div className="logout-box">
            <p>{t[language].alert}</p>
            <div className="logout-actions">
              <button onClick={handleLogout}>{t[language].yes}</button>
              <button onClick={handleCloseModal}>{t[language].no}</button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
