import React from "react";
import { Outlet, Navigate, useLocation } from "react-router-dom";
import Header from "./Header";

export default function PrivateLayout() {
  const location = useLocation();

  console.log('PrivateLayout render สำหรับ path:', location.pathname);
  
  // ข้ามเช็ค token สำหรับ public route ทันที (top-level if)
  const publicPaths = ['/login', '/register', '/forgot-password', '/reset-password'];
  if (publicPaths.includes(location.pathname)) {
    console.log('Public route detected → skipping token check, showing page directly');
    return <Outlet />; // แสดงหน้า public โดยไม่เช็ค token (ไม่ต้อง Header)
  }

  const token = localStorage.getItem("token");

  if (!token) {
    console.log('No token on path:', location.pathname, '→ redirect to /login');
    return <Navigate to="/login" replace />;
  }

  // เช็ค expiry
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp * 1000 < Date.now()) {
      console.log('Token expired on path:', location.pathname, '→ remove and redirect');
      localStorage.removeItem("token");
      return <Navigate to="/login" replace />;
    }
  } catch {
    console.log('Invalid token on path:', location.pathname, '→ remove and redirect');
    localStorage.removeItem("token");
    return <Navigate to="/login" replace />;
  }

  console.log('Token valid on path:', location.pathname, '→ show private page');
  return (
    <>
      <Header />
      <Outlet />
    </>
  );
}
