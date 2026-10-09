import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarCheck2, Eye, EyeOff, ShieldCheck, Wallet } from "lucide-react";
import api, { errorText } from "../api";
import { useAuth } from "../auth";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [company, setCompany] = useState("Wesolucions");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/auth/company/").then(({ data }) => data.company_name && setCompany(data.company_name)).catch(() => {}); }, []);

  async function submit(event) {
    event.preventDefault();
    const next = {};
    if (!username.trim()) next.username = "Enter your username.";
    if (!password) next.password = "Enter your password.";
    setErrors(next);
    setFormError("");
    if (Object.keys(next).length) return;
    setBusy(true);
    try {
      await login(username.trim(), password);
      navigate("/dashboard");
    } catch (err) {
      setFormError(err?.response?.status === 401 ? "That username and password do not match an active account." : errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <aside className="auth-aside">
        <div className="brand" style={{ padding: 0 }}>
          <div className="brand-mark">{company.charAt(0)}</div>
          <div><strong>{company}</strong><small style={{ color: "#a5b4fc" }}>Human Resources</small></div>
        </div>
        <div>
          <h2>Attendance, leave, and payroll in one place.</h2>
          <p>Track who is in, who is late, who is on leave, and what everyone is owed, from records your team can audit.</p>
          <div className="auth-points">
            <div><CalendarCheck2 size={18} /><span>Lateness follows each shift and its grace period. Approved leave, weekly offs, and holidays are never counted as absences.</span></div>
            <div><Wallet size={18} /><span>Payroll is calculated on the server with a line-by-line breakdown, and it locks when finalized.</span></div>
            <div><ShieldCheck size={18} /><span>Every role sees only what it should. Salaries stay private.</span></div>
          </div>
        </div>
        <p className="subtle" style={{ color: "#7f8fd1" }}>© {new Date().getFullYear()} {company}</p>
      </aside>
      <main className="auth-main">
        <form className="auth-card" onSubmit={submit} noValidate>
          <div>
            <p className="eyebrow">{company}</p>
            <h1>Sign in</h1>
            <p className="muted" style={{ marginTop: 6 }}>Use the account your administrator created for you.</p>
          </div>
          <label className="field">
            <span>Username</span>
            <input className="input" value={username} autoFocus autoComplete="username" aria-invalid={!!errors.username} onChange={(event) => { setUsername(event.target.value); setErrors((current) => ({ ...current, username: undefined })); }} />
            {errors.username && <em>{errors.username}</em>}
          </label>
          <label className="field">
            <span>Password</span>
            <div className="input-wrap">
              <input className="input" type={show ? "text" : "password"} value={password} autoComplete="current-password" aria-invalid={!!errors.password} onChange={(event) => { setPassword(event.target.value); setErrors((current) => ({ ...current, password: undefined })); }} />
              <button type="button" onClick={() => setShow((value) => !value)} aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff size={16} /> : <Eye size={16} />}</button>
            </div>
            {errors.password && <em>{errors.password}</em>}
          </label>
          {formError && <div className="callout error" role="alert">{formError}</div>}
          <button className="btn btn-primary" style={{ minHeight: 42 }} disabled={busy} type="submit">{busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </main>
    </div>
  );
}
