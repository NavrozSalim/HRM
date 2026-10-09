import axios from "axios";

const runtimeApi = typeof window !== "undefined" ? window.__HRM__?.apiUrl : "";
const api = axios.create({
  baseURL: runtimeApi || import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("hrm_access");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing = null;
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry && localStorage.getItem("hrm_refresh")) {
      original._retry = true;
      refreshing = refreshing || axios.post(`${api.defaults.baseURL}/auth/refresh/`, { refresh: localStorage.getItem("hrm_refresh") })
        .then(({ data }) => {
          localStorage.setItem("hrm_access", data.access);
          if (data.refresh) localStorage.setItem("hrm_refresh", data.refresh);
          return data.access;
        })
        .finally(() => { refreshing = null; });
      try {
        const access = await refreshing;
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch {
        localStorage.removeItem("hrm_access");
        localStorage.removeItem("hrm_refresh");
      }
    }
    return Promise.reject(error);
  },
);

export default api;

const fieldLabel = (key) => {
  const text = key.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const flatten = (value) => {
  if (Array.isArray(value)) return value.map(flatten).join(" ");
  if (value && typeof value === "object") return Object.values(value).map(flatten).join(" ");
  return String(value);
};

export function errorText(error) {
  if (!error?.response) return "Cannot reach the server. Check that the API is running and try again.";
  const { status, data } = error.response;
  if (status >= 500) return "The server hit an unexpected error. Try again, and check the API log if it continues.";
  if (!data || typeof data !== "object") return "The request could not be completed.";
  if (typeof data.detail === "string") return data.detail;
  return Object.entries(data)
    .map(([key, value]) => (["non_field_errors", "detail"].includes(key) ? flatten(value) : `${fieldLabel(key)}: ${flatten(value)}`))
    .join(" ");
}

export function fieldErrors(error) {
  const data = error?.response?.data;
  if (!data || typeof data !== "object" || typeof data.detail === "string") return {};
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, flatten(value)]));
}

export async function download(path, filename) {
  const response = await api.get(path, { responseType: "blob" });
  const url = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export const rowsOf = (data) => (Array.isArray(data) ? data : data?.results || []);
