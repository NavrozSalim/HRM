import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { Download, FileText } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { Badge, Empty, KeyValue, Spinner, Tabs, money, useToast } from "../ui";

const SOURCE = {
  preview: "Live preview from attendance. Payroll has not been calculated for this month.",
  open: "From a payroll month that has not been calculated yet.",
  calculated: "From calculated payroll, not yet approved.",
  approved: "From approved payroll, not yet finalized.",
  finalized: "From the finalized payroll snapshot. Later salary edits do not change it.",
  reopened: "From payroll that was reopened for corrections.",
};
const num = (value) => (value === null || value === undefined || value === "" ? "—" : Number(value).toString());

export default function ReportsPage() {
  const toast = useToast();
  const [employees, setEmployees] = useState([]);
  const [employee, setEmployee] = useState("");
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [report, setReport] = useState(null);
  const [company, setCompany] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState("employee");
  const [year, monthNumber] = month.split("-");
  const query = `year=${year}&month=${Number(monthNumber)}`;
  useEffect(() => { api.get("/employees/?page_size=200").then(({ data }) => { const items = rowsOf(data); setEmployees(items); if (items[0]) setEmployee(String(items[0].id)); }); }, []);
  useEffect(() => {
    if (tab === "employee" && !employee) return;
    setLoading(true);
    const request = tab === "employee" ? api.get(`/reports/employee-monthly/?employee=${employee}&${query}`) : api.get(`/reports/company-monthly/?${query}`);
    request.then(({ data }) => (tab === "employee" ? setReport(data) : setCompany(data))).catch((err) => toast(errorText(err), "bad")).finally(() => setLoading(false));
  }, [tab, employee, month]);
  const a = report?.attendance || {};
  const fileMonth = `${year}-${monthNumber}`;

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Overview</p><h1>Monthly reports</h1><p className="muted">Attendance and salary history for one person or the whole company.</p></div>
        <div className="filters">
          {tab === "employee" && employee && <button className="btn btn-ghost" onClick={() => download(`/reports/employee-monthly/?employee=${employee}&${query}&format=pdf`, `report-${report?.employee?.employee_code || employee}-${fileMonth}.pdf`)}><FileText size={15} /> PDF</button>}
          {tab === "company" && <button className="btn btn-ghost" onClick={() => download(`/reports/company-monthly/?${query}&format=xlsx`, `company-report-${fileMonth}.xlsx`)}><Download size={15} /> Excel</button>}
          {tab === "company" && <button className="btn btn-ghost" onClick={() => download(`/reports/company-monthly/?${query}&format=pdf`, `company-report-${fileMonth}.pdf`)}><FileText size={15} /> PDF</button>}
        </div>
      </div>
      <div className="toolbar">
        <Tabs items={[{ value: "employee", label: "Employee" }, { value: "company", label: "Company" }]} value={tab} onChange={setTab} />
        <div className="filters">
          {tab === "employee" && <select className="select" style={{ width: 230 }} aria-label="Employee" value={employee} onChange={(event) => setEmployee(event.target.value)}>{employees.map((item) => <option key={item.id} value={item.id}>{item.full_name} · {item.employee_code}</option>)}</select>}
          <input className="input" style={{ width: 170 }} aria-label="Month" type="month" value={month} onChange={(event) => event.target.value && setMonth(event.target.value)} />
        </div>
      </div>

      {loading && <Spinner label="Building report…" />}

      {!loading && tab === "employee" && (!report ? <div className="card"><Empty title="Choose an employee" /></div> : <>
        <div className={`callout ${report.stale ? "warn" : ""}`}><span>{SOURCE[report.source] || ""}{report.stale ? " Inputs changed since the last calculation, so these figures may be out of date." : ""}</span></div>
        <div className="grid-2">
          <article className="card">
            <h2>{report.employee.full_name}</h2>
            <p className="subtle" style={{ marginTop: -6 }}>{report.employee.employee_code} · {report.employee.job_title || "No title"} · {report.employee.department || "No department"} · {report.period.label}</p>
            <KeyValue items={[
              ["Scheduled working days", num(a.scheduled_working_days)],
              ["Present", num(a.present_days)],
              ["Absent", num(a.absent_days)],
              ["Half days", num(a.half_days)],
              ["Paid leave", num(a.paid_leave_days)],
              ["Unpaid leave", num(a.unpaid_leave_days)],
              ["Weekly offs", num(a.weekly_offs)],
              ["Public holidays", num(a.public_holidays)],
              ["Late arrivals", `${num(a.late_count)}${a.late_minutes ? ` (${a.late_minutes} min)` : ""}`],
              ["Early departures", num(a.early_departures)],
              ["Hours worked", num(a.working_hours)],
              ["Overtime", `${num(a.overtime_hours)} h`],
              ["Attendance", a.attendance_percentage !== undefined ? `${num(a.attendance_percentage)}%` : "—"],
              ["Punctuality", a.punctuality_percentage !== null && a.punctuality_percentage !== undefined ? `${num(a.punctuality_percentage)}%` : "—"],
            ]} />
          </article>
          <article className="card">
            {report.salary ? <>
              <div className="toolbar" style={{ marginBottom: 8 }}><h2 style={{ margin: 0 }}>Salary</h2><Badge value={report.salary.payment_status} /></div>
              <div className="list">
                {(report.salary.lines || []).map((line, index) => <div key={index} className="list-row"><span>{line.label}</span><strong style={{ color: line.kind === "deduction" ? "var(--danger)" : undefined }}>{line.kind === "deduction" ? "−" : ""}{money(line.amount, report.currency)}</strong></div>)}
                <div className="list-row"><span>Gross</span><strong>{money(report.salary.gross_salary, report.currency)}</strong></div>
                <div className="list-row"><span>Total deductions</span><strong>{money(report.salary.total_deductions, report.currency)}</strong></div>
                <div className="list-row"><span><strong>Net salary</strong></span><strong style={{ fontSize: 18 }}>{money(report.salary.net_salary, report.currency)}</strong></div>
              </div>
            </> : <Empty title="Salary hidden" body="Your role does not include salary figures." />}
            {(report.warnings || []).map((warning) => <div key={warning} className="callout warn" style={{ marginTop: 10 }}><span>{warning}</span></div>)}
          </article>
        </div>
      </>)}

      {!loading && tab === "company" && company && <>
        <div className="card table-wrap">
          {company.departments.length === 0 ? <Empty title="No employees in this report" /> : <table>
            <thead><tr><th>Department</th><th className="num">People</th><th className="num">Present days</th><th className="num">Absent days</th>{company.departments.some((item) => item.net_salary !== null) && <th className="num">Net payroll</th>}</tr></thead>
            <tbody>{company.departments.map((item) => <tr key={item.department}><td><strong>{item.department}</strong></td><td className="num">{item.employees}</td><td className="num">{num(item.present_days)}</td><td className="num">{num(item.absent_days)}</td>{item.net_salary !== null && <td className="num">{money(item.net_salary)}</td>}</tr>)}</tbody>
          </table>}
        </div>
        {company.employees.length > 0 && <div className="card table-wrap"><table>
          <thead><tr><th>Employee</th><th className="num">Present</th><th className="num">Absent</th><th className="num">Late</th><th className="num">Attendance</th><th className="num">Net</th><th>Payment</th></tr></thead>
          <tbody>{company.employees.map((row) => <tr key={row.employee.id}><td><strong>{row.employee.full_name}</strong><span className="subtle" style={{ display: "block" }}>{row.employee.department || "Unassigned"}</span></td><td className="num">{num(row.attendance.present_days)}</td><td className="num">{num(row.attendance.absent_days)}</td><td className="num">{num(row.attendance.late_count)}</td><td className="num">{num(row.attendance.attendance_percentage)}%</td><td className="num">{row.salary ? money(row.salary.net_salary) : "—"}</td><td>{row.salary ? <Badge value={row.salary.payment_status} /> : "—"}</td></tr>)}</tbody>
        </table></div>}
      </>}
    </div>
  );
}
