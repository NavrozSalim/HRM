import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AlarmClock, Bell, Clock, FileBarChart, LayoutDashboard, LogOut, Menu, Moon, Palmtree, Search, Settings, Sun, UserRound, Users, Wallet } from "lucide-react";
import { useAuth } from "./auth";
import api from "./api";
import { Avatar, Spinner, humanize } from "./ui";
import LoginPage from "./pages/Login";
import DashboardPage from "./pages/Dashboard";
import EmployeesPage from "./pages/Employees";
import EmployeeProfilePage from "./pages/EmployeeProfile";
import EmployeeFormPage from "./pages/EmployeeForm";
import AttendancePage from "./pages/Attendance";
import PunctualityPage from "./pages/Punctuality";
import LeavesPage from "./pages/Leaves";
import PayrollPage from "./pages/Payroll";
import ReportsPage from "./pages/Reports";
import SettingsPage from "./pages/Settings";
import MePage from "./pages/Me";
import NotificationsPage from "./pages/Notifications";
import SearchPage from "./pages/Search";

function Shell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [unread, setUnread] = useState(0);
  const [company, setCompany] = useState("Wesolucions");
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));
  const caps = user.capabilities || {};
  const staff = user.role !== "employee";
  useEffect(() => { api.get("/auth/company/").then(({ data }) => data.company_name && setCompany(data.company_name)).catch(() => {}); }, []);
  useEffect(() => {
    const refresh = () => api.get("/notifications/").then(({ data }) => setUnread(data.unread)).catch(() => {});
    refresh();
    setOpen(false);
    window.addEventListener("hrm:notifications", refresh);
    return () => window.removeEventListener("hrm:notifications", refresh);
  }, [location.pathname]);

  const groups = [
    { label: "Overview", links: [["/dashboard", "Dashboard", LayoutDashboard, true]] },
    { label: "People", links: [
      ["/employees", "Employees", Users, staff],
      ["/attendance", "Attendance", Clock, staff],
      ["/punctuality", "Punctuality", AlarmClock, staff],
      ["/leaves", "Leave", Palmtree, true],
    ] },
    { label: "Finance", links: [
      ["/payroll", "Payroll", Wallet, caps.view_payroll],
      ["/reports", "Reports", FileBarChart, staff],
    ] },
    { label: "Account", links: [
      ["/me", user.employee_id ? "My workspace" : "My account", UserRound, true],
      ["/settings", "Organization", Settings, staff],
    ] },
  ];

  function toggleTheme() {
    document.documentElement.classList.toggle("dark");
    const next = document.documentElement.classList.contains("dark");
    localStorage.setItem("hrm_theme", next ? "dark" : "light");
    setDark(next);
  }

  const fullName = `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username;
  return (
    <div className="shell">
      <div className={`scrim ${open ? "open" : ""}`} onClick={() => setOpen(false)} />
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">{company.charAt(0)}</div>
          <div style={{ minWidth: 0 }}><strong>{company}</strong><small>HR Management</small></div>
        </div>
        {groups.map((group) => {
          const visible = group.links.filter((item) => item[3]);
          if (!visible.length) return null;
          return (
            <nav key={group.label} className="nav" aria-label={group.label}>
              <div className="nav-label">{group.label}</div>
              {visible.map(([to, label, Icon]) => (
                <NavLink key={to} to={to} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
                  <Icon size={17} /> {label}
                </NavLink>
              ))}
            </nav>
          );
        })}
        <div className="sidebar-user">
          <Avatar name={fullName} size={32} />
          <div><strong>{fullName}</strong><small>{humanize(user.role)}</small></div>
          <button className="icon-btn" title="Sign out" aria-label="Sign out" onClick={() => logout().then(() => navigate("/login"))}><LogOut size={16} /></button>
        </div>
      </aside>
      <section className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" onClick={() => setOpen((value) => !value)} type="button" aria-label="Open menu"><Menu size={18} /></button>
          <form className="search" onSubmit={(event) => { event.preventDefault(); if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`); }}>
            <Search size={16} />
            <input className="input" placeholder="Search people by name, ID, or email" value={query} onChange={(event) => setQuery(event.target.value)} />
          </form>
          <div className="topbar-spacer" />
          <button className="icon-btn" type="button" onClick={toggleTheme} title={dark ? "Light mode" : "Dark mode"} aria-label="Toggle dark mode">{dark ? <Sun size={17} /> : <Moon size={17} />}</button>
          <button className="icon-btn notif-btn" type="button" onClick={() => navigate("/notifications")} title="Notifications" aria-label={`Notifications, ${unread} unread`}>
            <Bell size={17} />
            {unread > 0 && <span className="notif-dot">{unread > 99 ? "99+" : unread}</span>}
          </button>
        </header>
        <Routes>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/employees/new" element={<EmployeeFormPage />} />
          <Route path="/employees/:id/edit" element={<EmployeeFormPage />} />
          <Route path="/employees/:id" element={<EmployeeProfilePage />} />
          <Route path="/attendance" element={<AttendancePage />} />
          <Route path="/punctuality" element={<PunctualityPage />} />
          <Route path="/leaves" element={<LeavesPage />} />
          <Route path="/payroll" element={<PayrollPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/me" element={<MePage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </section>
    </div>
  );
}

export default function App() {
  const { user, ready } = useAuth();
  if (!ready) return <div style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}><Spinner label="Loading…" /></div>;
  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
      <Route path="/*" element={user ? <Shell /> : <Navigate to="/login" replace />} />
    </Routes>
  );
}
