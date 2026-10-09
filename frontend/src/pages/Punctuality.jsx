import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { AlertTriangle } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api, { errorText, rowsOf } from "../api";
import { Empty, Pager, Spinner, useToast } from "../ui";

const tooltipStyle = { background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--text)", fontSize: 12 };

export default function PunctualityPage() {
  const toast = useToast();
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [department, setDepartment] = useState("");
  const [departments, setDepartments] = useState([]);
  const [data, setData] = useState(null);
  const [page, setPage] = useState(1);
  useEffect(() => { api.get("/departments/?page_size=100").then(({ data: payload }) => setDepartments(rowsOf(payload))).catch(() => {}); }, []);
  useEffect(() => {
    const [year, monthNumber] = month.split("-");
    const params = new URLSearchParams({ year, month: Number(monthNumber), page });
    if (department) params.set("department", department);
    setData(null);
    api.get(`/attendance/punctuality/?${params}`).then(({ data: payload }) => setData(payload)).catch((err) => toast(errorText(err), "bad"));
  }, [month, department, page]);
  const warned = data?.results.filter((row) => row.warning) || [];

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Overview</p><h1>Punctuality</h1><p className="muted">Late arrivals, absences, and early departures for the month. Late arrivals only reduce pay if a super admin turns on late penalties.</p></div>
        <div className="filters">
          <select className="select" style={{ width: 190 }} aria-label="Department" value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }}><option value="">All departments</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          <input className="input" style={{ width: 170 }} aria-label="Month" type="month" value={month} onChange={(event) => { if (event.target.value) { setMonth(event.target.value); setPage(1); } }} />
        </div>
      </div>
      {!data ? <Spinner label="Calculating punctuality…" /> : <>
        {warned.length > 0 && <div className="callout warn"><AlertTriangle size={16} /><span>{warned.length} {warned.length === 1 ? "person has" : "people have"} reached {data.monthly_late_warning_threshold} or more late arrivals this month: {warned.map((row) => row.full_name).join(", ")}.</span></div>}
        <article className="card">
          <h2>Late arrivals by department</h2>
          {data.departments.length === 0 ? <Empty title="No data for this month" /> : <div style={{ height: 240 }}><ResponsiveContainer>
            <BarChart data={data.departments} margin={{ left: -20, right: 8 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" />
              <XAxis dataKey="department" tickLine={false} axisLine={false} tick={{ fill: "var(--text-3)", fontSize: 12 }} />
              <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fill: "var(--text-3)", fontSize: 12 }} />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--surface-2)" }} formatter={(value) => [value, "Late arrivals"]} />
              <Bar dataKey="late_count" fill="#f79009" radius={[6, 6, 0, 0]} maxBarSize={48} />
            </BarChart>
          </ResponsiveContainer></div>}
        </article>
        <div className="card table-wrap">
          {data.results.length === 0 ? <Empty title="No employees in this view" /> : <table>
            <thead><tr><th>Employee</th><th className="num">Late</th><th className="num">Late minutes</th><th className="num">Absent</th><th className="num">Paid leave</th><th className="num">Unpaid leave</th><th className="num">Half days</th><th className="num">Left early</th><th className="num">Overtime</th><th className="num">Absence streak</th><th className="num">Attendance</th><th className="num">On time</th></tr></thead>
            <tbody>{data.results.map((row) => <tr key={row.employee_id}>
              <td><strong>{row.full_name}</strong>{row.warning && <span className="badge late" style={{ marginLeft: 8 }}>Warning</span>}<span className="subtle" style={{ display: "block" }}>{row.department || "Unassigned"}</span></td>
              <td className="num">{row.late_count}</td>
              <td className="num">{row.late_minutes}</td>
              <td className="num">{Number(row.absent_days)}</td>
              <td className="num">{Number(row.paid_leave_days)}</td>
              <td className="num">{Number(row.unpaid_leave_days)}</td>
              <td className="num">{Number(row.half_days)}</td>
              <td className="num">{row.early_departures}</td>
              <td className="num">{Number(row.overtime_hours)} h</td>
              <td className="num">{row.consecutive_absences ? `${row.consecutive_absences} days` : "—"}</td>
              <td className="num">{Number(row.attendance_percentage)}%</td>
              <td className="num">{row.punctuality_percentage === null || row.punctuality_percentage === undefined ? "—" : `${Number(row.punctuality_percentage)}%`}</td>
            </tr>)}</tbody>
          </table>}
        </div>
        <Pager page={page} count={data.count} onPage={setPage} />
      </>}
    </div>
  );
}
