import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import dayjs from "dayjs";
import api, { errorText } from "../api";
import { Avatar, Badge, Empty, Spinner, useToast } from "../ui";

export default function SearchPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const query = params.get("q") || "";
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!query) { setData({ employees: [], leave_requests: [] }); return; }
    setData(null);
    api.get(`/search/?q=${encodeURIComponent(query)}`).then(({ data: payload }) => setData(payload)).catch((err) => { setData({ employees: [], leave_requests: [] }); toast(errorText(err), "bad"); });
  }, [query]);
  return (
    <div className="page">
      <div className="page-head"><div><p className="eyebrow">Search</p><h1>{query ? `Results for “${query}”` : "Search"}</h1><p className="muted">Searches people and leave requests you have access to. Salary and bank details are never included.</p></div></div>
      {data === null ? <Spinner label="Searching…" /> : !query ? <div className="card"><Empty title="Type in the search bar above" body="Search by name, employee ID, email, or phone." /></div> : <div className="grid-2">
        <article className="card">
          <h2>People <span className="subtle">{data.employees.length}</span></h2>
          {data.employees.length === 0 ? <Empty title="No matching people" /> : <div className="list">{data.employees.map((item) => (
            <button key={item.id} className="list-row" style={{ background: "none", border: 0, borderBottom: "1px solid var(--border)", width: "100%", textAlign: "left", cursor: "pointer", color: "inherit", font: "inherit" }} onClick={() => navigate(`/employees/${item.id}`)}>
              <span style={{ display: "flex", gap: 12, alignItems: "center" }}><Avatar name={item.full_name} size={32} /><span><strong>{item.full_name}</strong><span className="subtle">{item.employee_code} · {item.department || "Unassigned"}</span></span></span>
            </button>
          ))}</div>}
        </article>
        <article className="card">
          <h2>Leave requests <span className="subtle">{data.leave_requests.length}</span></h2>
          {data.leave_requests.length === 0 ? <Empty title="No matching leave requests" /> : <div className="list">{data.leave_requests.map((item) => (
            <button key={item.id} className="list-row" style={{ background: "none", border: 0, borderBottom: "1px solid var(--border)", width: "100%", textAlign: "left", cursor: "pointer", color: "inherit", font: "inherit" }} onClick={() => navigate("/leaves")}>
              <span><strong>{item.employee}</strong><span className="subtle">{item.type} · {dayjs(item.start_date).format("D MMM YYYY")}</span></span>
              <Badge value={item.status} />
            </button>
          ))}</div>}
        </article>
      </div>}
    </div>
  );
}
