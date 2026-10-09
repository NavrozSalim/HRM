import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { errorText, fieldErrors, rowsOf } from "../api";
import { Spinner, Switch, useToast } from "../ui";

const blank = {
  first_name: "", last_name: "", employee_code: "", phone: "", email: "", address: "",
  emergency_contact_name: "", emergency_contact_phone: "", emergency_contact_relation: "",
  department: "", job_title: "", location: "", employment_type: "full_time", joining_date: "", exit_date: "",
  date_of_birth: "", status: "active", shift: "", salary_type: "monthly", basic_salary: "0", daily_rate: "0", hourly_rate: "0",
  bank_name: "", bank_account_name: "", bank_account_number: "", bank_routing: "", notes: "",
  create_account: false, account_username: "", account_password: "",
};

function Section({ title, description, children }) {
  return (
    <div className="form-section">
      <div><h2>{title}</h2>{description && <p className="muted">{description}</p>}</div>
      <div className="form-grid">{children}</div>
    </div>
  );
}

export default function EmployeeFormPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState(blank);
  const [loaded, setLoaded] = useState(!id);
  const [lists, setLists] = useState({ departments: [], titles: [], shifts: [], locations: [] });
  const [photo, setPhoto] = useState(null);
  const [error, setError] = useState("");
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  useEffect(() => {
    Promise.all([
      api.get("/departments/?page_size=100"),
      api.get("/job-titles/?page_size=200"),
      api.get("/shifts/?page_size=100"),
      api.get("/locations/?page_size=100"),
    ]).then(([departments, titles, shifts, locations]) => setLists({
      departments: rowsOf(departments.data), titles: rowsOf(titles.data), shifts: rowsOf(shifts.data), locations: rowsOf(locations.data),
    }));
    if (id) api.get(`/employees/${id}/`).then(({ data }) => { setForm({ ...blank, ...data, department: data.department || "", job_title: data.job_title || "", location: data.location || "", shift: data.shift || "" }); setLoaded(true); }).catch((err) => { setError(errorText(err)); setLoaded(true); });
  }, [id]);
  async function save(event) {
    event.preventDefault();
    setError("");
    setErrors({});
    setSaving(true);
    const skip = new Set(["photo_url", "full_name", "department_name", "job_title_name", "shift_name", "location_name", "user", "created_at", "updated_at", "id", "weekly_off_days", "photo"]);
    const body = {};
    Object.entries(form).forEach(([key, value]) => {
      if (skip.has(key) || value === null || value === undefined) return;
      if (value === "" && !id) return;
      if (value === "" && ["department", "job_title", "location", "shift", "exit_date", "date_of_birth"].includes(key)) { body[key] = null; return; }
      if (value === "") return;
      body[key] = value;
    });
    if (!body.create_account) { delete body.account_username; delete body.account_password; }
    try {
      let response;
      if (photo) {
        const payload = new FormData();
        Object.entries(body).forEach(([key, value]) => { if (value !== null) payload.append(key, value); });
        payload.append("photo", photo);
        response = id ? await api.patch(`/employees/${id}/`, payload) : await api.post("/employees/", payload);
      } else {
        response = id ? await api.patch(`/employees/${id}/`, body) : await api.post("/employees/", body);
      }
      toast(id ? "Employee updated." : "Employee added.");
      navigate(`/employees/${response.data.id}`);
    } catch (err) {
      setErrors(fieldErrors(err));
      setError(errorText(err));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally { setSaving(false); }
  }
  const input = (label, key, props = {}) => (
    <label className={`field ${props.wide ? "span-2" : ""}`}>
      <span>{label}{props.required && <span style={{ color: "var(--danger)" }}> *</span>}</span>
      <input className="input" type={props.type || "text"} value={form[key] ?? ""} onChange={set(key)} required={props.required} min={props.min} step={props.step} placeholder={props.placeholder} autoComplete="off" />
      {errors[key] ? <small style={{ color: "var(--danger)" }}>{errors[key]}</small> : props.hint && <small>{props.hint}</small>}
    </label>
  );
  const select = (label, key, options, empty) => (
    <label className="field">
      <span>{label}</span>
      <select className="select" value={form[key] ?? ""} onChange={set(key)}>{empty && <option value="">{empty}</option>}{options.map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select>
      {errors[key] && <small style={{ color: "var(--danger)" }}>{errors[key]}</small>}
    </label>
  );
  if (!loaded) return <div className="page"><Spinner label="Loading employee…" /></div>;
  return (
    <form className="page" onSubmit={save}>
      <div className="page-head">
        <div><p className="eyebrow">People</p><h1>{id ? `Edit ${form.first_name} ${form.last_name}` : "Add employee"}</h1><p className="muted">Fields marked * are required. Salary changes are recorded in the employment timeline.</p></div>
        <div className="filters"><button type="button" className="btn btn-ghost" onClick={() => navigate(id ? `/employees/${id}` : "/employees")}>Cancel</button><button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "Saving…" : id ? "Save changes" : "Add employee"}</button></div>
      </div>
      {error && <div className="callout error">{error}</div>}
      <div className="card">
        <Section title="Personal details" description="Name, contact information, and emergency contact.">
          {input("First name", "first_name", { required: true })}
          {input("Last name", "last_name", { required: true })}
          {input("Email", "email", { type: "email" })}
          {input("Phone", "phone", { type: "tel" })}
          {input("Date of birth", "date_of_birth", { type: "date" })}
          <label className="field"><span>Profile photo</span><input className="input" type="file" accept="image/*" onChange={(event) => setPhoto(event.target.files?.[0] || null)} /></label>
          <label className="field span-2"><span>Residential address</span><textarea className="textarea" value={form.address || ""} onChange={set("address")} /></label>
          {input("Emergency contact", "emergency_contact_name")}
          {input("Relationship", "emergency_contact_relation")}
          {input("Emergency phone", "emergency_contact_phone", { type: "tel" })}
        </Section>
        <Section title="Employment" description="Where this person works and on which schedule.">
          {input("Employee ID", "employee_code", { hint: id ? undefined : "Leave blank to generate the next ID." })}
          {select("Status", "status", [["active", "Active"], ["on_notice", "On notice"], ["inactive", "Inactive"], ["terminated", "Terminated"]])}
          {select("Department", "department", lists.departments.map((item) => [item.id, item.name]), "Unassigned")}
          {select("Job title", "job_title", lists.titles.map((item) => [item.id, item.name]), "Unassigned")}
          {select("Location", "location", lists.locations.map((item) => [item.id, item.name]), "Unassigned")}
          {select("Shift", "shift", lists.shifts.map((item) => [item.id, `${item.name} (${item.start_time?.slice(0, 5)}–${item.end_time?.slice(0, 5)})`]), "Office default, 09:00–17:00")}
          {select("Employment type", "employment_type", [["full_time", "Full time"], ["part_time", "Part time"], ["contract", "Contract"], ["intern", "Intern"], ["daily_wage", "Daily wage"], ["hourly", "Hourly"]])}
          <div />
          {input("Joining date", "joining_date", { type: "date", required: true })}
          {input("Exit date", "exit_date", { type: "date" })}
        </Section>
        <Section title="Pay" description="Only the rate that matches the salary type is used in payroll.">
          {select("Salary type", "salary_type", [["monthly", "Fixed monthly"], ["daily", "Daily wage"], ["hourly", "Hourly wage"]])}
          {form.salary_type === "monthly" && input("Basic monthly salary", "basic_salary", { type: "number", min: "0", step: "0.01" })}
          {form.salary_type === "daily" && input("Daily rate", "daily_rate", { type: "number", min: "0", step: "0.01" })}
          {form.salary_type === "hourly" && input("Hourly rate", "hourly_rate", { type: "number", min: "0", step: "0.01" })}
          {input("Bank name", "bank_name")}
          {input("Account holder", "bank_account_name")}
          {input("Account number", "bank_account_number", { hint: "Shown masked everywhere except this form." })}
          {input("Routing or branch code", "bank_routing")}
        </Section>
        <Section title="Notes">
          <label className="field span-2"><span>Internal notes</span><textarea className="textarea" value={form.notes || ""} onChange={set("notes")} /></label>
        </Section>
        {!id && <Section title="Sign-in" description="Optionally give this employee their own login to check in and request leave.">
          <div className="span-2"><Switch checked={!!form.create_account} onChange={(value) => setForm({ ...form, create_account: value })} label="Create a login for this employee" description="They sign in with the employee role and can only see their own records." /></div>
          {form.create_account && input("Username", "account_username", { required: true })}
          {form.create_account && input("Temporary password", "account_password", { type: "password", required: true, hint: "At least 8 characters. Share it privately." })}
        </Section>}
      </div>
      <div className="filters" style={{ justifyContent: "flex-end" }}><button type="button" className="btn btn-ghost" onClick={() => navigate(id ? `/employees/${id}` : "/employees")}>Cancel</button><button className="btn btn-primary" type="submit" disabled={saving}>{saving ? "Saving…" : id ? "Save changes" : "Add employee"}</button></div>
    </form>
  );
}
