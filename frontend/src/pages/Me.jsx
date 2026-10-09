import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { Download, LogIn, LogOut } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Avatar, Badge, Empty, KeyValue, humanize, money, useToast } from "../ui";

function PasswordCard() {
  const toast = useToast();
  const [form, setForm] = useState({ old_password: "", new_password: "", confirm: "" });
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    setError("");
    if (form.new_password !== form.confirm) { setError("The new passwords do not match."); return; }
    try {
      await api.post("/auth/change-password/", { old_password: form.old_password, new_password: form.new_password });
      toast("Password changed.");
      setForm({ old_password: "", new_password: "", confirm: "" });
    } catch (err) { setError(errorText(err)); }
  }
  return (
    <form className="card" onSubmit={submit}>
      <h2>Change password</h2>
      <p className="muted" style={{ marginBottom: 16 }}>Use at least 8 characters that are hard to guess.</p>
      <div className="form-grid three">
        <label className="field"><span>Current password</span><input className="input" type="password" autoComplete="current-password" value={form.old_password} onChange={(event) => setForm({ ...form, old_password: event.target.value })} required /></label>
        <label className="field"><span>New password</span><input className="input" type="password" autoComplete="new-password" value={form.new_password} onChange={(event) => setForm({ ...form, new_password: event.target.value })} required /></label>
        <label className="field"><span>Confirm new password</span><input className="input" type="password" autoComplete="new-password" value={form.confirm} onChange={(event) => setForm({ ...form, confirm: event.target.value })} required /></label>
      </div>
      {error && <div className="callout error" style={{ marginTop: 12 }}>{error}</div>}
      <div className="form-actions" style={{ marginTop: 16 }}><button className="btn btn-primary">Update password</button></div>
    </form>
  );
}

export default function MePage() {
  const { user } = useAuth();
  const toast = useToast();
  const [profile, setProfile] = useState(null);
  const [balances, setBalances] = useState([]);
  const [attendance, setAttendance] = useState([]);
  const [slips, setSlips] = useState([]);
  const [today, setToday] = useState(null);
  const [types, setTypes] = useState([]);
  const blankLeave = { leave_type: "", start_date: "", end_date: "", day_part: "full", reason: "" };
  const [leave, setLeave] = useState(blankLeave);
  const fullName = `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.username;
  const todayIso = dayjs().format("YYYY-MM-DD");

  function loadToday() {
    api.get(`/attendance/daily/?date=${todayIso}`).then(({ data }) => setToday((data.results || []).find((row) => row.employee_id === user.employee_id) || null)).catch(() => {});
  }
  function loadBalances() { api.get(`/leave-balances/?employee=${user.employee_id}`).then(({ data }) => setBalances(rowsOf(data))); }
  useEffect(() => {
    if (!user.employee_id) return;
    api.get(`/employees/${user.employee_id}/`).then(({ data }) => setProfile(data));
    loadBalances();
    api.get(`/attendance/records/?employee=${user.employee_id}`).then(({ data }) => setAttendance(data.results || []));
    api.get(`/payroll/records/?employee=${user.employee_id}`).then(({ data }) => setSlips(rowsOf(data))).catch(() => {});
    api.get("/leave-types/").then(({ data }) => setTypes(rowsOf(data)));
    loadToday();
  }, [user]);

  async function punch(path, label) {
    try { await api.post(path, {}); toast(label); loadToday(); } catch (err) { toast(errorText(err), "bad"); }
  }

  if (!user.employee_id) {
    return (
      <div className="page">
        <div className="page-head"><div><p className="eyebrow">Account</p><h1>My account</h1></div></div>
        <article className="card">
          <div className="profile-head" style={{ marginBottom: 20 }}>
            <Avatar name={fullName} size={52} />
            <div><h2 style={{ fontSize: 18 }}>{fullName}</h2><p className="muted">{humanize(user.role)}</p></div>
          </div>
          <KeyValue items={[["Username", user.username], ["Email", user.email], ["Role", humanize(user.role)], ["Employee profile", "Not linked. This is an administrative login."]]} />
        </article>
        <PasswordCard />
      </div>
    );
  }

  const checkedIn = today?.check_in_time;
  const checkedOut = today?.check_out_time;
  return (
    <div className="page">
      <div className="page-head">
        <div className="profile-head">
          <Avatar name={profile?.full_name || fullName} src={profile?.photo_url} size={56} />
          <div><p className="eyebrow" style={{ marginBottom: 2 }}>{profile?.employee_code}</p><h1>{profile?.full_name || fullName}</h1><p className="muted">{profile?.job_title_name || "No title"} · {profile?.department_name || "No department"}</p></div>
        </div>
      </div>

      <article className="card">
        <div className="toolbar">
          <div>
            <h2>Today, {dayjs().format("dddd D MMMM")}</h2>
            <p className="muted" style={{ marginTop: 4 }}>
              {today ? <><Badge value={today.status} /> <span style={{ marginLeft: 6 }}>{checkedIn ? `In at ${checkedIn}` : "Not checked in"}{checkedOut ? ` · Out at ${checkedOut}` : ""}{today.late_minutes ? ` · ${today.late_minutes} minutes late` : ""}</span></> : "No attendance information for today."}
            </p>
          </div>
          {user.capabilities.can_check_in && <div className="filters">
            <button className="btn btn-primary" disabled={!!checkedIn} onClick={() => punch("/attendance/check-in/", "Checked in.")}><LogIn size={16} /> Check in</button>
            <button className="btn btn-ghost" disabled={!checkedIn || !!checkedOut} onClick={() => punch("/attendance/check-out/", "Checked out.")}><LogOut size={16} /> Check out</button>
          </div>}
        </div>
      </article>

      <div className="grid-2 even">
        <article className="card">
          <h2>Leave balance, {dayjs().year()}</h2>
          <div className="list">
            {balances.map((item) => <div key={item.id} className="list-row"><div><strong>{item.leave_type_name}</strong><span className="subtle">{Number(item.used)} used · {Number(item.pending)} pending</span></div><strong style={{ fontSize: 18 }}>{Number(item.available)}<span className="subtle" style={{ display: "inline", marginLeft: 4 }}>days</span></strong></div>)}
          </div>
          {balances.length === 0 && <Empty title="No leave balances" />}
        </article>
        <form className="card" onSubmit={async (event) => {
          event.preventDefault();
          try { await api.post("/leave-requests/", { ...leave, employee: user.employee_id, end_date: leave.day_part === "full" ? leave.end_date : leave.start_date }); toast("Leave request sent for approval."); setLeave(blankLeave); loadBalances(); } catch (err) { toast(errorText(err), "bad"); }
        }}>
          <h2>Request leave</h2>
          <div className="form-grid">
            <label className="field"><span>Leave type</span><select className="select" value={leave.leave_type} onChange={(event) => setLeave({ ...leave, leave_type: event.target.value })} required><option value="">Choose…</option>{types.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <label className="field"><span>Duration</span><select className="select" value={leave.day_part} onChange={(event) => setLeave({ ...leave, day_part: event.target.value })}><option value="full">Full days</option><option value="first_half">Half day, morning</option><option value="second_half">Half day, afternoon</option></select></label>
            <label className="field"><span>{leave.day_part === "full" ? "From" : "Date"}</span><input className="input" type="date" value={leave.start_date} onChange={(event) => setLeave({ ...leave, start_date: event.target.value, end_date: leave.end_date && leave.end_date >= event.target.value ? leave.end_date : event.target.value })} required /></label>
            {leave.day_part === "full" && <label className="field"><span>To</span><input className="input" type="date" min={leave.start_date} value={leave.end_date} onChange={(event) => setLeave({ ...leave, end_date: event.target.value })} required /></label>}
            <label className="field span-2"><span>Reason</span><textarea className="textarea" value={leave.reason} onChange={(event) => setLeave({ ...leave, reason: event.target.value })} required /></label>
          </div>
          <div className="form-actions" style={{ marginTop: 16 }}><button className="btn btn-primary">Send request</button></div>
        </form>
      </div>

      <div className="grid-2 even">
        <article className="card flush">
          <div className="card-head"><h2>Salary slips</h2></div>
          {slips.length === 0 ? <Empty title="No salary slips yet" /> : <div className="table-wrap"><table><thead><tr><th>Month</th><th className="num">Net pay</th><th>Status</th><th /></tr></thead><tbody>{slips.map((item) => <tr key={item.id}><td><strong>{dayjs(`${item.period_label}-01`).format("MMMM YYYY")}</strong></td><td className="num">{money(item.net_salary)}</td><td><Badge value={item.payment_status} /></td><td className="num"><button className="btn btn-ghost btn-sm" onClick={() => download(`/payroll/records/${item.id}/slip/?format=pdf`, `salary-slip-${item.period_label}.pdf`)}><Download size={14} /> PDF</button></td></tr>)}</tbody></table></div>}
        </article>
        <article className="card flush">
          <div className="card-head"><h2>Recent attendance</h2></div>
          {attendance.length === 0 ? <Empty title="No attendance yet" /> : <div className="table-wrap"><table><thead><tr><th>Date</th><th>Status</th><th>In</th><th>Out</th></tr></thead><tbody>{attendance.filter((item) => item.date <= todayIso).slice(0, 10).map((item) => <tr key={item.id}><td>{dayjs(item.date).format("ddd, D MMM")}</td><td><Badge value={item.status} /></td><td>{item.check_in_time || "—"}</td><td>{item.check_out_time || "—"}</td></tr>)}</tbody></table></div>}
        </article>
      </div>

      <PasswordCard />
    </div>
  );
}
