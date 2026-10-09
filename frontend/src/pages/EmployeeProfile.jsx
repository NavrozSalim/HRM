import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import dayjs from "dayjs";
import api, { errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Avatar, Badge, Empty, KeyValue, Modal, Spinner, Tabs, humanize, maskAccount, money, useToast } from "../ui";

export default function EmployeeProfilePage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [employee, setEmployee] = useState(null);
  const [tab, setTab] = useState("overview");
  const [attendance, setAttendance] = useState([]);
  const [leaves, setLeaves] = useState([]);
  const [payroll, setPayroll] = useState([]);
  const [timeline, setTimeline] = useState([]);
  const [allowances, setAllowances] = useState([]);
  const [allowance, setAllowance] = useState({ name: "Transport", amount: "" });
  const [missing, setMissing] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [reason, setReason] = useState("");
  const [exitDate, setExitDate] = useState(dayjs().format("YYYY-MM-DD"));
  useEffect(() => {
    setMissing(false);
    api.get(`/employees/${id}/`).then(({ data }) => setEmployee(data)).catch((err) => { setMissing(true); toast(errorText(err), "bad"); });
  }, [id]);
  useEffect(() => {
    if (tab === "attendance") api.get(`/attendance/records/?employee=${id}`).then(({ data }) => setAttendance(data.results));
    if (tab === "leave") api.get(`/leave-requests/?employee=${id}`).then(({ data }) => setLeaves(rowsOf(data)));
    if (tab === "payroll" && (user.capabilities.view_payroll || Number(user.employee_id) === Number(id))) api.get(`/payroll/records/?employee=${id}`).then(({ data }) => setPayroll(rowsOf(data))).catch(() => setPayroll([]));
    if (tab === "timeline") api.get(`/employees/${id}/timeline/`).then(({ data }) => setTimeline(data));
    if (tab === "overview") api.get(`/allowances/?employee=${id}`).then(({ data }) => setAllowances(rowsOf(data))).catch(() => setAllowances([]));
  }, [tab, id]);
  if (missing) return <div className="page"><h1>This profile is not available.</h1><p className="muted">You can only open employee records included in your role.</p></div>;
  if (!employee) return <div className="page"><Spinner label="Loading profile…" /></div>;
  async function deactivate() {
    await api.post(`/employees/${id}/deactivate/`, { exit_date: exitDate, reason, disable_login: true });
    toast("Employee deactivated. Payroll history was kept.");
    setConfirm(false);
    const { data } = await api.get(`/employees/${id}/`);
    setEmployee(data);
  }
  async function addAllowance(event) {
    event.preventDefault();
    await api.post("/allowances/", { employee: Number(id), name: allowance.name, amount: allowance.amount });
    toast("Allowance saved.");
    const { data } = await api.get(`/allowances/?employee=${id}`);
    setAllowances(rowsOf(data));
  }
  return (
    <div className="page">
      <div className="page-head">
        <div className="profile-head">
          <Avatar name={employee.full_name} src={employee.photo_url} size={56} />
          <div>
            <p className="eyebrow" style={{ marginBottom: 2 }}>{employee.employee_code}</p>
            <h1>{employee.full_name}</h1>
            <p className="muted">{employee.job_title_name || "No title"} · {employee.department_name || "No department"} · <Badge value={employee.status} /></p>
          </div>
        </div>
        {user.capabilities.manage_employees && <div className="filters">
          <button className="btn btn-ghost" onClick={() => navigate(`/employees/${id}/edit`)}>Edit</button>
          {employee.status === "active" && <button className="btn btn-danger" onClick={() => setConfirm(true)}>Deactivate</button>}
          {employee.status !== "active" && <button className="btn btn-primary" onClick={async () => { await api.post(`/employees/${id}/reactivate/`, { reason: "Returned to work" }); toast("Employee reactivated."); const { data } = await api.get(`/employees/${id}/`); setEmployee(data); }}>Reactivate</button>}
        </div>}
      </div>
      <Tabs items={["overview", "attendance", "leave", "payroll", "timeline"]} value={tab} onChange={setTab} />
      {tab === "overview" && <div className="grid-2">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <article className="card">
            <h2>Contact</h2>
            <KeyValue items={[
              ["Phone", employee.phone],
              ["Email", employee.email],
              ["Address", employee.address],
              ["Emergency contact", [employee.emergency_contact_name, employee.emergency_contact_relation && `(${employee.emergency_contact_relation})`, employee.emergency_contact_phone].filter(Boolean).join(" ")],
            ]} />
          </article>
          <article className="card">
            <h2>Employment</h2>
            <KeyValue items={[
              ["Joined", employee.joining_date && dayjs(employee.joining_date).format("D MMM YYYY")],
              ["Employment type", humanize(employee.employment_type)],
              ["Shift", employee.shift_name || "Office default, 09:00–17:00"],
              ["Location", employee.location_name],
              employee.exit_date && ["Exit date", dayjs(employee.exit_date).format("D MMM YYYY")],
              ["Notes", employee.notes],
            ]} />
          </article>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {employee.basic_salary !== undefined && <article className="card">
            <h2>Pay</h2>
            <KeyValue items={[
              ["Salary type", humanize(employee.salary_type)],
              employee.salary_type === "monthly" && ["Basic monthly salary", money(employee.basic_salary)],
              employee.salary_type === "daily" && ["Daily rate", money(employee.daily_rate)],
              employee.salary_type === "hourly" && ["Hourly rate", money(employee.hourly_rate)],
              ["Bank", employee.bank_name],
              ["Account", maskAccount(employee.bank_account_number)],
            ]} />
          </article>}
          <article className="card">
            <h2>Allowances</h2>
            <div className="list">{allowances.map((item) => <div key={item.id} className="list-row"><span>{item.name}{!item.is_active && <span className="subtle"> Inactive</span>}</span><strong>{money(item.amount)}</strong></div>)}</div>
            {allowances.length === 0 && <p className="muted">No recurring allowances.</p>}
            {user.capabilities.manage_employees && <form className="filters" style={{ marginTop: 12 }} onSubmit={addAllowance}><input className="input" aria-label="Allowance name" placeholder="Name" value={allowance.name} onChange={(event) => setAllowance({ ...allowance, name: event.target.value })} required /><input className="input" aria-label="Monthly amount" type="number" min="0.01" step="0.01" placeholder="Monthly amount" value={allowance.amount} onChange={(event) => setAllowance({ ...allowance, amount: event.target.value })} required /><button className="btn btn-primary">Add</button></form>}
          </article>
        </div>
      </div>}
      {tab === "attendance" && <div className="card table-wrap"><table><thead><tr><th>Date</th><th>Status</th><th>In</th><th>Out</th><th>Late</th><th>Early</th><th>Hours</th><th>OT</th></tr></thead><tbody>{attendance.map((row) => <tr key={row.id}><td>{row.date}</td><td><Badge value={row.status} /></td><td>{row.check_in_time || "—"}</td><td>{row.check_out_time || "—"}</td><td>{row.late_minutes}</td><td>{row.early_departure_minutes}</td><td>{row.working_hours}</td><td>{row.overtime_hours}</td></tr>)}</tbody></table></div>}
      {tab === "leave" && <div className="card table-wrap"><table><thead><tr><th>Type</th><th>Dates</th><th>Days</th><th>Status</th><th>Reason</th></tr></thead><tbody>{leaves.map((row) => <tr key={row.id}><td>{row.leave_type_name}</td><td>{row.start_date} – {row.end_date}</td><td>{row.total_days}</td><td><Badge value={row.status} /></td><td>{row.reason}</td></tr>)}</tbody></table></div>}
      {tab === "payroll" && <div className="card table-wrap">{user.capabilities.view_payroll || user.role === "employee" ? <table><thead><tr><th>Period</th><th>Gross</th><th>Deductions</th><th>Net</th><th>Status</th></tr></thead><tbody>{payroll.map((row) => <tr key={row.id}><td>{row.period_label}</td><td>{money(row.gross_salary)}</td><td>{money(row.total_deductions)}</td><td>{money(row.net_salary)}</td><td><Badge value={row.payment_status} /></td></tr>)}</tbody></table> : <p>Salary history is hidden for department managers.</p>}</div>}
      {tab === "timeline" && <div className="card">{timeline.map((item) => <p key={item.id}><strong>{item.summary}</strong><br /><span className="muted">{dayjs(item.created_at).format("D MMM YYYY HH:mm")} · {item.actor_name || "System"} {item.reason ? `· ${item.reason}` : ""}</span></p>)}{timeline.length === 0 && <Empty title="No employment events yet" />}</div>}
      {confirm && <Modal title="Deactivate employee" onClose={() => setConfirm(false)}>
        <p>Attendance and payroll history stay on file. This does not delete the person.</p>
        <label className="field">Exit date<input className="input" type="date" value={exitDate} onChange={(event) => setExitDate(event.target.value)} /></label>
        <label className="field">Reason<textarea className="textarea" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <div className="modal-actions"><button className="btn btn-ghost" onClick={() => setConfirm(false)}>Cancel</button><button className="btn btn-danger" onClick={deactivate}>Deactivate</button></div>
      </Modal>}
    </div>
  );
}
