import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { Check, ChevronLeft, ChevronRight, Download, Plus, X } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Badge, Empty, Modal, Spinner, Tabs, useToast } from "../ui";

const blankForm = (employee) => ({ leave_type: "", start_date: "", end_date: "", day_part: "full", reason: "", employee: employee || "" });

export default function LeavesPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("requests");
  const [status, setStatus] = useState("");
  const [requests, setRequests] = useState(null);
  const [types, setTypes] = useState([]);
  const [balances, setBalances] = useState([]);
  const [calendar, setCalendar] = useState(null);
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [form, setForm] = useState(blankForm(user.employee_id));
  const [file, setFile] = useState(null);
  const [creating, setCreating] = useState(false);
  const [decision, setDecision] = useState(null);
  const [note, setNote] = useState("");
  const [employees, setEmployees] = useState([]);
  const staff = user.role !== "employee";
  useEffect(() => { api.get("/leave-types/?page_size=100").then(({ data }) => setTypes(rowsOf(data))); }, []);
  useEffect(() => { if (staff) api.get("/employees/?page_size=200").then(({ data }) => setEmployees(rowsOf(data))).catch(() => {}); }, [user]);
  function load() {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    api.get(`/leave-requests/?${params}`).then(({ data }) => setRequests(rowsOf(data))).catch(() => setRequests([]));
    api.get("/leave-balances/?page_size=200").then(({ data }) => setBalances(rowsOf(data)));
    const [year, monthNumber] = month.split("-");
    api.get(`/leave-calendar/?year=${year}&month=${Number(monthNumber)}`).then(({ data }) => setCalendar(data));
  }
  useEffect(() => { load(); }, [status, month]);

  async function submit(event) {
    event.preventDefault();
    const payload = new FormData();
    const body = { ...form, end_date: form.day_part === "full" ? form.end_date : form.start_date };
    Object.entries(body).forEach(([key, value]) => { if (value) payload.append(key, value); });
    if (file) payload.append("document", file);
    try {
      await api.post("/leave-requests/", payload);
      toast("Leave request submitted.");
      setCreating(false);
      setForm(blankForm(user.employee_id));
      setFile(null);
      load();
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function act(row, action, text) {
    try {
      await api.post(`/leave-requests/${row.id}/${action}/`, { note: text || "" });
      toast({ approve: "Leave approved.", reject: "Leave rejected.", cancel: "Leave cancelled." }[action]);
      setDecision(null);
      setNote("");
      load();
    } catch (err) { toast(errorText(err), "bad"); }
  }

  const start = dayjs(`${month}-01`);
  const days = Array.from({ length: start.daysInMonth() }, (_, index) => start.date(index + 1));
  const lead = (start.day() + 6) % 7;
  const canDecide = (row) => row.status === "pending" && user.capabilities.approve_leave && row.employee !== user.employee_id;

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Time off</p><h1>Leave</h1><p className="muted">Approved leave is written into attendance automatically. It is never treated as an absence.</p></div>
        <div className="filters">
          <button className="btn btn-ghost" onClick={() => download(`/exports/leave/?format=xlsx${status ? `&status=${status}` : ""}`, "leave.xlsx")}><Download size={15} /> Export</button>
          <button className="btn btn-primary" onClick={() => setCreating(true)}><Plus size={15} /> New request</button>
        </div>
      </div>
      <div className="toolbar">
        <Tabs items={[{ value: "requests", label: "Requests" }, { value: "calendar", label: "Calendar" }, { value: "balances", label: "Balances" }]} value={tab} onChange={setTab} />
        {tab === "requests" && <select className="select" style={{ width: 180 }} aria-label="Status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="rejected">Rejected</option><option value="cancelled">Cancelled</option></select>}
        {tab === "calendar" && <div className="filters">
          <button className="icon-btn" aria-label="Previous month" onClick={() => setMonth(start.subtract(1, "month").format("YYYY-MM"))}><ChevronLeft size={16} /></button>
          <strong style={{ minWidth: 130, textAlign: "center" }}>{start.format("MMMM YYYY")}</strong>
          <button className="icon-btn" aria-label="Next month" onClick={() => setMonth(start.add(1, "month").format("YYYY-MM"))}><ChevronRight size={16} /></button>
        </div>}
      </div>

      {tab === "requests" && <div className="card table-wrap">
        {requests === null ? <Spinner /> : requests.length === 0 ? <Empty title="No leave requests" body="New requests appear here for approval." /> : (
          <table>
            <thead><tr>{staff && <th>Employee</th>}<th>Type</th><th>Dates</th><th className="num">Days</th><th>Status</th><th /></tr></thead>
            <tbody>{requests.map((row) => (
              <tr key={row.id}>
                {staff && <td><strong>{row.employee_name}</strong></td>}
                <td>{row.leave_type_name}</td>
                <td>
                  {dayjs(row.start_date).format("D MMM")}{row.end_date !== row.start_date ? ` – ${dayjs(row.end_date).format("D MMM YYYY")}` : ` ${dayjs(row.start_date).format("YYYY")}`}
                  {row.day_part !== "full" && <span className="subtle"> · {row.day_part === "first_half" ? "Morning" : "Afternoon"}</span>}
                  <span className="subtle" style={{ display: "block" }}>{row.reason}</span>
                </td>
                <td className="num">{Number(row.total_days)}</td>
                <td><Badge value={row.status} /></td>
                <td className="num"><div className="filters" style={{ justifyContent: "flex-end" }}>
                  {canDecide(row) && <button className="btn btn-primary btn-sm" onClick={() => act(row, "approve", "Approved")}><Check size={14} /> Approve</button>}
                  {canDecide(row) && <button className="btn btn-ghost btn-sm" onClick={() => { setNote(""); setDecision({ row, action: "reject" }); }}><X size={14} /> Reject</button>}
                  {(row.status === "pending" || (row.status === "approved" && user.capabilities.approve_leave)) && <button className="btn btn-ghost btn-sm" onClick={() => { setNote(""); setDecision({ row, action: "cancel" }); }}>Cancel</button>}
                </div></td>
              </tr>
            ))}</tbody>
          </table>
        )}
      </div>}

      {tab === "calendar" && <div className="card">
        <div className="calendar">
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => <div key={day} className="subtle" style={{ fontWeight: 650, padding: "0 4px" }}>{day}</div>)}
          {Array.from({ length: lead }).map((_, index) => <div key={`lead-${index}`} />)}
          {days.map((day) => {
            const key = day.format("YYYY-MM-DD");
            const items = (calendar?.requests || []).filter((item) => item.start_date <= key && item.end_date >= key);
            const holiday = (calendar?.holidays || []).find((item) => item.date === key);
            const weekend = day.day() === 0 || day.day() === 6;
            const isToday = key === dayjs().format("YYYY-MM-DD");
            return (
              <div key={key} className="day-cell" style={{ background: holiday ? "var(--brand-soft)" : weekend ? "var(--surface-2)" : undefined, borderColor: isToday ? "var(--brand)" : undefined }}>
                <strong style={{ color: isToday ? "var(--brand)" : undefined }}>{day.date()}</strong>
                {holiday && <div className="subtle" style={{ color: "var(--brand)" }}>{holiday.name}</div>}
                {items.map((item) => <div key={item.id} className={`badge ${item.status}`} style={{ marginTop: 4, maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis" }}>{item.employee_name.split(" ")[0]} · {item.leave_type_code}</div>)}
              </div>
            );
          })}
        </div>
      </div>}

      {tab === "balances" && <div className="card table-wrap">
        {balances.length === 0 ? <Empty title="No balances yet" /> : <table>
          <thead><tr><th>Employee</th><th>Leave type</th><th>Year</th><th className="num">Entitled</th><th className="num">Used</th><th className="num">Pending</th><th className="num">Available</th></tr></thead>
          <tbody>{balances.map((row) => <tr key={row.id}><td><strong>{row.employee_name}</strong></td><td>{row.leave_type_name}</td><td>{row.year}</td><td className="num">{Number(row.entitled)}</td><td className="num">{Number(row.used)}</td><td className="num">{Number(row.pending)}</td><td className="num"><strong>{Number(row.available)}</strong></td></tr>)}</tbody>
        </table>}
      </div>}

      {creating && <Modal title="New leave request" onClose={() => setCreating(false)}>
        <form className="form-grid" onSubmit={submit}>
          {staff && <label className="field span-2"><span>Employee</span><select className="select" value={form.employee} onChange={(event) => setForm({ ...form, employee: event.target.value })} required><option value="">Choose an employee…</option>{employees.map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_code}</option>)}</select></label>}
          <label className="field"><span>Leave type</span><select className="select" value={form.leave_type} onChange={(event) => setForm({ ...form, leave_type: event.target.value })} required><option value="">Choose…</option>{types.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}{item.is_paid ? "" : " (unpaid)"}</option>)}</select></label>
          <label className="field"><span>Duration</span><select className="select" value={form.day_part} onChange={(event) => setForm({ ...form, day_part: event.target.value })}><option value="full">Full days</option><option value="first_half">Half day, morning</option><option value="second_half">Half day, afternoon</option></select></label>
          <label className="field"><span>{form.day_part === "full" ? "From" : "Date"}</span><input className="input" type="date" value={form.start_date} onChange={(event) => setForm({ ...form, start_date: event.target.value, end_date: form.end_date && form.end_date >= event.target.value ? form.end_date : event.target.value })} required /></label>
          {form.day_part === "full" ? <label className="field"><span>To</span><input className="input" type="date" min={form.start_date} value={form.end_date} onChange={(event) => setForm({ ...form, end_date: event.target.value })} required /></label> : <div />}
          <label className="field span-2"><span>Reason</span><textarea className="textarea" value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} required /></label>
          <label className="field span-2"><span>Supporting document</span><input className="input" type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} /><small>Optional. A medical note, for example.</small></label>
          <div className="modal-actions span-2"><button type="button" className="btn btn-ghost" onClick={() => setCreating(false)}>Cancel</button><button className="btn btn-primary">Submit request</button></div>
        </form>
      </Modal>}

      {decision && <Modal title={decision.action === "reject" ? "Reject leave request" : "Cancel leave"} onClose={() => setDecision(null)}>
        <p className="muted">{decision.row.employee_name} · {decision.row.leave_type_name} · {dayjs(decision.row.start_date).format("D MMM")}{decision.row.end_date !== decision.row.start_date ? ` – ${dayjs(decision.row.end_date).format("D MMM")}` : ""}</p>
        {decision.action === "cancel" && <p className="muted">Any reserved balance is returned, and attendance written for this leave is cleared.</p>}
        <label className="field"><span>{decision.action === "reject" ? "Reason for the employee" : "Note (optional)"}</span><textarea className="textarea" value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <div className="modal-actions">
          <button className="btn btn-ghost" onClick={() => setDecision(null)}>Keep request</button>
          <button className="btn btn-danger" disabled={decision.action === "reject" && !note.trim()} onClick={() => act(decision.row, decision.action, note)}>{decision.action === "reject" ? "Reject" : "Cancel leave"}</button>
        </div>
      </Modal>}
    </div>
  );
}
