import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { Trash2 } from "lucide-react";
import api, { errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Badge, ConfirmDialog, Empty, Spinner, Switch, Tabs, humanize, useToast } from "../ui";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function Crud({ title, description, path, fields, columns, canWrite }) {
  const toast = useToast();
  const [rows, setRows] = useState(null);
  const [form, setForm] = useState({});
  const [removing, setRemoving] = useState(null);
  const load = () => api.get(`${path}?page_size=100`).then(({ data }) => setRows(rowsOf(data))).catch((err) => { setRows([]); toast(errorText(err), "bad"); });
  useEffect(() => { load(); }, [path]);
  async function save(event) {
    event.preventDefault();
    const payload = Object.fromEntries(Object.entries(form).filter(([, value]) => value !== ""));
    try { await api.post(path, payload); toast(`${title.replace(/s$/, "")} added.`); setForm({}); load(); } catch (err) { toast(errorText(err), "bad"); }
  }
  async function remove() {
    try { await api.delete(`${path}${removing.id}/`); toast("Removed."); load(); } catch (err) { toast(errorText(err), "bad"); }
    setRemoving(null);
  }
  return (
    <article className="card flush">
      <div className="card-head"><div><h2>{title}</h2>{description && <p className="muted">{description}</p>}</div></div>
      {canWrite && <form className="filters" style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)" }} onSubmit={save}>
        {fields.map((field) => field.type === "select"
          ? <select key={field.name} className="select" aria-label={field.label} value={form[field.name] || ""} onChange={(event) => setForm({ ...form, [field.name]: event.target.value })}><option value="">{field.label}</option>{field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
          : <input key={field.name} className="input" aria-label={field.label} placeholder={field.label} type={field.type || "text"} required={field.required} value={form[field.name] || ""} onChange={(event) => setForm({ ...form, [field.name]: event.target.value })} />)}
        <button className="btn btn-primary">Add</button>
      </form>}
      {rows === null ? <Spinner /> : rows.length === 0 ? <Empty title={`No ${title.toLowerCase()} yet`} /> : (
        <div className="table-wrap">
          <table>
            <thead><tr>{columns.map(([label]) => <th key={label}>{label}</th>)}{canWrite && <th />}</tr></thead>
            <tbody>{rows.map((row) => <tr key={row.id}>{columns.map(([label, render]) => <td key={label}>{render(row)}</td>)}{canWrite && <td className="num"><button className="icon-btn" title="Remove" aria-label={`Remove ${row.name}`} onClick={() => setRemoving(row)}><Trash2 size={15} /></button></td>}</tr>)}</tbody>
          </table>
        </div>
      )}
      {removing && <ConfirmDialog title={`Remove ${removing.name}?`} body="Items already used by employees, attendance, or payroll cannot be removed. Mark them inactive instead." confirmLabel="Remove" danger onConfirm={remove} onClose={() => setRemoving(null)} />}
    </article>
  );
}

function Section({ title, description, children }) {
  return (
    <div className="form-section">
      <div><h2>{title}</h2>{description && <p className="muted">{description}</p>}</div>
      <div>{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("policy");
  const [policy, setPolicy] = useState(null);
  const [saved, setSaved] = useState(null);
  const [departments, setDepartments] = useState([]);
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [busy, setBusy] = useState(false);
  const blankAccount = { username: "", first_name: "", last_name: "", email: "", role: "management", password: "" };
  const [account, setAccount] = useState(blankAccount);
  const canEditPolicy = user.capabilities.manage_settings;
  const canWriteOrg = user.capabilities.manage_org;
  useEffect(() => {
    api.get("/office-settings/").then(({ data }) => { setPolicy(data); setSaved(data); }).catch(() => setPolicy(false));
    api.get("/departments/?page_size=100").then(({ data }) => setDepartments(rowsOf(data))).catch(() => {});
  }, []);
  useEffect(() => { if (tab === "users" && user.capabilities.manage_users) api.get("/auth/users/").then(({ data }) => setUsers(rowsOf(data))); }, [tab]);
  useEffect(() => { if (tab === "audit" && user.capabilities.view_audit) api.get("/audit-logs/").then(({ data }) => setAudit(data.results || [])).catch((err) => toast(errorText(err), "bad")); }, [tab]);
  const set = (key) => (value) => setPolicy((current) => ({ ...current, [key]: value }));
  const dirty = policy && saved && JSON.stringify(policy) !== JSON.stringify(saved);

  async function savePolicy(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.patch("/office-settings/", policy);
      setPolicy(data);
      setSaved(data);
      toast("Policy saved. Recalculate any open payroll month so it uses the new rules.");
    } catch (err) { toast(errorText(err), "bad"); }
    setBusy(false);
  }

  const tabs = [
    { value: "policy", label: "Policies" },
    { value: "departments", label: "Departments" },
    { value: "titles", label: "Job titles" },
    { value: "locations", label: "Locations" },
    { value: "shifts", label: "Shifts" },
    { value: "holidays", label: "Holidays" },
    { value: "leave", label: "Leave types" },
    user.capabilities.manage_users && { value: "users", label: "Users" },
    user.capabilities.view_audit && { value: "audit", label: "Audit log" },
  ].filter(Boolean);

  const number = (key, label, hint, step = "1") => (
    <label className="field"><span>{label}</span><input className="input" type="number" min="0" step={step} disabled={!canEditPolicy} value={policy[key] ?? ""} onChange={(event) => set(key)(event.target.value)} />{hint && <small>{hint}</small>}</label>
  );
  const toggle = (key, label, description) => <Switch checked={policy[key]} disabled={!canEditPolicy} onChange={set(key)} label={label} description={description} />;

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Setup</p><h1>Organization</h1><p className="muted">Company rules, structure, and access. Changes are recorded in the audit log.</p></div>
      </div>
      <Tabs items={tabs} value={tab} onChange={setTab} />

      {tab === "policy" && (policy === null ? <Spinner /> : policy === false ? <div className="callout warn">Your role cannot view office policies.</div> : (
        <form className="card" onSubmit={savePolicy}>
          {!canEditPolicy && <div className="callout" style={{ marginBottom: 16 }}>You can view these rules. Only a super user can change them.</div>}
          <Section title="Company" description="Shown on the sign-in page, reports, and salary slips.">
            <div className="form-grid">
              <label className="field"><span>Company name</span><input className="input" disabled={!canEditPolicy} value={policy.company_name} onChange={(event) => set("company_name")(event.target.value)} /></label>
              <label className="field"><span>Legal name</span><input className="input" disabled={!canEditPolicy} value={policy.legal_name || ""} onChange={(event) => set("legal_name")(event.target.value)} /></label>
              <label className="field"><span>Time zone</span><input className="input" disabled={!canEditPolicy} value={policy.timezone} onChange={(event) => set("timezone")(event.target.value)} /><small>For example Asia/Karachi</small></label>
              <label className="field"><span>Currency</span><input className="input" disabled={!canEditPolicy} value={policy.currency} maxLength={3} onChange={(event) => set("currency")(event.target.value.toUpperCase())} /><small>Three-letter code, such as USD or PKR</small></label>
            </div>
          </Section>
          <Section title="Working week" description="Employees inherit these days off unless their shift or profile sets its own.">
            <span className="field" style={{ marginBottom: 8 }}><span>Weekly days off</span></span>
            <div className="tabs" role="group" aria-label="Weekly days off">
              {WEEKDAYS.map((label, index) => {
                const on = (policy.default_weekly_off_days || []).includes(index);
                return <button key={label} type="button" disabled={!canEditPolicy} className={`tab ${on ? "active" : ""}`} aria-pressed={on} onClick={() => set("default_weekly_off_days")(on ? policy.default_weekly_off_days.filter((day) => day !== index) : [...(policy.default_weekly_off_days || []), index].sort())}>{label}</button>;
              })}
            </div>
            <div className="form-grid" style={{ marginTop: 16 }}>
              {number("standard_work_minutes", "Standard working minutes per day", "480 is eight hours")}
              {number("half_day_threshold_minutes", "Half-day threshold (minutes)", "Less work than this counts as a half day")}
            </div>
          </Section>
          <Section title="Punctuality" description="Lateness is measured from the shift start once the grace period has passed.">
            <div className="form-grid">
              {number("default_grace_minutes", "Late grace period (minutes)")}
              {number("early_departure_grace_minutes", "Early departure grace (minutes)")}
              {number("monthly_late_warning_threshold", "Late arrivals before a warning", "Per employee, per month")}
            </div>
          </Section>
          <Section title="Salary calculation" description="A full month of monthly salary is always paid in full. The divisor sets the day rate for unpaid days and mid-month joiners.">
            <div className="form-grid">
              <label className="field"><span>Day-rate divisor</span><select className="select" disabled={!canEditPolicy} value={policy.salary_divisor_mode} onChange={(event) => set("salary_divisor_mode")(event.target.value)}><option value="scheduled_working_days">Scheduled working days in the month</option><option value="calendar_days">Calendar days in the month</option><option value="fixed">Fixed number of days</option></select></label>
              {policy.salary_divisor_mode === "fixed" ? number("fixed_salary_divisor", "Fixed divisor (days)", "Often 26 or 30", "0.01") : <div />}
              {number("overtime_multiplier", "Overtime rate multiplier", "1.5 means time and a half", "0.01")}
            </div>
            <div style={{ marginTop: 8 }}>
              {toggle("holiday_work_counts_as_overtime", "Pay holiday and weekly-off work as overtime", "Every hour worked on a day off is paid at the overtime rate.")}
              {toggle("daily_wage_pays_weekly_off", "Pay daily-wage staff for weekly offs")}
              {toggle("daily_wage_pays_holiday", "Pay daily-wage staff for public holidays")}
              {toggle("daily_wage_pays_paid_leave", "Pay daily-wage staff for approved paid leave")}
            </div>
          </Section>
          <Section title="Deductions" description="Deductions apply only when switched on here. Weekly offs and public holidays are never deducted.">
            {toggle("unpaid_leave_deduction_enabled", "Deduct approved unpaid leave", "Monthly salaries lose one day rate for each unpaid leave day.")}
            {toggle("absence_deduction_enabled", "Deduct unexplained absences", "Days with no attendance and no approved leave. A day is never deducted twice.")}
            {toggle("late_penalty_enabled", "Apply a late-arrival penalty", "Leave this off unless your office has a written lateness policy.")}
            {policy.late_penalty_enabled && <div className="form-grid" style={{ marginTop: 12 }}>
              <label className="field"><span>Penalty method</span><select className="select" disabled={!canEditPolicy} value={policy.late_penalty_mode} onChange={(event) => set("late_penalty_mode")(event.target.value)}><option value="per_occurrence">Fixed amount per late arrival</option><option value="per_minute">Amount per late minute</option></select></label>
              {number("late_penalty_amount", `Penalty amount (${policy.currency})`, undefined, "0.01")}
            </div>}
          </Section>
          <Section title="Attendance capture" description="How attendance gets into the system.">
            {toggle("self_checkin_enabled", "Let employees check in and out themselves", "Adds Check in and Check out buttons to each employee's workspace.")}
            {toggle("biometric_enabled", "Accept biometric device punches", "No device is connected. Punches are refused until an adapter is installed.")}
          </Section>
          {canEditPolicy && <div className="form-actions">
            <button type="button" className="btn btn-ghost" disabled={!dirty || busy} onClick={() => setPolicy(saved)}>Discard changes</button>
            <button className="btn btn-primary" disabled={!dirty || busy}>{busy ? "Saving…" : "Save policies"}</button>
          </div>}
        </form>
      ))}

      {tab === "departments" && <Crud title="Departments" canWrite={canWriteOrg} path="/departments/" fields={[{ name: "name", label: "Department name", required: true }, { name: "code", label: "Code, e.g. ENG", required: true }]} columns={[["Name", (row) => <strong>{row.name}</strong>], ["Code", (row) => row.code], ["Manager", (row) => row.manager_name || "—"], ["Status", (row) => <Badge value={row.is_active ? "active" : "inactive"} />]]} />}
      {tab === "titles" && <Crud title="Job titles" canWrite={canWriteOrg} path="/job-titles/" fields={[{ name: "name", label: "Job title", required: true }, { name: "department", label: "Any department", type: "select", options: departments.map((item) => ({ value: item.id, label: item.name })) }]} columns={[["Title", (row) => <strong>{row.name}</strong>], ["Department", (row) => row.department_name || "Any"]]} />}
      {tab === "locations" && <Crud title="Locations" canWrite={canWriteOrg} path="/locations/" fields={[{ name: "name", label: "Location name", required: true }, { name: "address", label: "Address" }, { name: "timezone", label: "Time zone (optional)" }]} columns={[["Name", (row) => <strong>{row.name}</strong>], ["Address", (row) => row.address || "—"], ["Time zone", (row) => row.timezone || "Office default"]]} />}
      {tab === "shifts" && <Crud title="Shifts" canWrite={canWriteOrg} description="A shift that ends before it starts is treated as overnight." path="/shifts/" fields={[{ name: "name", label: "Shift name", required: true }, { name: "start_time", label: "Start", type: "time", required: true }, { name: "end_time", label: "End", type: "time", required: true }, { name: "break_minutes", label: "Break minutes", type: "number" }, { name: "grace_minutes", label: "Grace minutes", type: "number" }]} columns={[["Shift", (row) => <strong>{row.name}</strong>], ["Hours", (row) => `${row.start_time?.slice(0, 5)} – ${row.end_time?.slice(0, 5)}${row.is_overnight ? " (overnight)" : ""}`], ["Break", (row) => `${row.break_minutes} min`], ["Grace", (row) => `${row.grace_minutes} min`]]} />}
      {tab === "holidays" && <Crud title="Public holidays" canWrite={canWriteOrg} description="Holidays are not deducted and are never counted as absences." path="/holidays/" fields={[{ name: "name", label: "Holiday name", required: true }, { name: "date", label: "Date", type: "date", required: true }]} columns={[["Holiday", (row) => <strong>{row.name}</strong>], ["Date", (row) => dayjs(row.date).format("ddd, D MMM YYYY")], ["Applies to", (row) => row.location_name || "All locations"]]} />}
      {tab === "leave" && <Crud title="Leave types" canWrite={canWriteOrg} path="/leave-types/" fields={[{ name: "name", label: "Leave type name", required: true }, { name: "code", label: "Code, e.g. CL", required: true }, { name: "annual_entitlement", label: "Days per year", type: "number" }]} columns={[["Type", (row) => <strong>{row.name}</strong>], ["Pay", (row) => <Badge value={row.is_paid ? "paid" : "unpaid"} />], ["Days per year", (row) => (row.tracks_balance ? Number(row.annual_entitlement) : "Not tracked")]]} />}

      {tab === "users" && <div className="grid-2">
        <article className="card flush">
          <div className="card-head"><h2>User accounts</h2></div>
          <div className="table-wrap"><table><thead><tr><th>Username</th><th>Name</th><th>Role</th><th>Status</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td><strong>{item.username}</strong></td><td>{`${item.first_name} ${item.last_name}`.trim() || "—"}</td><td>{humanize(item.role)}</td><td><Badge value={item.is_active ? "active" : "inactive"} /></td></tr>)}</tbody></table></div>
        </article>
        <form className="card" onSubmit={async (event) => { event.preventDefault(); try { await api.post("/auth/users/", account); toast("Account created."); setAccount(blankAccount); const { data } = await api.get("/auth/users/"); setUsers(rowsOf(data)); } catch (err) { toast(errorText(err), "bad"); } }}>
          <h2>New account</h2>
          <p className="muted" style={{ marginBottom: 16 }}>Create a management login here. Management can add employees and handle attendance, leave, and payroll. For an employee, use Add employee and turn on Create login so the account is linked to their profile.</p>
          <div className="form-grid">
            <label className="field"><span>First name</span><input className="input" value={account.first_name} onChange={(event) => setAccount({ ...account, first_name: event.target.value })} required /></label>
            <label className="field"><span>Last name</span><input className="input" value={account.last_name} onChange={(event) => setAccount({ ...account, last_name: event.target.value })} /></label>
            <label className="field"><span>Username</span><input className="input" value={account.username} onChange={(event) => setAccount({ ...account, username: event.target.value })} required /></label>
            <label className="field"><span>Email</span><input className="input" type="email" value={account.email} onChange={(event) => setAccount({ ...account, email: event.target.value })} /></label>
            <label className="field"><span>Role</span><select className="select" value={account.role} onChange={(event) => setAccount({ ...account, role: event.target.value })}><option value="management">Management</option><option value="employee">Employee</option></select></label>
            <label className="field"><span>Temporary password</span><input className="input" type="password" autoComplete="new-password" value={account.password} onChange={(event) => setAccount({ ...account, password: event.target.value })} required /><small>At least 8 characters, not too common</small></label>
          </div>
          <div className="form-actions" style={{ marginTop: 16 }}><button className="btn btn-primary">Create account</button></div>
        </form>
      </div>}

      {tab === "audit" && <article className="card flush">
        <div className="card-head"><div><h2>Audit log</h2><p className="muted">The latest 200 changes. Passwords, tokens, and full account numbers are never recorded.</p></div></div>
        {audit.length === 0 ? <Empty title="No audit entries yet" /> : <div className="table-wrap"><table><thead><tr><th>When</th><th>Who</th><th>What changed</th><th>Reason</th></tr></thead><tbody>{audit.map((item) => <tr key={item.id}><td style={{ whiteSpace: "nowrap" }}>{dayjs(item.created_at).format("D MMM YYYY, HH:mm")}</td><td>{item.actor}</td><td>{item.summary}</td><td className="muted">{item.reason || "—"}</td></tr>)}</tbody></table></div>}
      </article>}
    </div>
  );
}
