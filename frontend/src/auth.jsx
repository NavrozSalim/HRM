import { createContext, useContext, useEffect, useMemo, useState } from "react";
import api from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("hrm_access");
    if (!token) {
      setReady(true);
      return;
    }
    api.get("/auth/me/").then(({ data }) => setUser(data)).catch(() => {
      localStorage.removeItem("hrm_access");
      localStorage.removeItem("hrm_refresh");
    }).finally(() => setReady(true));
  }, []);

  const value = useMemo(() => ({
    user,
    ready,
    async login(username, password) {
      const { data } = await api.post("/auth/login/", { username, password });
      localStorage.setItem("hrm_access", data.access);
      localStorage.setItem("hrm_refresh", data.refresh);
      setUser(data.user);
      return data.user;
    },
    async logout() {
      const refresh = localStorage.getItem("hrm_refresh");
      try { await api.post("/auth/logout/", { refresh }); } catch { /* token may already be expired */ }
      localStorage.removeItem("hrm_access");
      localStorage.removeItem("hrm_refresh");
      setUser(null);
    },
    refreshUser: async () => {
      const { data } = await api.get("/auth/me/");
      setUser(data);
    },
  }), [user, ready]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
