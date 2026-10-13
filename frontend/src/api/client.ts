import type { ApiHealth, DashboardSnapshot } from "./contracts";

const configuredBaseUrl = import.meta.env.VITE_VALORIA_API_URL?.trim();
const apiBaseUrl = configuredBaseUrl ? configuredBaseUrl.replace(/\/$/, "") : "";

async function request<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || `Erreur API ${response.status}`;
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  return request<ApiHealth>("/api/v1/health", signal);
}

export function getDashboard(signal?: AbortSignal): Promise<DashboardSnapshot> {
  return request<DashboardSnapshot>("/api/v1/dashboard", signal);
}
