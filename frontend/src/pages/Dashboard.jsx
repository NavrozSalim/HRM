import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlarmClock, CalendarClock, CalendarX2, Clock, Gift, LogOut, Palmtree, Timer, TrendingUp, UserCheck, UserMinus, Users, Wallet, AlertTriangle, CircleDollarSign, ClipboardList } from "lucide-react";
import dayjs from "dayjs";
import api, { errorText } from "../api";
import { Avatar, Empty, Spinner, humanize, money } from "../ui";

function Stat({ label, value, icon: Icon, tone = "", hint }) {
  return (
    <article className="card stat">
      <div className="stat-top"><span>{label}</span><span className={`icon-pill ${tone}`}><Icon size={16} /></span></div>
      <strong>{value}</strong>
      {hint && <small>{hint}</small>}
    </article>
  );
}

const tooltipStyle = { contentStyle: { borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface)", color: "var(--text)", fontSize: 12 } };

export default function DashboardPage() {
  const navigate = useNavigate();
  const [date, setDate] = useState(dayjs().format("YYYY-MM-DD"));
  const [department, setDepartment] = useState("");
  const [departments, setDepartments] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/departments/?page_size=100").then(({ data: payload }) => setDepartments(payload.results || [])).catch(() => {}); }, []);
  useEffect(() => {
    const params = new URLSearchParams({ date });
    if (department) params.set("department", department);
    setError("");
    api.get(`/dashboard/?${params}`).then(({ data: payload }) => setData(payload)).catch((err) => setError(errorText(err)));
  }, [date, department]);
  if (error) return <div className="page"><div className="callout error">{error}</div></div>;
  if (!data) return <div className="page"><Spinner label="Loading today's numbers…" /></div>;
  const { today, month, headcount } = data;
  const currency = data.currency;
  const isToday = date === dayjs().format("YYYY-MM-DD");
  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">{data.company_name}</p>
          <h1>{isToday ? "Today in the office" : "Office snapshot"}</h1>
          <p className="muted">{dayjs(data.filters.date).format("dddd, D MMMM YYYY")} · {humanize(data.scope)} view</p>
        </div>
        <div className="filters">
          <input className="input" type="date" value={date} onChange={(event) => setDate(event.target.value)} aria-label="Date" />
          {data.scope !== "personal" && <select className="select" value={department} onChange={(event) => setDepartment(event.target.value)} aria-label="Department"><option value="">All departments</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}
        </div>
      </div>

      <section>
        <div className="section-title"><h2>Attendance</h2></div>
        <div className="stat-grid">
          <Stat label="Present" value={today.present} icon={UserCheck} tone="green" hint={`${today.on_time} on time`} />
          <Stat label="Late arrivals" value={today.late} icon={AlarmClock} tone="amber" />
          <Stat label="Absent" value={today.absent} icon={UserMinus} tone="red" />
          <Stat label="On leave" value={today.on_leave} icon={Palmtree} tone="violet" />
          <Stat label="Not checked in yet" value={today.not_checked_in} icon={Clock} />
          <Stat label="Missing check-out" value={today.incomplete} icon={AlertTriangle} tone="amber" />
          <Stat label="Early departures" value={today.early_departures} icon={LogOut} />
          <Stat label="Hours worked" value={today.working_hours} icon={Timer} />
        </div>
      </section>

      <section>
        <div className="section-title"><h2>This month</h2>{month.needs_recalculation && <span className="badge pending">Payroll needs recalculation</span>}</div>
        <div className="stat-grid">
          <Stat label="Employees" value={headcount.total} icon={Users} hint={`${headcount.active} active · ${headcount.inactive} inactive`} />
          <Stat label="Attendance rate" value={`${month.attendance_percentage}%`} icon={TrendingUp} tone="green" />
          <Stat label="Payroll total" value={month.payroll_total === null ? "Restricted" : money(month.payroll_total, currency)} icon={Wallet} hint={month.payroll_total === null ? undefined : humanize(month.payroll_source)} />
          <Stat label="Pending leave requests" value={data.pending_leave_requests} icon={ClipboardList} tone="violet" />
          <Stat label="Unpaid salaries" value={data.unpaid_salaries.count} icon={CircleDollarSign} tone={data.unpaid_salaries.count ? "red" : ""} hint={data.unpaid_salaries.amount === null ? undefined : `${money(data.unpaid_salaries.amount, currency)} outstanding`} />
        </div>
      </section>

      <section className="grid-2 even">
        <article className="card">
          <h2>Late arrivals over the last 14 days</h2>
          <div style={{ height: 240, marginTop: 8 }}>
            <ResponsiveContainer>
              <LineChart data={data.charts.late_trend} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" tickFormatter={(value) => dayjs(value).format("D MMM")} tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
                <Tooltip {...tooltipStyle} labelFormatter={(value) => dayjs(value).format("D MMM YYYY")} />
                <Line type="monotone" dataKey="late" name="Late" stroke="#2f5bea" strokeWidth={2.5} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
        <article className="card">
          <h2>Status breakdown</h2>
          <div style={{ height: 240, marginTop: 8 }}>
            <ResponsiveContainer>
              <BarChart data={data.charts.status_breakdown.map((item) => ({ ...item, label: humanize(item.status) }))} margin={{ left: -20, right: 8, top: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "var(--text-3)" }} axisLine={false} tickLine={false} />
                <Tooltip {...tooltipStyle} cursor={{ fill: "var(--surface-2)" }} />
                <Bar dataKey="total" name="Employees" fill="#2f5bea" radius={[6, 6, 0, 0]} maxBarSize={48} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="grid-3">
        <article className="card">
          <h2>Headcount by department</h2>
          <div className="list">
            {data.charts.department_headcount.map((item) => <div key={item.department} className="list-row"><span>{item.department}</span><strong>{item.total}</strong></div>)}
          </div>
          {data.charts.department_headcount.length === 0 && <Empty title="No active employees" body="Nobody matches this filter." />}
          {data.charts.payroll_by_department.length > 0 && <>
            <h2 style={{ marginTop: 20, marginBottom: 4 }}>Payroll by department</h2>
            <div className="list">{data.charts.payroll_by_department.map((item) => <div key={item.department} className="list-row"><span>{item.department}</span><strong>{money(item.total, currency)}</strong></div>)}</div>
          </>}
        </article>
        <article className="card">
          <h2>Upcoming celebrations</h2>
          <div className="list">
            {data.birthdays.map((item) => (
              <button key={`${item.employee_id}-b`} className="list-row btn-link" style={{ color: "inherit", textAlign: "left", width: "100%" }} onClick={() => navigate(`/employees/${item.employee_id}`)}>
                <span className="person"><Avatar name={item.full_name} size={30} /><span><strong>{item.full_name}</strong><small>Birthday</small></span></span>
                <span className="badge open"><Gift size={12} /> {dayjs(item.date).format("D MMM")}</span>
              </button>
            ))}
            {data.anniversaries.map((item) => (
              <button key={`${item.employee_id}-a`} className="list-row btn-link" style={{ color: "inherit", textAlign: "left", width: "100%" }} onClick={() => navigate(`/employees/${item.employee_id}`)}>
                <span className="person"><Avatar name={item.full_name} size={30} /><span><strong>{item.full_name}</strong><small>{item.years} year{item.years === 1 ? "" : "s"} at the company</small></span></span>
                <span className="badge approved"><CalendarClock size={12} /> {dayjs(item.date).format("D MMM")}</span>
              </button>
            ))}
          </div>
          {data.birthdays.length === 0 && data.anniversaries.length === 0 && <Empty title="Nothing in the next two weeks" />}
        </article>
        <article className="card">
          <div className="section-title" style={{ marginBottom: 4 }}>
            <h2>Recent activity</h2>
            <div className="filters">
              <button className="btn btn-ghost btn-sm" onClick={() => navigate("/leaves")}><CalendarX2 size={14} /> Leave</button>
              <button className="btn btn-primary btn-sm" onClick={() => navigate("/attendance")}><Clock size={14} /> Attendance</button>
            </div>
          </div>
          <div className="list">
            {data.recent_activity.map((item) => <div key={item.id} className="list-row" style={{ alignItems: "flex-start" }}><div><span>{item.summary}</span><span className="subtle">{item.actor} · {dayjs(item.created_at).format("D MMM, HH:mm")}</span></div></div>)}
          </div>
          {data.recent_activity.length === 0 && <Empty title="No activity yet" />}
        </article>
      </section>
    </div>
  );
}
