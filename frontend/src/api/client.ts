import { invoke } from "@tauri-apps/api/core";

import type { AccountsSnapshot, ApiHealth, AuthSession, AuthStatus, BudgetsSnapshot, DashboardSnapshot, ForecastSnapshot, ReconciliationActionResult, ReconciliationSnapshot, TransactionsSnapshot } from "./contracts";

const configuredBaseUrl = import.meta.env.VITE_VALORIA_API_URL?.trim();
interface ApiConnection {
  baseUrl: string;
  bootstrapSecret: string;
}

let resolvedConnection: Promise<ApiConnection> | undefined;

async function apiConnection(): Promise<ApiConnection> {
  if (configuredBaseUrl) {
    return { baseUrl: configuredBaseUrl.replace(/\/$/, ""), bootstrapSecret: "" };
  }
  resolvedConnection ??= Promise.all([
    invoke<string>("local_api_origin"),
    invoke<string>("local_api_bootstrap_secret"),
  ])
    .then(([baseUrl, bootstrapSecret]) => ({ baseUrl, bootstrapSecret }))
    .catch(() => ({ baseUrl: "", bootstrapSecret: "" }));
  return resolvedConnection;
}

async function request<T>(
  path: string,
  options: { method?: "GET" | "POST"; body?: unknown; token?: string; signal?: AbortSignal } = {},
): Promise<T> {
  const connection = await apiConnection();
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (connection.bootstrapSecret) headers["X-Valoria-Bootstrap"] = connection.bootstrapSecret;
  if (options.token) headers["X-Valoria-Session"] = options.token;

  const response = await fetch(`${connection.baseUrl}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = payload?.detail || `Erreur API ${response.status}`;
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  return request<ApiHealth>("/api/v1/health", { signal });
}

export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return request<AuthStatus>("/api/v1/auth/status", { signal });
}

export function openSession(password: string, configured: boolean): Promise<AuthSession> {
  return request<AuthSession>(configured ? "/api/v1/auth/unlock" : "/api/v1/auth/setup", {
    method: "POST",
    body: { password },
  });
}

export function closeSession(token: string): Promise<{ locked: boolean }> {
  return request<{ locked: boolean }>("/api/v1/auth/lock", { method: "POST", token });
}

export function getDashboard(token: string, signal?: AbortSignal): Promise<DashboardSnapshot> {
  return request<DashboardSnapshot>("/api/v1/dashboard", { token, signal });
}

export function getAccounts(token: string, signal?: AbortSignal): Promise<AccountsSnapshot> {
  return request<AccountsSnapshot>("/api/v1/accounts", { token, signal });
}

export function getTransactions(token: string, signal?: AbortSignal): Promise<TransactionsSnapshot> {
  return request<TransactionsSnapshot>("/api/v1/transactions", { token, signal });
}

export function getForecast(
  token: string,
  filters: { accountId: string; horizonDays: number; scenario: string },
  signal?: AbortSignal,
): Promise<ForecastSnapshot> {
  const query = new URLSearchParams({
    horizon_days: String(filters.horizonDays),
    scenario: filters.scenario,
  });
  if (filters.accountId !== "all") query.set("account_id", filters.accountId);
  return request<ForecastSnapshot>(`/api/v1/forecast?${query.toString()}`, { token, signal });
}

export function getBudgets(token: string, month: string, signal?: AbortSignal): Promise<BudgetsSnapshot> {
  const query = new URLSearchParams();
  if (month) query.set("month", month);
  const encoded = query.toString();
  const suffix = encoded ? `?${encoded}` : "";
  return request<BudgetsSnapshot>(`/api/v1/budgets${suffix}`, { token, signal });
}

export function getReconciliation(
  token: string,
  filters: { accountId: string; status: string },
  signal?: AbortSignal,
): Promise<ReconciliationSnapshot> {
  const query = new URLSearchParams({ status: filters.status });
  if (filters.accountId !== "all") query.set("account_id", filters.accountId);
  return request<ReconciliationSnapshot>(`/api/v1/reconciliation?${query.toString()}`, { token, signal });
}

export function confirmReconciliationProposal(token: string, proposalId: number): Promise<ReconciliationActionResult> {
  return request<ReconciliationActionResult>(`/api/v1/reconciliation/proposals/${proposalId}/confirm`, {
    method: "POST",
    token,
  });
}

export function rejectReconciliationProposal(token: string, proposalId: number): Promise<ReconciliationActionResult> {
  return request<ReconciliationActionResult>(`/api/v1/reconciliation/proposals/${proposalId}/reject`, {
    method: "POST",
    token,
  });
}

export function confirmManualReconciliation(
  token: string,
  payload: { occurrenceId: number; transactionId: number; includeOverage: boolean },
): Promise<ReconciliationActionResult> {
  return request<ReconciliationActionResult>("/api/v1/reconciliation/manual-match", {
    method: "POST",
    token,
    body: {
      occurrence_id: payload.occurrenceId,
      transaction_id: payload.transactionId,
      include_overage: payload.includeOverage,
    },
  });
}
