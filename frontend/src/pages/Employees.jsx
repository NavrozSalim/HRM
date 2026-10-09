import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import { Download, Search, UserPlus } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Avatar, Badge, Empty, Pager, Spinner, money } from "../ui";

export default function EmployeesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [departments, setDepartments] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => { api.get("/departments/?page_size=100").then(({ data }) => setDepartments(rowsOf(data))).catch(() => {}); }, []);
  useEffect(() => { const timer = setTimeout(() => { setQuery(search); setPage(1); }, 250); return () => clearTimeout(timer); }, [search]);
  useEffect(() => {
    const params = new URLSearchParams({ page, search: query, ordering: "employee_code" });
    if (status) params.set("status", status);
    if (department) params.set("department", department);
    setError("");
    api.get(`/employees/?${params}`).then(({ data }) => { setRows(rowsOf(data)); setCount(data.count || 0); }).catch((err) => { setRows([]); setError(errorText(err)); });
  }, [page, query, status, department]);
  const showPay = rows?.some((row) => row.basic_salary !== undefined);
  const filtered = query || status || department;
  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">People</p><h1>Employees</h1>{rows !== null && <p className="muted">{count} {count === 1 ? "person" : "people"}{filtered ? " match these filters" : " on record"}.</p>}</div>
        <div className="filters">
          <button className="btn btn-ghost" onClick={() => download(`/exports/employees/?format=xlsx${department ? `&department=${department}` : ""}${status ? `&status=${status}` : ""}`, "employees.xlsx")}><Download size={15} /> Export</button>
          {user.capabilities.manage_employees && <button className="btn btn-primary" onClick={() => navigate("/employees/new")}><UserPlus size={15} /> Add employee</button>}
        </div>
      </div>
      <div className="toolbar">
        <div className="search" style={{ maxWidth: 340 }}><Search size={16} /><input className="input" aria-label="Search employees" placeholder="Search by name, ID, email, or phone" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        <div className="filters">
          <select className="select" style={{ width: 160 }} aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option><option value="active">Active</option><option value="on_notice">On notice</option><option value="inactive">Inactive</option><option value="terminated">Terminated</option></select>
          <select className="select" style={{ width: 200 }} aria-label="Department" value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }}><option value="">All departments</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        </div>
      </div>
      {error && <div className="callout error">{error}</div>}
      <div className="card table-wrap">
        {rows === null ? <Spinner /> : rows.length === 0 ? <Empty title={filtered ? "No employees match" : "No employees yet"} body={filtered ? "Try a different search or clear the filters." : "Add your first employee to get started."} /> : (
          <table>
            <thead><tr><th>Employee</th><th>Department</th><th>Status</th><th>Joined</th>{showPay && <th className="num">Pay</th>}</tr></thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="clickable" onClick={() => navigate(`/employees/${row.id}`)}>
                  <td><div style={{ display: "flex", alignItems: "center", gap: 12 }}><Avatar name={row.full_name} src={row.photo_url} size={34} /><div><strong>{row.full_name}</strong><span className="subtle" style={{ display: "block" }}>{row.employee_code} · {row.job_title_name || "No title"}</span></div></div></td>
                  <td>{row.department_name || <span className="subtle">Unassigned</span>}</td>
                  <td><Badge value={row.status} /></td>
                  <td>{row.joining_date ? dayjs(row.joining_date).format("D MMM YYYY") : "—"}</td>
                  {showPay && <td className="num">{row.salary_type === "daily" && Number(row.daily_rate) ? `${money(row.daily_rate)} / day` : row.salary_type === "hourly" && Number(row.hourly_rate) ? `${money(row.hourly_rate)} / hour` : Number(row.basic_salary) ? `${money(row.basic_salary)} / month` : "—"}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Pager page={page} count={count} onPage={setPage} />
    </div>
  );
}
