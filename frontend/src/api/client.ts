import { invoke } from "@tauri-apps/api/core";

import type { PendingRulesApplyResult, PendingRulesPreview, RuleSuggestionApplyItem, RuleSuggestionApplyResult, RuleSuggestionPreviewRow, RuleSuggestionsSnapshot, AccessMatrix, BackupFile, BackupInspection, BackupList, Me, Profile, ProfileAccessPayload, ProfileCreatePayload, ProfileUpdatePayload, RecoveryRequestResult, SecurityStatus, SecurityEvent, AccountActionResult, AccountPayload, AccountsSnapshot, ApiHealth, AssetsSnapshot, AuthSession, AuthStatus, BankImportCancelResult, BankImportHistory, BankImportPreview, BankImportResult, BudgetActionResult, BudgetsSnapshot, DashboardSnapshot, ForecastSimulationResult, ForecastSnapshot, OccurrenceRescheduleResult, PatrimonialAssetActionResult, PatrimonialAssetPayload, RecurrenceActionResult, RecurrenceOccurrenceActionResult, RecurrenceOccurrencesSnapshot, RecurrencePayload, ReschedulableOccurrencesResult, ReconciliationActionResult, ReconciliationHistory, ReconciliationRulesPayload, ScenarioActionResult, ScenarioEventPayload, ScenarioPayload, ScenarioPresetPayload, ScenarioSettingsSnapshot, ReconciliationSnapshot, SettingsActionResult, SettingsCategoryPayload, SettingsRulePayload, SettingsRulesPreview, SettingsSnapshot, TransactionActionResult, TransactionBulkResult, TransactionCreatePayload, TransactionEditPayload, TransactionsSnapshot } from "./contracts";

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
    const retryAfter = Number(response.headers.get("Retry-After")) || undefined;
    throw Object.assign(new Error(detail), { retryAfter });
  }

  return response.json() as Promise<T>;
}

export function getHealth(signal?: AbortSignal): Promise<ApiHealth> {
  return request<ApiHealth>("/api/v1/health", { signal });
}

export function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  return request<AuthStatus>("/api/v1/auth/status", { signal });
}

export function openSession(profileId: string, password: string): Promise<AuthSession> {
  return request<AuthSession>("/api/v1/auth/unlock", {
    method: "POST",
    body: { profile_id: profileId, password },
  });
}

/** Première installation : crée le premier administrateur et ouvre sa session. */
export function setupAdministrator(name: string, password: string): Promise<AuthSession & { recoveryKey: string }> {
  return request<AuthSession & { recoveryKey: string }>("/api/v1/auth/setup", { method: "POST", body: { name, password } });
}

export function getAccessMatrix(token: string, signal?: AbortSignal): Promise<AccessMatrix> {
  return request<AccessMatrix>("/api/v1/access", { token, signal });
}

export function updateProfileAccess(token: string, profileId: string, payload: ProfileAccessPayload): Promise<{ profile: Profile }> {
  return request<{ profile: Profile }>(`/api/v1/profiles/${encodeURIComponent(profileId)}/access`, { method: "PUT", token, body: payload });
}

export function getMe(token: string): Promise<{ me: Me | null }> {
  return request<{ me: Me | null }>("/api/v1/me", { token });
}

export function createProfile(token: string, payload: ProfileCreatePayload): Promise<{ profile: Profile; recoveryKey: string | null }> {
  return request<{ profile: Profile; recoveryKey: string | null }>("/api/v1/profiles", { method: "POST", token, body: payload });
}

export function updateProfile(token: string, profileId: string, payload: ProfileUpdatePayload): Promise<{ profile: Profile }> {
  return request<{ profile: Profile }>(`/api/v1/profiles/${encodeURIComponent(profileId)}`, { method: "PUT", token, body: payload });
}

export function deleteProfile(token: string, profileId: string, password: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/api/v1/profiles/${encodeURIComponent(profileId)}/delete`, { method: "POST", token, body: { password } });
}

export function getSecurityJournal(token: string, signal?: AbortSignal): Promise<{ events: SecurityEvent[] }> {
  return request<{ events: SecurityEvent[] }>("/api/v1/security/journal", { token, signal });
}

export function getSecurityStatus(token: string, signal?: AbortSignal): Promise<SecurityStatus> {
  return request<SecurityStatus>("/api/v1/security/status", { token, signal });
}

export function changePassword(token: string, currentPassword: string, newPassword: string): Promise<{ changed: boolean }> {
  return request<{ changed: boolean }>("/api/v1/security/change-password", {
    method: "POST",
    token,
    body: { current_password: currentPassword, new_password: newPassword },
  });
}

export function createRecoveryKey(token: string, password: string): Promise<{ recoveryKey: string; createdAt: string }> {
  return request<{ recoveryKey: string; createdAt: string }>("/api/v1/security/recovery-key", {
    method: "POST",
    token,
    body: { password },
  });
}

export function recoverAccess(recoveryKey: string, newPassword: string, profileId?: string): Promise<RecoveryRequestResult> {
  return request<RecoveryRequestResult>("/api/v1/auth/recover", {
    method: "POST",
    body: { recovery_key: recoveryKey, new_password: newPassword, profile_id: profileId },
  });
}

export function closeSession(token: string): Promise<{ locked: boolean }> {
  return request<{ locked: boolean }>("/api/v1/auth/lock", { method: "POST", token });
}

export function getDashboard(token: string, filters?: { accountId?: string; month?: string }, signal?: AbortSignal): Promise<DashboardSnapshot> {
  const query = new URLSearchParams();
  if (filters?.accountId && filters.accountId !== "all") query.set("account_id", filters.accountId);
  if (filters?.month) query.set("month", filters.month);
  const encoded = query.toString();
  return request<DashboardSnapshot>(`/api/v1/dashboard${encoded ? `?${encoded}` : ""}`, { token, signal });
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

export function updateAccountStatus(token: string, accountId: number, status: string): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/v1/accounts/${accountId}/status`, {
    method: "POST",
    token,
    body: { status },
  });
}

export function deleteAccount(token: string, accountId: number): Promise<AccountActionResult> {
  return request<AccountActionResult>(`/api/v1/accounts/${accountId}/delete`, {
    method: "POST",
    token,
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

export function createTransaction(
  token: string,
  payload: TransactionCreatePayload,
): Promise<TransactionActionResult> {
  return request<TransactionActionResult>("/api/v1/transactions", {
    method: "POST",
    token,
    body: {
      account_id: payload.accountId,
      tx_date: payload.date,
      label: payload.label,
      beneficiary: payload.beneficiary || null,
      category: payload.category || null,
      direction: payload.direction,
      amount: payload.amount,
    },
  });
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
  action: "category" | "validate" | "delete",
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
    kind: payload.kind ?? null,
  };
}

export function getScenarioSettings(token: string, signal?: AbortSignal): Promise<ScenarioSettingsSnapshot> {
  return request<ScenarioSettingsSnapshot>("/api/v1/scenarios", { token, signal });
}

export function updateScenarioPreset(token: string, scenarioName: string, payload: ScenarioPresetPayload): Promise<ScenarioActionResult> {
  return request<ScenarioActionResult>(`/api/v1/scenario-presets/${encodeURIComponent(scenarioName)}`, {
    method: "POST",
    token,
    body: {
      income_percent: payload.incomePercent,
      expense_percent: payload.expensePercent,
    },
  });
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

export function reviseBudget(
  token: string,
  payload: { category: string; month: string; scope: "month" | "from" | "year"; newAmount: number; reason: string },
): Promise<BudgetActionResult> {
  return request<BudgetActionResult>("/api/v1/budgets/revise", {
    method: "POST",
    token,
    body: { category: payload.category, month: payload.month, scope: payload.scope, new_amount: payload.newAmount, reason: payload.reason },
  });
}

export function saveBudgetCategory(
  token: string,
  payload: { category: string; month: string; plannedAmount?: number; alertThreshold?: number; mode?: string; notes?: string; active?: boolean },
): Promise<BudgetActionResult> {
  return request<BudgetActionResult>("/api/v1/budgets/category", {
    method: "POST",
    token,
    body: {
      category: payload.category,
      month: payload.month,
      planned_amount: payload.plannedAmount ?? null,
      alert_threshold: payload.alertThreshold ?? null,
      mode: payload.mode ?? null,
      notes: payload.notes ?? null,
      active: payload.active ?? null,
    },
  });
}

export function removeBudgetCategory(token: string, category: string, month: string): Promise<BudgetActionResult> {
  return request<BudgetActionResult>("/api/v1/budgets/category/remove", { method: "POST", token, body: { category, month } });
}

export function saveBudgetRules(token: string, defaultAlertThreshold: number): Promise<BudgetActionResult> {
  return request<BudgetActionResult>("/api/v1/budgets/rules", { method: "POST", token, body: { default_alert_threshold: defaultAlertThreshold } });
}

export function getAssets(token: string, signal?: AbortSignal): Promise<AssetsSnapshot> {
  return request<AssetsSnapshot>("/api/v1/assets", { token, signal });
}

function assetBody(payload: PatrimonialAssetPayload) {
  return {
    name: payload.name,
    category: payload.category,
    asset_type: payload.assetType,
    value: payload.value,
    valuation_date: payload.valuationDate,
    valuation_mode: payload.valuationMode,
    comment: payload.comment,
    details: payload.details,
    status: payload.status,
  };
}

export function createAsset(token: string, payload: PatrimonialAssetPayload): Promise<PatrimonialAssetActionResult> {
  return request<PatrimonialAssetActionResult>("/api/v1/assets", { method: "POST", token, body: assetBody(payload) });
}

export function updateAsset(token: string, assetId: number, payload: PatrimonialAssetPayload): Promise<PatrimonialAssetActionResult> {
  return request<PatrimonialAssetActionResult>(`/api/v1/assets/${assetId}`, { method: "POST", token, body: assetBody(payload) });
}

export function deleteAsset(token: string, assetId: number): Promise<PatrimonialAssetActionResult> {
  return request<PatrimonialAssetActionResult>(`/api/v1/assets/${assetId}/delete`, { method: "POST", token });
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

export function deleteSettingsRule(token: string, ruleId: number): Promise<SettingsActionResult> {
  return request<SettingsActionResult>(`/api/v1/settings/rules/${ruleId}/delete`, { method: "POST", token });
}

export function previewPendingRules(token: string, ruleId?: number | null): Promise<PendingRulesPreview> {
  return request<PendingRulesPreview>("/api/v1/settings/rules-pending-preview", {
    method: "POST",
    token,
    body: { rule_id: ruleId ?? null },
  });
}

export function applyPendingRules(token: string, transactionIds: number[], ruleId?: number | null): Promise<PendingRulesApplyResult> {
  return request<PendingRulesApplyResult>("/api/v1/settings/rules-apply", {
    method: "POST",
    token,
    body: { transaction_ids: transactionIds, rule_id: ruleId ?? null },
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

export function updateReconciliationRules(
  token: string,
  rules: ReconciliationRulesPayload,
): Promise<ReconciliationActionResult> {
  return request<ReconciliationActionResult>("/api/v1/reconciliation/rules", {
    method: "PUT",
    token,
    body: {
      date_tolerance_days: rules.dateToleranceDays,
      amount_tolerance_abs: rules.amountToleranceAbs,
      amount_tolerance_percent: rules.amountTolerancePercent,
      manual_window_days: rules.manualWindowDays,
      manual_amount_tolerance_percent: rules.manualAmountTolerancePercent,
    },
  });
}

export function cancelReconciliation(
  token: string,
  payload: { occurrenceId: number; transactionId?: number },
): Promise<ReconciliationActionResult> {
  return request<ReconciliationActionResult>("/api/v1/reconciliation/links/cancel", {
    method: "POST",
    token,
    body: { occurrence_id: payload.occurrenceId, transaction_id: payload.transactionId ?? null },
  });
}

export function getReconciliationHistory(
  token: string,
  filter: { transactionId?: number; occurrenceId?: number },
): Promise<ReconciliationHistory> {
  const params = new URLSearchParams();
  if (filter.transactionId !== undefined) params.set("transaction_id", String(filter.transactionId));
  if (filter.occurrenceId !== undefined) params.set("occurrence_id", String(filter.occurrenceId));
  return request<ReconciliationHistory>(`/api/v1/reconciliation/history?${params.toString()}`, { token });
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

export function getRecurrenceOccurrences(token: string, signal?: AbortSignal): Promise<RecurrenceOccurrencesSnapshot> {
  return request<RecurrenceOccurrencesSnapshot>("/api/v1/recurrences/occurrences", { token, signal });
}

export function updateRecurrenceOccurrence(
  token: string,
  occurrenceId: number,
  payload: { date: string; amount: number; label: string; category: string; apply_to_rule?: boolean },
): Promise<RecurrenceOccurrenceActionResult> {
  return request<RecurrenceOccurrenceActionResult>(`/api/v1/recurrences/occurrences/${occurrenceId}`, {
    method: "PUT",
    token,
    body: payload,
  });
}

export function shiftRecurrenceOccurrences(token: string, occurrenceIds: number[], targetDate: string): Promise<RecurrenceOccurrenceActionResult> {
  return request<RecurrenceOccurrenceActionResult>("/api/v1/recurrences/occurrences/shift", {
    method: "POST",
    token,
    body: { occurrence_ids: occurrenceIds, target_date: targetDate },
  });
}

export function deleteRecurrenceOccurrences(token: string, occurrenceIds: number[]): Promise<RecurrenceOccurrenceActionResult> {
  return request<RecurrenceOccurrenceActionResult>("/api/v1/recurrences/occurrences/delete", {
    method: "POST",
    token,
    body: { occurrence_ids: occurrenceIds },
  });
}

export function restoreRecurrenceOccurrence(token: string, occurrenceId: number): Promise<RecurrenceOccurrenceActionResult> {
  return request<RecurrenceOccurrenceActionResult>(`/api/v1/recurrences/occurrences/${occurrenceId}/restore`, {
    method: "POST",
    token,
  });
}

export function postponeRecurrenceOccurrences(token: string, occurrenceIds: number[]): Promise<RecurrenceOccurrenceActionResult> {
  return request<RecurrenceOccurrenceActionResult>("/api/v1/recurrences/occurrences/postpone", {
    method: "POST",
    token,
    body: { occurrence_ids: occurrenceIds },
  });
}

export function updateSafetyThreshold(token: string, amount: number): Promise<{ success: boolean; message: string; safetyThreshold: number }> {
  return request<{ success: boolean; message: string; safetyThreshold: number }>("/api/v1/forecast/safety-threshold", {
    method: "PUT",
    token,
    body: { amount },
  });
}

export function simulateForecast(
  token: string,
  payload: { kind: "Dépense" | "Recette"; date: string; amount: number; accountId: number | null; label: string; scenario: string },
  signal?: AbortSignal,
): Promise<ForecastSimulationResult> {
  return request<ForecastSimulationResult>("/api/v1/forecast/simulate", {
    method: "POST",
    token,
    signal,
    body: {
      kind: payload.kind,
      date: payload.date,
      amount: payload.amount,
      account_id: payload.accountId,
      label: payload.label,
      scenario: payload.scenario,
    },
  });
}

export function listBackups(token: string, signal?: AbortSignal): Promise<BackupList> {
  return request<BackupList>("/api/v1/backups", { token, signal });
}

export function createBackup(token: string, passphrase: string, confirm: string): Promise<BackupFile> {
  return request<BackupFile>("/api/v1/backups", { method: "POST", token, body: { passphrase, confirm } });
}

export function downloadBackup(token: string, name: string): Promise<BackupFile> {
  return request<BackupFile>("/api/v1/backups/download", { method: "POST", token, body: { name } });
}

export function deleteBackup(token: string, name: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>("/api/v1/backups/delete", { method: "POST", token, body: { name } });
}

/** Une sauvegarde est désignée par le nom d'une copie locale ou par le contenu (base64) d'un fichier choisi. */
export type BackupSource = { name: string } | { data: string };

export function inspectBackup(token: string, source: BackupSource, passphrase: string): Promise<BackupInspection> {
  return request<BackupInspection>("/api/v1/backups/inspect", { method: "POST", token, body: { ...source, passphrase } });
}

export function restoreBackup(token: string, source: BackupSource, passphrase: string, password: string): Promise<{ restored: boolean; safetyCopy: string }> {
  return request<{ restored: boolean; safetyCopy: string }>("/api/v1/backups/restore", { method: "POST", token, body: { ...source, passphrase, password } });
}

export function resetEverything(token: string, password: string, confirmation: string, passphrase: string): Promise<{ reset: boolean; safetyCopy: string }> {
  return request<{ reset: boolean; safetyCopy: string }>("/api/v1/system/reset", { method: "POST", token, body: { password, confirmation, passphrase } });
}

export function getRuleSuggestions(token: string, minReliability: number, signal?: AbortSignal): Promise<RuleSuggestionsSnapshot> {
  return request<RuleSuggestionsSnapshot>(`/api/v1/rule-suggestions?min_reliability=${minReliability}`, { token, signal });
}

export function previewRuleSuggestion(token: string, matchValue: string, transactionType: string | null, signal?: AbortSignal): Promise<{ transactions: RuleSuggestionPreviewRow[] }> {
  const query = new URLSearchParams({ match_value: matchValue });
  if (transactionType) query.set("transaction_type", transactionType);
  return request<{ transactions: RuleSuggestionPreviewRow[] }>(`/api/v1/rule-suggestions/preview?${query.toString()}`, { token, signal });
}

export function applyRuleSuggestions(token: string, items: RuleSuggestionApplyItem[]): Promise<RuleSuggestionApplyResult> {
  return request<RuleSuggestionApplyResult>("/api/v1/rule-suggestions/apply", { method: "POST", token, body: { items } });
}

export function dismissRuleSuggestion(token: string, matchValue: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>("/api/v1/rule-suggestions/dismiss", { method: "POST", token, body: { match_value: matchValue } });
}
