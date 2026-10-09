import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { ChevronLeft, ChevronRight, Download, FileSpreadsheet, Lock, Upload } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Badge, Empty, Modal, Pager, Spinner, Tabs, humanize, useToast } from "../ui";

const FILTER_STATUSES = ["present", "late", "absent", "half_day", "on_leave", "weekly_off", "public_holiday", "incomplete", "unmarked"];
const EDIT_STATUSES = ["present", "late", "absent", "half_day", "on_leave", "weekly_off", "public_holiday", "holiday_worked", "off_worked", "incomplete"];
const LEGEND = ["present", "late", "absent", "half_day", "on_leave", "weekly_off", "public_holiday", "incomplete"];

export default function AttendancePage() {
  const { user } = useAuth();
  const toast = useToast();
  const [tab, setTab] = useState("daily");
  const [date, setDate] = useState(dayjs().format("YYYY-MM-DD"));
  const [department, setDepartment] = useState("");
  const [status, setStatus] = useState("");
  const [departments, setDepartments] = useState([]);
  const [rows, setRows] = useState(null);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [grid, setGrid] = useState(null);
  const [edit, setEdit] = useState(null);
  const [selected, setSelected] = useState([]);
  const [bulk, setBulk] = useState({ check_in: "09:00", check_out: "17:00", status: "", reason: "" });
  const [importResult, setImportResult] = useState(null);
  const canEdit = user.capabilities.manage_attendance;
  const canImport = ["super_admin", "management", "hr_manager"].includes(user.role);
  useEffect(() => { api.get("/departments/?page_size=100").then(({ data }) => setDepartments(rowsOf(data))).catch(() => {}); }, []);
  function loadDaily() {
    const params = new URLSearchParams({ date, page, page_size: 25 });
    if (department) params.set("department", department);
    if (status) params.set("status", status);
    api.get(`/attendance/daily/?${params}`).then(({ data }) => { setRows(data.results); setCount(data.count); }).catch((err) => { setRows([]); toast(errorText(err), "bad"); });
  }
  function loadGrid() {
    const [year, month] = date.split("-");
    const params = new URLSearchParams({ year, month: Number(month), page });
    if (department) params.set("department", department);
    setGrid(null);
    api.get(`/attendance/grid/?${params}`).then(({ data }) => setGrid(data)).catch((err) => toast(errorText(err), "bad"));
  }
  useEffect(() => { if (tab === "daily") loadDaily(); else if (tab === "grid") loadGrid(); }, [tab, date, department, status, page]);

  async function saveEdit(event) {
    event.preventDefault();
    try {
      await api.post("/attendance/mark/", { ...edit, date: edit.date || date, reason: edit.reason || "" });
      toast("Attendance saved.");
      setEdit(null);
      loadDaily();
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function saveBulk() {
    try {
      const { data } = await api.post("/attendance/bulk/", { date, employee_ids: selected, ...bulk });
      toast(`Saved ${data.created + data.updated} records${data.errors.length ? `, skipped ${data.errors.length}` : ""}.`, data.errors.length ? "bad" : "good");
      setSelected([]);
      loadDaily();
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function importFile(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const payload = new FormData();
    payload.append("file", file);
    try {
      const { data } = await api.post("/attendance/import/", payload);
      setImportResult(data);
      toast(`Imported ${data.created + data.updated} rows.`);
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function lockDay() {
    const day = dayjs(date).subtract(1, "day").format("YYYY-MM-DD");
    try { const { data } = await api.post("/attendance/close-day/", { date: day }); toast(data.detail); } catch (err) { toast(errorText(err), "bad"); }
  }
  const shift = (amount) => setDate(dayjs(date).add(amount, tab === "grid" ? "month" : "day").format("YYYY-MM-DD"));
  const allSelected = rows?.length > 0 && rows.every((row) => selected.includes(row.employee_id));

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Time</p><h1>Attendance</h1><p className="muted">Late minutes start after the shift's grace period. Weekly offs, holidays, and approved leave never count as absences.</p></div>
        <button className="btn btn-ghost" onClick={() => download(`/exports/attendance/?from=${date.slice(0, 7)}-01&to=${tab === "grid" ? dayjs(date).endOf("month").format("YYYY-MM-DD") : date}&format=xlsx${department ? `&department=${department}` : ""}`, "attendance.xlsx")}><Download size={15} /> Export</button>
      </div>
      <div className="toolbar">
        <Tabs items={[{ value: "daily", label: "Daily" }, { value: "grid", label: "Monthly grid" }, ...(canImport ? [{ value: "import", label: "Import" }] : [])]} value={tab} onChange={(item) => { setTab(item); setPage(1); }} />
        {tab !== "import" && <div className="filters">
          <button className="icon-btn" aria-label="Previous" onClick={() => shift(-1)}><ChevronLeft size={16} /></button>
          <input className="input" style={{ width: 170 }} aria-label={tab === "grid" ? "Month" : "Date"} type={tab === "grid" ? "month" : "date"} value={tab === "grid" ? date.slice(0, 7) : date} onChange={(event) => event.target.value && setDate(tab === "grid" ? `${event.target.value}-01` : event.target.value)} />
          <button className="icon-btn" aria-label="Next" onClick={() => shift(1)}><ChevronRight size={16} /></button>
          <select className="select" style={{ width: 180 }} aria-label="Department" value={department} onChange={(event) => { setDepartment(event.target.value); setPage(1); }}><option value="">All departments</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
          {tab === "daily" && <select className="select" style={{ width: 160 }} aria-label="Status" value={status} onChange={(event) => { setStatus(event.target.value); setPage(1); }}><option value="">All statuses</option>{FILTER_STATUSES.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}</select>}
        </div>}
      </div>

      {tab === "daily" && <>
        {canEdit && selected.length > 0 && <div className="card filters">
          <strong>{selected.length} selected</strong>
          <input className="input" style={{ width: 120 }} aria-label="Check in" type="time" value={bulk.check_in} onChange={(event) => setBulk({ ...bulk, check_in: event.target.value })} />
          <input className="input" style={{ width: 120 }} aria-label="Check out" type="time" value={bulk.check_out} onChange={(event) => setBulk({ ...bulk, check_out: event.target.value })} />
          <select className="select" style={{ width: 170 }} aria-label="Status" value={bulk.status} onChange={(event) => setBulk({ ...bulk, status: event.target.value })}><option value="">Status from times</option>{["present", "late", "absent", "half_day", "on_leave"].map((item) => <option key={item} value={item}>{humanize(item)}</option>)}</select>
          <input className="input" style={{ flex: 1, minWidth: 200 }} placeholder="Reason (required when replacing records)" value={bulk.reason} onChange={(event) => setBulk({ ...bulk, reason: event.target.value })} />
          <button className="btn btn-primary" onClick={saveBulk}>Apply</button>
          <button className="btn btn-ghost" onClick={() => setSelected([])}>Clear</button>
        </div>}
        <div className="card table-wrap">
          {rows === null ? <Spinner /> : rows.length === 0 ? <Empty title="No employees match" body="Try another date, department, or status." /> : (
            <table>
              <thead><tr>
                {canEdit && <th style={{ width: 36 }}><input type="checkbox" aria-label="Select all" checked={allSelected} onChange={(event) => setSelected(event.target.checked ? rows.map((row) => row.employee_id) : [])} /></th>}
                <th>Employee</th><th>Status</th><th>In</th><th>Out</th><th className="num">Late</th><th className="num">Left early</th><th className="num">Hours</th><th className="num">Overtime</th>
              </tr></thead>
              <tbody>
                {rows.map((row) => <tr key={row.employee_id} className={canEdit ? "clickable" : ""} title={canEdit ? "Edit attendance" : undefined} onClick={() => canEdit && setEdit({ employee_id: row.employee_id, full_name: row.full_name, date, check_in: row.check_in_time || "", check_out: row.check_out_time || "", status: row.projected ? "" : row.status, notes: row.notes || "", reason: "", shift_slot: row.shift_slot || 1, existing: !row.projected })}>
                  {canEdit && <td onClick={(event) => event.stopPropagation()}><input type="checkbox" aria-label={`Select ${row.full_name}`} checked={selected.includes(row.employee_id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, row.employee_id] : current.filter((item) => item !== row.employee_id))} /></td>}
                  <td><strong>{row.full_name}</strong><span className="subtle" style={{ display: "block" }}>{row.employee_code} · {row.department || "No department"}</span></td>
                  <td><Badge value={row.status} /></td>
                  <td>{row.check_in_time?.slice(0, 5) || "—"}</td>
                  <td>{row.check_out_time?.slice(0, 5) || "—"}</td>
                  <td className="num">{row.late_minutes ? `${row.late_minutes} min` : "—"}</td>
                  <td className="num">{row.early_departure_minutes ? `${row.early_departure_minutes} min` : "—"}</td>
                  <td className="num">{Number(row.working_hours) ? Number(row.working_hours).toFixed(2) : "—"}</td>
                  <td className="num">{Number(row.overtime_hours) ? `${Number(row.overtime_hours).toFixed(2)} h` : "—"}</td>
                </tr>)}
              </tbody>
            </table>
          )}
        </div>
        <Pager page={page} count={count} onPage={setPage} />
      </>}

      {tab === "grid" && <div className="card">
        <div className="filters" style={{ marginBottom: 12 }}>{LEGEND.map((item) => <span key={item} className="filters" style={{ gap: 6 }}><span className={`cell ${item}`}>{item.slice(0, 1).toUpperCase()}</span><span className="subtle">{humanize(item)}</span></span>)}</div>
        {grid === null ? <Spinner /> : grid.results.length === 0 ? <Empty title="No employees in this view" /> : <div className="grid-scroll"><table className="mini-grid"><thead><tr><th>Employee</th>{grid.days.map((day) => <th key={day} style={{ color: [0, 6].includes(dayjs(day).day()) ? "var(--text-3)" : undefined }}>{Number(day.slice(-2))}</th>)}</tr></thead><tbody>{grid.results.map((employee) => <tr key={employee.employee_id}><td style={{ paddingRight: 8, whiteSpace: "nowrap" }}>{employee.full_name}</td>{employee.cells.map((cell) => <td key={cell.date}><div className={`cell ${cell.status}`} title={`${dayjs(cell.date).format("ddd D MMM")}: ${humanize(cell.status)}${cell.late_minutes ? `, ${cell.late_minutes} min late` : ""}`}>{cell.status === "unmarked" ? "" : cell.status.slice(0, 1).toUpperCase()}</div></td>)}</tr>)}</tbody></table></div>}
      </div>}

      {tab === "import" && canImport && <div className="grid-2">
        <article className="card">
          <h2><FileSpreadsheet size={17} style={{ verticalAlign: -3 }} /> Import from Excel</h2>
          <p className="muted">Use the template's columns: employee_code, date, check_in, check_out, status, notes, shift_slot, break_minutes, reason. Use shift_slot 2 for a second shift on the same day. Rows that replace an existing record need a reason.</p>
          <div className="filters">
            <button className="btn btn-ghost" onClick={() => download("/exports/attendance-template/", "attendance-import-template.xlsx")}><Download size={15} /> Download template</button>
            <label className="btn btn-primary" style={{ cursor: "pointer" }}><Upload size={15} /> Upload .xlsx<input type="file" accept=".xlsx" hidden onChange={importFile} /></label>
          </div>
          {importResult && <div className={`callout ${importResult.errors.length ? "warn" : ""}`} style={{ marginTop: 14, flexDirection: "column" }}>
            <strong>{importResult.created} created, {importResult.updated} updated, {importResult.errors.length} rejected</strong>
            {importResult.errors.slice(0, 8).map((item, index) => <span key={index}>Row {item.row}: {item.detail}</span>)}
          </div>}
        </article>
        <article className="card">
          <h2><Lock size={17} style={{ verticalAlign: -3 }} /> Close past days</h2>
          <p className="muted">Saves this month's attendance up to and including the selected day as permanent records: absences, weekly offs, holidays, and approved leave. Later edits then need a reason and are kept in the audit trail.</p>
          <button className="btn btn-ghost" onClick={lockDay}>Close {dayjs(date).subtract(1, "day").format("ddd, D MMM")}</button>
          <div className="callout" style={{ marginTop: 16 }}><span>No biometric device is connected. Device punches are refused until a real adapter is installed and a super admin enables it.</span></div>
        </article>
      </div>}

      {edit && <Modal title={`${edit.full_name} · ${dayjs(edit.date).format("ddd, D MMM YYYY")}`} onClose={() => setEdit(null)}>
        <form className="form-grid" onSubmit={saveEdit}>
          <label className="field"><span>Check in</span><input className="input" type="time" value={edit.check_in?.slice(0, 5)} onChange={(event) => setEdit({ ...edit, check_in: event.target.value })} /></label>
          <label className="field"><span>Check out</span><input className="input" type="time" value={edit.check_out?.slice(0, 5)} onChange={(event) => setEdit({ ...edit, check_out: event.target.value })} /></label>
          <label className="field"><span>Status</span><select className="select" value={edit.status || ""} onChange={(event) => setEdit({ ...edit, status: event.target.value })}><option value="">Work out from times</option>{EDIT_STATUSES.map((item) => <option key={item} value={item}>{humanize(item)}</option>)}</select></label>
          <label className="field"><span>Shift</span><select className="select" value={edit.shift_slot} onChange={(event) => setEdit({ ...edit, shift_slot: Number(event.target.value) })}><option value={1}>First shift</option><option value={2}>Second shift</option></select></label>
          <label className="field span-2"><span>Notes</span><textarea className="textarea" value={edit.notes} onChange={(event) => setEdit({ ...edit, notes: event.target.value })} /></label>
          <label className="field span-2"><span>Reason for change</span><textarea className="textarea" value={edit.reason} onChange={(event) => setEdit({ ...edit, reason: event.target.value })} required={edit.existing} /><small>{edit.existing ? "Required. Saved with the before and after values in the audit trail." : "Optional for a new record."}</small></label>
          <div className="modal-actions span-2"><button type="button" className="btn btn-ghost" onClick={() => setEdit(null)}>Cancel</button><button className="btn btn-primary" type="submit">Save attendance</button></div>
        </form>
      </Modal>}
    </div>
  );
}
