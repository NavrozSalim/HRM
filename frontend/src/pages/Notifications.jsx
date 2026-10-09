import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import { Bell, CheckCheck } from "lucide-react";
import api, { errorText, rowsOf } from "../api";
import { Empty, Spinner, useToast } from "../ui";

dayjs.extend(relativeTime);

export default function NotificationsPage() {
  const [items, setItems] = useState(null);
  const navigate = useNavigate();
  const toast = useToast();
  const load = () => api.get("/notifications/").then(({ data }) => setItems(rowsOf(data))).catch((err) => { setItems([]); toast(errorText(err), "bad"); });
  useEffect(() => { load(); }, []);
  async function markRead(ids) {
    try { await api.post("/notifications/read/", ids ? { ids } : { all: true }); load(); window.dispatchEvent(new Event("hrm:notifications")); } catch (err) { toast(errorText(err), "bad"); }
  }
  async function open(item) {
    if (!item.is_read) await markRead([item.id]);
    if (item.link) navigate(item.link);
  }
  const unread = items?.filter((item) => !item.is_read).length || 0;
  return (
    <div className="page">
      <div className="page-head">
        <div><p className="eyebrow">Account</p><h1>Notifications</h1><p className="muted">{unread ? `${unread} unread` : "You're all caught up."}</p></div>
        {unread > 0 && <button className="btn btn-ghost" onClick={() => markRead()}><CheckCheck size={15} /> Mark all as read</button>}
      </div>
      <div className="card" style={{ padding: 0 }}>
        {items === null ? <Spinner /> : items.length === 0 ? <Empty title="No notifications" body="Leave decisions, payroll updates, and reminders appear here." /> : items.map((item) => (
          <div key={item.id} className="notif-row" style={{ display: "flex", gap: 12, padding: "14px 18px", borderBottom: "1px solid var(--border)", background: item.is_read ? undefined : "var(--brand-soft)" }}>
            <span className="icon-pill"><Bell size={15} /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <strong style={{ fontWeight: item.is_read ? 550 : 700 }}>{item.title}</strong>
              <p style={{ margin: "2px 0 4px" }} className="muted">{item.body}</p>
              <span className="subtle" title={dayjs(item.created_at).format("D MMM YYYY, HH:mm")}>{dayjs(item.created_at).fromNow()}</span>
            </div>
            <div className="filters" style={{ alignSelf: "center", flexWrap: "nowrap" }}>
              {item.link && <button className="btn btn-ghost btn-sm" onClick={() => open(item)}>Open</button>}
              {!item.is_read && <button className="btn btn-ghost btn-sm" onClick={() => markRead([item.id])}>Mark read</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
