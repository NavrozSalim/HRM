import { useEffect, useState } from "react";
import dayjs from "dayjs";
import { AlertTriangle, Calculator, CheckCircle2, Download, FileText, Lock, Plus, RotateCcw } from "lucide-react";
import api, { download, errorText, rowsOf } from "../api";
import { useAuth } from "../auth";
import { Badge, Empty, Modal, Spinner, money, useToast } from "../ui";

const STEPS = [
  { value: "calculated", label: "Calculate" },
  { value: "approved", label: "Approve" },
  { value: "finalized", label: "Finalize" },
];
const blankExtra = () => ({ kind: "bonus", employee: "", amount: "", label: "", reason: "", issued_date: dayjs().format("YYYY-MM-DD"), monthly_recovery: "" });

function periodName(period) {
  return dayjs(`${period.year}-${String(period.month).padStart(2, "0")}-01`).format("MMMM YYYY");
}

export default function PayrollPage() {
  const { user } = useAuth();
  const toast = useToast();
  const canManage = user.capabilities.manage_payroll;
  const [periods, setPeriods] = useState(null);
  const [periodId, setPeriodId] = useState("");
  const [records, setRecords] = useState(null);
  const [active, setActive] = useState(null);
  const [pay, setPay] = useState(null);
  const [adjust, setAdjust] = useState(null);
  const [reopen, setReopen] = useState(false);
  const [reason, setReason] = useState("");
  const [opening, setOpening] = useState(false);
  const [month, setMonth] = useState(dayjs().format("YYYY-MM"));
  const [extra, setExtra] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [busy, setBusy] = useState(false);

  function loadPeriods(select) {
    api.get("/payroll/periods/?page_size=24").then(({ data }) => {
      const items = rowsOf(data);
      setPeriods(items);
      if (select) setPeriodId(String(select));
      else if (!periodId && items[0]) setPeriodId(String(items[0].id));
    }).catch((err) => { setPeriods([]); toast(errorText(err), "bad"); });
  }
  function loadRecords() {
    if (!periodId) return;
    api.get(`/payroll/records/?period=${periodId}&page_size=200`).then(({ data }) => setRecords(rowsOf(data))).catch(() => setRecords([]));
  }
  useEffect(() => { loadPeriods(); if (canManage) api.get("/employees/?page_size=200").then(({ data }) => setEmployees(rowsOf(data))); }, []);
  useEffect(() => { setRecords(null); loadRecords(); }, [periodId]);
  const period = periods?.find((item) => String(item.id) === String(periodId));

  async function run(action, body, message) {
    setBusy(true);
    try {
      await api.post(`/payroll/periods/${periodId}/${action}/`, body || {});
      toast(message);
      loadPeriods();
      loadRecords();
      return true;
    } catch (err) { toast(errorText(err), "bad"); return false; } finally { setBusy(false); }
  }
  async function openMonth(event) {
    event.preventDefault();
    const [year, monthNumber] = month.split("-");
    try {
      const { data } = await api.post("/payroll/periods/", { year: Number(year), month: Number(monthNumber) });
      toast("Payroll month opened. Calculate it to build the preview.");
      setOpening(false);
      loadPeriods(data.id);
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function saveExtra(event) {
    event.preventDefault();
    const [year, monthNumber] = month.split("-");
    const target = period ? { year: period.year, month: period.month } : { year: Number(year), month: Number(monthNumber) };
    const path = extra.kind === "advance" ? "/payroll/advances/" : extra.kind === "deduction" ? "/payroll/deductions/" : "/payroll/bonuses/";
    const label = extra.label || (extra.kind === "deduction" ? "Deduction" : "Bonus");
    const payload = extra.kind === "advance"
      ? { employee: extra.employee, amount: extra.amount, issued_date: extra.issued_date, monthly_recovery: extra.monthly_recovery || null, reason: extra.reason }
      : { employee: extra.employee, ...target, label, amount: extra.amount, reason: extra.reason };
    try {
      await api.post(path, payload);
      toast("Saved. Recalculate this payroll month to include it.");
      setExtra(null);
      loadPeriods();
    } catch (err) { toast(errorText(err), "bad"); }
  }
  async function submitForm(event, path, message, close) {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(event.target).entries());
    try {
      await api.post(path, body);
      toast(message);
      close();
      loadPeriods();
      loadRecords();
    } catch (err) { toast(errorText(err), "bad"); }
  }

  const status = period?.status;
  const stepIndex = { open: -1, reopened: -1, calculated: 0, approved: 1, finalized: 2 }[status] ?? -1;
  const locked = status === "finalized";

  if (periods === null) return <div className="page"><Spinner label="Loading payroll…" /></div>;

  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Finance</p><h1>Payroll</h1><p className="muted">Every amount is calculated on the server from attendance, leave, and your salary policies.</p></div>
        <div className="filters">
          {periods.length > 0 && <select className="select" style={{ width: 210 }} aria-label="Payroll month" value={periodId} onChange={(event) => setPeriodId(event.target.value)}>{periods.map((item) => <option key={item.id} value={item.id}>{periodName(item)}</option>)}</select>}
          {canManage && <button className="btn btn-primary" onClick={() => setOpening(true)}><Plus size={15} /> Open month</button>}
        </div>
      </div>

      {periods.length === 0 && <div className="card"><Empty title="No payroll months yet" body={canManage ? "Open a month to calculate salaries from attendance and leave." : "Payroll has not been prepared yet."} action={canManage && <button className="btn btn-primary" onClick={() => setOpening(true)}>Open month</button>} /></div>}

      {period && <>
        <div className="card">
          <div className="toolbar">
            <div>
              <h2 style={{ margin: 0 }}>{periodName(period)} <Badge value={period.status} /></h2>
              <p className="subtle" style={{ margin: "4px 0 0" }}>
                {period.finalized_at ? `Finalized ${dayjs(period.finalized_at).format("D MMM YYYY, HH:mm")}` : period.calculated_at ? `Last calculated ${dayjs(period.calculated_at).format("D MMM YYYY, HH:mm")}` : "Not calculated yet"}
                {period.divisor_mode && ` · Daily rate divides by ${period.divisor_mode.replaceAll("_", " ")}`}
              </p>
            </div>
            <div className="filters">
              {user.capabilities.view_payroll && <button className="btn btn-ghost" onClick={() => download(`/exports/payroll/?period=${periodId}&format=xlsx`, `payroll-${period.year}-${period.month}.xlsx`)}><Download size={15} /> Excel</button>}
              {user.capabilities.view_payroll && <button className="btn btn-ghost" onClick={() => download(`/exports/payroll/?period=${periodId}&format=pdf`, `payroll-${period.year}-${period.month}.pdf`)}><FileText size={15} /> PDF</button>}
            </div>
          </div>

          <div className="steps" style={{ marginTop: 16 }}>
            {STEPS.map((step, index) => <div key={step.value} className={`step ${index <= stepIndex ? "done" : ""} ${index === stepIndex + 1 ? "next" : ""}`}><span>{index + 1}</span>{step.label}</div>)}
          </div>

          {period.needs_recalculation && !locked && <div className="callout warn" style={{ marginTop: 14 }}><AlertTriangle size={16} /><span>Attendance, leave, or pay items changed after the last calculation. Recalculate before approving.</span></div>}
          {status === "reopened" && period.reopen_reason && <div className="callout" style={{ marginTop: 14 }}><RotateCcw size={16} /><span>Reopened: {period.reopen_reason}</span></div>}
          {locked && <div className="callout" style={{ marginTop: 14 }}><Lock size={16} /><span>This payroll is finalized and locked. Record payments below, or reopen it with a reason to make changes.</span></div>}

          {canManage && <div className="filters" style={{ marginTop: 14 }}>
            {!locked && <button className="btn btn-primary" disabled={busy} onClick={() => run("calculate", null, "Payroll calculated.")}><Calculator size={15} /> {period.calculated_at ? "Recalculate" : "Calculate"}</button>}
            {status === "calculated" && <button className="btn btn-primary" disabled={busy || period.needs_recalculation} onClick={() => run("approve", null, "Payroll approved.")}><CheckCircle2 size={15} /> Approve</button>}
            {status === "approved" && <button className="btn btn-primary" disabled={busy || period.needs_recalculation} onClick={() => run("finalize", null, "Payroll finalized and locked.")}><Lock size={15} /> Finalize</button>}
            {locked && <button className="btn btn-ghost" onClick={() => { setReason(""); setReopen(true); }}><RotateCcw size={15} /> Reopen</button>}
            {!locked && <button className="btn btn-ghost" onClick={() => setExtra(blankExtra())}><Plus size={15} /> Bonus, deduction, or advance</button>}
          </div>}
        </div>

        <div className="stat-grid">
          <article className="card stat"><span>Employees</span><strong>{period.employee_count}</strong></article>
          <article className="card stat"><span>Net payroll</span><strong>{money(period.total_net)}</strong></article>
          <article className="card stat"><span>Still to pay</span><strong>{money(period.total_unpaid)}</strong><small>{locked ? "After finalization" : "Shown once finalized"}</small></article>
        </div>

        <div className="card table-wrap">
          {records === null ? <Spinner /> : records.length === 0 ? <Empty title="No salary records" body={canManage ? "Calculate this month to build salary records." : "Nothing has been calculated for this month yet."} /> : (
            <table>
              <thead><tr><th>Employee</th><th className="num">Present</th><th className="num">Absent</th><th className="num">Unpaid leave</th><th className="num">Gross</th><th className="num">Deductions</th><th className="num">Net</th><th>Payment</th><th /></tr></thead>
              <tbody>{records.map((row) => (
                <tr key={row.id}>
                  <td><strong>{row.employee_name}</strong><span className="subtle" style={{ display: "block" }}>{row.employee_code} · {row.department || "No department"}</span></td>
                  <td className="num">{Number(row.present_days)}</td>
                  <td className="num">{Number(row.absent_days)}</td>
                  <td className="num">{Number(row.unpaid_leave_days)}</td>
                  <td className="num">{money(row.gross_salary)}</td>
                  <td className="num">{money(row.total_deductions)}</td>
                  <td className="num"><strong>{money(row.net_salary)}</strong></td>
                  <td>{locked ? <Badge value={row.payment_status} /> : <span className="subtle">After finalization</span>}</td>
                  <td className="num"><div className="filters" style={{ justifyContent: "flex-end", flexWrap: "nowrap" }}>
                    <button className="btn btn-ghost btn-sm" onClick={() => setActive(row)}>Details</button>
                    {canManage && !locked && <button className="btn btn-ghost btn-sm" onClick={() => setAdjust(row)}>Adjust</button>}
                    {canManage && locked && row.payment_status !== "paid" && <button className="btn btn-primary btn-sm" onClick={() => setPay(row)}>Pay</button>}
                    <button className="btn btn-ghost btn-sm" title="Download salary slip" onClick={() => download(`/payroll/records/${row.id}/slip/?format=pdf`, `slip-${row.employee_code}-${row.period_label}.pdf`)}><FileText size={14} /> Slip</button>
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </>}

      {opening && <Modal title="Open payroll month" onClose={() => setOpening(false)}>
        <form onSubmit={openMonth} style={{ display: "grid", gap: 14 }}>
          <label className="field"><span>Month</span><input className="input" type="month" value={month} onChange={(event) => setMonth(event.target.value)} required /></label>
          <div className="modal-actions"><button type="button" className="btn btn-ghost" onClick={() => setOpening(false)}>Cancel</button><button className="btn btn-primary">Open month</button></div>
        </form>
      </Modal>}

      {active && <Modal title={`${active.employee_name} · ${active.period_label}`} onClose={() => setActive(null)}>
        <div className="kv" style={{ marginBottom: 12 }}>
          <div><dt>Scheduled days</dt><dd>{Number(active.scheduled_working_days)}</dd></div>
          <div><dt>Paid leave</dt><dd>{Number(active.paid_leave_days)}</dd></div>
          <div><dt>Weekly offs / holidays</dt><dd>{Number(active.weekly_offs)} / {Number(active.public_holidays)}</dd></div>
          <div><dt>Late arrivals</dt><dd>{active.late_count} ({active.late_minutes} min)</dd></div>
          <div><dt>Hours worked</dt><dd>{Number(active.working_hours)}</dd></div>
          <div><dt>Overtime</dt><dd>{Number(active.overtime_hours)} h</dd></div>
        </div>
        <div className="list">
          {(active.lines || []).map((line) => <div key={line.id || line.label} className="list-row"><span>{line.label}{line.manual && <span className="subtle">Manual adjustment{line.reason ? ` · ${line.reason}` : ""}</span>}</span><strong style={{ color: line.kind === "deduction" ? "var(--danger)" : undefined }}>{line.kind === "deduction" ? "−" : ""}{money(line.amount)}</strong></div>)}
          <div className="list-row"><span><strong>Net salary</strong></span><strong>{money(active.net_salary)}</strong></div>
        </div>
        {(active.breakdown?.warnings || []).map((warning) => <div key={warning} className="callout warn" style={{ marginTop: 10 }}><AlertTriangle size={16} /><span>{warning}</span></div>)}
        {(active.breakdown?.formula || []).length > 0 && <details style={{ marginTop: 12 }}><summary className="subtle" style={{ cursor: "pointer" }}>How this was calculated</summary>{active.breakdown.formula.map((line) => <p key={line} className="subtle" style={{ margin: "6px 0" }}>{line}</p>)}</details>}
      </Modal>}

      {adjust && <Modal title={`Adjust ${adjust.employee_name}`} onClose={() => setAdjust(null)}>
        <form className="form-grid" onSubmit={(event) => submitForm(event, `/payroll/records/${adjust.id}/adjust/`, "Adjustment saved and recorded in the audit log.", () => setAdjust(null))}>
          <label className="field"><span>Type</span><select className="select" name="kind"><option value="earning">Add to pay</option><option value="deduction">Deduct from pay</option></select></label>
          <label className="field"><span>Amount</span><input className="input" name="amount" type="number" min="0.01" step="0.01" required /></label>
          <label className="field span-2"><span>Label on the salary slip</span><input className="input" name="label" placeholder="For example, Travel reimbursement" required /></label>
          <label className="field span-2"><span>Reason</span><textarea className="textarea" name="reason" required /><small>Stored in the audit log.</small></label>
          <div className="modal-actions span-2"><button type="button" className="btn btn-ghost" onClick={() => setAdjust(null)}>Cancel</button><button className="btn btn-primary">Save adjustment</button></div>
        </form>
      </Modal>}

      {pay && <Modal title={`Record payment · ${pay.employee_name}`} onClose={() => setPay(null)}>
        <p className="muted">Net {money(pay.net_salary)} · already paid {money(pay.amount_paid)}</p>
        <form className="form-grid" onSubmit={(event) => submitForm(event, `/payroll/records/${pay.id}/pay/`, "Payment recorded.", () => setPay(null))}>
          <label className="field"><span>Amount</span><input className="input" name="amount" type="number" min="0.01" step="0.01" defaultValue={(Number(pay.net_salary) - Number(pay.amount_paid)).toFixed(2)} required /></label>
          <label className="field"><span>Paid on</span><input className="input" type="date" name="paid_on" defaultValue={dayjs().format("YYYY-MM-DD")} required /></label>
          <label className="field"><span>Method</span><select className="select" name="method"><option value="bank">Bank transfer</option><option value="cash">Cash</option><option value="cheque">Cheque</option></select></label>
          <label className="field"><span>Reference</span><input className="input" name="reference" placeholder="Optional" /></label>
          <div className="modal-actions span-2"><button type="button" className="btn btn-ghost" onClick={() => setPay(null)}>Cancel</button><button className="btn btn-primary">Record payment</button></div>
        </form>
      </Modal>}

      {reopen && <Modal title={`Reopen ${periodName(period)}`} onClose={() => setReopen(false)}>
        <p className="muted">Reopening unlocks this payroll for corrections. The reason is saved in the audit log, and the month must be approved and finalized again.</p>
        <label className="field"><span>Reason</span><textarea className="textarea" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <div className="modal-actions" style={{ marginTop: 14 }}>
          <button className="btn btn-ghost" onClick={() => setReopen(false)}>Cancel</button>
          <button className="btn btn-danger" disabled={reason.trim().length < 3 || busy} onClick={async () => { if (await run("reopen", { reason }, "Payroll reopened.")) setReopen(false); }}>Reopen payroll</button>
        </div>
      </Modal>}

      {extra && <Modal title="Add a pay item" onClose={() => setExtra(null)}>
        <form className="form-grid" onSubmit={saveExtra}>
          <label className="field"><span>Type</span><select className="select" value={extra.kind} onChange={(event) => setExtra({ ...extra, kind: event.target.value })}><option value="bonus">Bonus</option><option value="deduction">Approved deduction</option><option value="advance">Salary advance</option></select></label>
          <label className="field"><span>Employee</span><select className="select" value={extra.employee} onChange={(event) => setExtra({ ...extra, employee: event.target.value })} required><option value="">Choose…</option>{employees.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select></label>
          {extra.kind !== "advance" && <label className="field span-2"><span>Label</span><input className="input" placeholder={extra.kind === "deduction" ? "Deduction" : "Bonus"} value={extra.label} onChange={(event) => setExtra({ ...extra, label: event.target.value })} /><small>Applies to {period ? periodName(period) : "the selected month"}.</small></label>}
          <label className="field"><span>Amount</span><input className="input" type="number" min="0.01" step="0.01" value={extra.amount} onChange={(event) => setExtra({ ...extra, amount: event.target.value })} required /></label>
          {extra.kind === "advance" && <label className="field"><span>Issued on</span><input className="input" type="date" value={extra.issued_date} onChange={(event) => setExtra({ ...extra, issued_date: event.target.value })} required /></label>}
          {extra.kind === "advance" && <label className="field"><span>Recover per month</span><input className="input" type="number" min="0.01" step="0.01" placeholder="Whole amount" value={extra.monthly_recovery} onChange={(event) => setExtra({ ...extra, monthly_recovery: event.target.value })} /></label>}
          <label className="field span-2"><span>Reason</span><textarea className="textarea" value={extra.reason} onChange={(event) => setExtra({ ...extra, reason: event.target.value })} /></label>
          <div className="modal-actions span-2"><button type="button" className="btn btn-ghost" onClick={() => setExtra(null)}>Cancel</button><button className="btn btn-primary">Save</button></div>
        </form>
      </Modal>}
    </div>
  );
}
