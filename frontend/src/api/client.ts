import { invoke } from "@tauri-apps/api/core";

import type { AccountActionResult, AccountPayload, AccountsSnapshot, ApiHealth, AssetsSnapshot, AuthSession, AuthStatus, BankImportCancelResult, BankImportHistory, BankImportPreview, BankImportResult, BudgetsSnapshot, DashboardSnapshot, ForecastSnapshot, OccurrenceRescheduleResult, RecurrenceActionResult, RecurrencePayload, ReschedulableOccurrencesResult, ReconciliationActionResult, ScenarioActionResult, ScenarioEventPayload, ScenarioPayload, ScenarioSettingsSnapshot, ReconciliationSnapshot, SettingsActionResult, SettingsCategoryPayload, SettingsRulePayload, SettingsRulesPreview, SettingsSnapshot, TransactionActionResult, TransactionBulkResult, TransactionEditPayload, TransactionsSnapshot } from "./contracts";

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
  options: { method?: "GET" | "POST" | "PUT" | "DELETE"; body?: unknown; token?: string; signal?: AbortSignal } = {},
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

function accountBody(payload: AccountPayload) {
  return {
    name: payload.name,
    bank: payload.bank,
    account_type: payload.type,
    identifier: payload.identifier,
    initial_balance: payload.initialBalance,
    initial_date: payload.initialDate,
    currency: payload.currency,
    status: payload.status,
  };
}

export function createAccount(token: string, payload: AccountPayload): Promise<AccountActionResult> {
  return request<AccountActionResult>("/api/v1/accounts", {
    method: "POST",
    token,
    body: accountBody(payload),
  });
}

export function updateAccount(token: string, accountId: number, payload: AccountPayload): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/v1/accounts/${accountId}`, {
    method: "POST",
    token,
    body: accountBody(payload),
  });
}

export function updateAccountReference(
  token: string,
  accountId: number,
  initialBalance: number,
  initialDate: string,
): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/v1/accounts/${accountId}/reference`, {
    method: "POST",
    token,
    body: { initial_balance: initialBalance, initial_date: initialDate },
  });
}

export function getTransactions(token: string, signal?: AbortSignal): Promise<TransactionsSnapshot> {
  return request<TransactionsSnapshot>("/api/v1/transactions", { token, signal });
}

export function updateTransaction(
  token: string,
  transactionId: number,
  payload: TransactionEditPayload,
): Promise<TransactionActionResult> {
  return request<TransactionActionResult>(`/api/v1/transactions/${transactionId}`, {
    method: "POST",
    token,
    body: {
      account_id: payload.accountId,
      tx_date: payload.date,
      label: payload.label,
      category: payload.category || null,
      direction: payload.direction,
      amount: payload.amount,
      status: payload.status,
    },
  });
}

export function createTransactionCategorizationRule(
  token: string,
  transactionId: number,
  targetCategoryId: number,
  matchValue: string,
): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/transactions/${transactionId}/categorization-rule`, {
    method: "POST",
    token,
    body: { target_category_id: targetCategoryId, match_value: matchValue },
  });
}

export function bulkUpdateTransactions(
  token: string,
  transactionIds: number[],
  action: "category" | "validate",
  category?: string,
): Promise<TransactionBulkResult> {
  return request<TransactionBulkResult>("/api/v1/transactions/actions/bulk", {
    method: "POST",
    token,
    body: {
      transaction_ids: transactionIds,
      action,
      category: category || null,
    },
  });
}

export function previewBankImport(
  token: string,
  payload: { fileName: string; contentBase64: string; accountId: number | null },
): Promise<BankImportPreview> {
  return request<BankImportPreview>("/api/v1/transactions/imports/preview", {
    method: "POST",
    token,
    body: {
      file_name: payload.fileName,
      content_base64: payload.contentBase64,
      account_id: payload.accountId,
    },
  });
}

export function commitBankImport(
  token: string,
  previewId: string,
  accountId: number | null,
): Promise<BankImportResult> {
  return request<BankImportResult>("/api/v1/transactions/imports/commit", {
    method: "POST",
    token,
    body: { preview_id: previewId, account_id: accountId },
  });
}

export function getBankImportHistory(token: string, signal?: AbortSignal): Promise<BankImportHistory> {
  return request<BankImportHistory>("/api/v1/transactions/imports?limit=20", { token, signal });
}

export function cancelBankImport(token: string, batchId: number): Promise<BankImportCancelResult> {
  return request<BankImportCancelResult>(`/api/v1/transactions/imports/${batchId}/cancel`, {
    method: "POST",
    token,
  });
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

export function getReschedulableOccurrences(
  token: string,
  accountId: string,
  signal?: AbortSignal,
): Promise<ReschedulableOccurrencesResult> {
  const query = new URLSearchParams();
  if (accountId !== "all") query.set("account_id", accountId);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return request<ReschedulableOccurrencesResult>(
    `/api/v1/forecast/reschedulable-occurrences${suffix}`,
    { token, signal },
  );
}

export function rescheduleOccurrences(
  token: string,
  occurrenceIds: number[],
  targetDate: string,
): Promise<OccurrenceRescheduleResult> {
  return request<OccurrenceRescheduleResult>("/api/v1/forecast/occurrences/reschedule", {
    method: "POST",
    token,
    body: { occurrence_ids: occurrenceIds, target_date: targetDate },
  });
}

export function createRecurrence(token: string, payload: RecurrencePayload): Promise<RecurrenceActionResult> {
  return request<RecurrenceActionResult>("/api/v1/recurrences", {
    method: "POST",
    token,
    body: recurrenceBody(payload),
  });
}

export function updateRecurrence(token: string, itemId: number, payload: RecurrencePayload): Promise<RecurrenceActionResult> {
  return request<RecurrenceActionResult>(`/api/v1/recurrences/${itemId}`, {
    method: "PUT",
    token,
    body: recurrenceBody(payload),
  });
}

export function deleteRecurrence(token: string, itemId: number): Promise<RecurrenceActionResult> {
  return request<RecurrenceActionResult>(`/api/v1/recurrences/${itemId}`, {
    method: "DELETE",
    token,
  });
}

function recurrenceBody(payload: RecurrencePayload) {
  return {
    account_id: payload.accountId,
    name: payload.name,
    category: payload.category,
    direction: payload.direction,
    amount: payload.amount,
    frequency: payload.frequency,
    next_date: payload.nextDate,
    end_date: payload.endDate || null,
    scenario: payload.scenario,
  };
}

export function getScenarioSettings(token: string, signal?: AbortSignal): Promise<ScenarioSettingsSnapshot> {
  return request<ScenarioSettingsSnapshot>("/api/v1/scenarios", { token, signal });
}

export function createScenario(token: string, payload: ScenarioPayload): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>("/api/v1/scenarios", {
    method: "POST",
    token,
    body: scenarioBody(payload),
  });
}

export function updateScenario(token: string, scenarioId: number, payload: ScenarioPayload): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenarios/${scenarioId}`, {
    method: "POST",
    token,
    body: scenarioBody(payload),
  });
}

export function duplicateScenario(token: string, scenarioId: number): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenarios/${scenarioId}/duplicate`, {
    method: "POST",
    token,
  });
}

export function deleteScenario(token: string, scenarioId: number): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenarios/${scenarioId}/delete`, {
    method: "POST",
    token,
  });
}

export function createScenarioEvent(token: string, scenarioId: number, payload: ScenarioEventPayload): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenarios/${scenarioId}/events`, {
    method: "POST",
    token,
    body: scenarioEventBody(payload),
  });
}

export function updateScenarioEvent(token: string, eventId: number, payload: ScenarioEventPayload): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenario-events/${eventId}`, {
    method: "POST",
    token,
    body: scenarioEventBody(payload),
  });
}

export function deleteScenarioEvent(token: string, eventId: number): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenario-events/${eventId}/delete`, {
    method: "POST",
    token,
  });
}

function scenarioBody(payload: ScenarioPayload) {
  return {
    name: payload.name,
    description: payload.description,
    scenario_type: payload.scenarioType,
    start_date: payload.startDate,
    end_date: payload.endDate || null,
    horizon_months: payload.horizonMonths,
    currency_code: payload.currencyCode,
    is_active: payload.isActive,
  };
}

function scenarioEventBody(payload: ScenarioEventPayload) {
  return {
    event_type: payload.eventType,
    label: payload.label,
    description: payload.description,
    event_date: payload.eventDate,
    end_date: payload.endDate || null,
    amount: payload.amount,
    currency_code: payload.currencyCode,
    frequency: payload.frequency,
    duration_months: payload.durationMonths || null,
    account_id: payload.accountId,
    is_active: payload.isActive,
  };
}

export function getBudgets(token: string, month: string, signal?: AbortSignal): Promise<BudgetsSnapshot> {
  const query = new URLSearchParams();
  if (month) query.set("month", month);
  const encoded = query.toString();
  const suffix = encoded ? `?${encoded}` : "";
  return request<BudgetsSnapshot>(`/api/v1/budgets${suffix}`, { token, signal });
}

export function getAssets(token: string, signal?: AbortSignal): Promise<AssetsSnapshot> {
  return request<AssetsSnapshot>("/api/v1/assets", { token, signal });
}

export function getSettings(token: string, signal?: AbortSignal): Promise<SettingsSnapshot> {
  return request<SettingsSnapshot>("/api/v1/settings", { token, signal });
}

export function updateSettingsGeneral(
  token: string,
  payload: { currency: string; current_month: string; session_timeout_minutes: number },
): Promise<SettingsActionResult> {
  return request<SettingsActionResult>("/api/v1/settings/general", { method: "POST", token, body: payload });
}

export function createSettingsCategory(token: string, payload: SettingsCategoryPayload): Promise<SettingsActionResult> {
  return request<SettingsActionResult>("/api/v1/settings/categories", { method: "POST", token, body: payload });
}

export function updateSettingsCategory(token: string, categoryId: number, payload: SettingsCategoryPayload): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/settings/categories/${categoryId}`, { method: "POST", token, body: payload });
}

export function deleteSettingsCategory(token: string, categoryId: number): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/settings/categories/${categoryId}/delete`, { method: "POST", token });
}

export function createSettingsRule(token: string, payload: SettingsRulePayload): Promise<SettingsActionResult> {
  return request<SettingsActionResult>("/api/v1/settings/rules", { method: "POST", token, body: payload });
}

export function updateSettingsRule(token: string, ruleId: number, payload: SettingsRulePayload): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/settings/rules/${ruleId}`, { method: "POST", token, body: payload });
}

export function setSettingsRuleActive(token: string, ruleId: number, active: boolean): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/settings/rules/${ruleId}/active`, {
    method: "POST",
    token,
    body: { active },
  });
}

export function previewSettingsRules(token: string): Promise<SettingsRulesPreview> {
  return request<SettingsRulesPreview>("/api/v1/settings/rules-preview", { method: "POST", token });
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
