/* eslint-disable react-refresh/only-export-components */
import { createContext, useMemo, useState } from "react";

export const AuthContext = createContext();

function safeParseJwt(token) {
  try {
    const parts = token.split(".");
    if (parts.length < 2) return null;
    const payload = JSON.parse(atob(parts[1]));
    if (payload?.exp && payload.exp * 1000 < Date.now()) return null;
    return payload;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [guestMode, setGuestMode] = useState(false);
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");

  const user = useMemo(() => {
    if (guestMode) {
      return { id: "guest", email: "guest@local", username: "Guest", isGuest: true };
    }

    if (!token) return null;

    const payload = safeParseJwt(token);
    if (!payload) {
      localStorage.removeItem("token");
      return null;
    }

    const usernameFromStorage = localStorage.getItem("username");
    const email = payload.email || "user@local";

    return {
      id: payload.id,
      email,
      username: usernameFromStorage || email.split("@")[0],
      isGuest: false,
    };
  }, [token, guestMode]);

  const loginAsGuest = () => {
    setGuestMode(true);
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    setToken("");
  };

  const loginWithToken = (nextToken, username) => {
    setGuestMode(false);
    localStorage.setItem("token", nextToken);
    if (username) localStorage.setItem("username", username);
    setToken(nextToken);
  };

  const logout = () => {
    setGuestMode(false);
    setToken("");
    localStorage.removeItem("token");
    localStorage.removeItem("username");
  };

  return (
    <AuthContext.Provider value={{ user, token, loginAsGuest, loginWithToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
