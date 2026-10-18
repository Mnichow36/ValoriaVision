export type Tone = "blue" | "green" | "purple" | "red" | "amber";

export interface DashboardKpi {
  id: string;
  label: string;
  value: number;
  currency: string;
  detail: string;
  tone: Tone;
}

export interface ForecastPoint {
  label: string;
  balance: number;
}

export interface BudgetRow {
  category: string;
  planned: number;
  actual: number;
  remaining: number;
  usage: number;
  status: string;
}

export interface AssetSlice {
  label: string;
  value: number;
}

export interface DashboardAlert {
  level: "info" | "success" | "warning" | "critical";
  title: string;
  detail: string;
}

export interface DashboardSnapshot {
  generatedAt: string;
  period: string;
  currency: string;
  kpis: DashboardKpi[];
  forecast: ForecastPoint[];
  budget: {
    month: string;
    totalPlanned: number;
    totalRealized: number;
    rows: BudgetRow[];
  };
  assets: AssetSlice[];
  alerts: DashboardAlert[];
}

export interface AccountTransaction {
  id: number;
  date: string;
  label: string;
  category: string;
  amount: number;
  status: string;
}

export interface AccountOverview {
  id: number;
  name: string;
  bank: string;
  type: string;
  identifier: string;
  currency: string;
  status: string;
  initialBalance: number;
  initialDate: string;
  movementTotal: number;
  currentBalance: number;
  currentDate: string;
  transactions: AccountTransaction[];
}

export interface AccountsSnapshot {
  generatedAt: string;
  currency: string;
  summary: {
    accountCount: number;
    activeCount: number;
    netBalance: number;
  };
  accounts: AccountOverview[];
}

export interface AccountPayload {
  name: string;
  bank: string;
  type: string;
  identifier: string;
  initialBalance: number;
  initialDate: string;
  currency: string;
  status: string;
}

export interface AccountActionResult {
  success: boolean;
  message: string;
  accountId: number;
}

export interface TransactionAccount {
  id: number;
  name: string;
  bank: string;
  status: string;
}

export interface TransactionCategory {
  id: number;
  name: string;
  kind: string;
  color: string;
}

export interface TransactionRow {
  id: number;
  date: string;
  accountId: number;
  accountName: string;
  bank: string;
  label: string;
  beneficiary: string;
  ruleSuggestion: string;
  category: string;
  status: string;
  amount: number;
  type: string;
  source: string;
  importBatchId: number | null;
}

export interface TransactionEditPayload {
  accountId: number;
  date: string;
  label: string;
  category: string;
  direction: "Débit" | "Crédit";
  amount: number;
  status: string;
}

export interface TransactionActionResult {
  success: boolean;
  message: string;
  transactionId: number;
}

export interface TransactionBulkResult {
  success: boolean;
  message: string;
  updatedCount: number;
  transactionIds: number[];
}

export interface RecentImport {
  id: number;
  fileName: string;
  accountName: string;
  importedCount: number;
  duplicateCount: number;
  errorCount: number;
  recognizedCount: number;
  linkedTransactions: number;
  status: string;
  createdAt: string;
}

export interface TransactionsSnapshot {
  generatedAt: string;
  currency: string;
  summary: {
    transactionCount: number;
    categorizedCount: number;
    categorizedPercent: number;
    reviewCount: number;
  };
  accounts: TransactionAccount[];
  categories: TransactionCategory[];
  transactions: TransactionRow[];
  recentImport: RecentImport | null;
}

export interface BankImportPreviewRow {
  date: string;
  label: string;
  beneficiary: string;
  category: string;
  amount: number;
  currency: string;
  status: "Nouveau" | "Doublon";
  duplicate: boolean;
}

export interface BankImportPreview {
  previewId: string;
  fileName: string;
  accountId: number | null;
  accountConsistent: boolean;
  accountMessage: string;
  detectedAccounts: string[];
  format: string;
  profile: string;
  recognizedCount: number;
  newCount: number;
  duplicateCount: number;
  errorCount: number;
  rowsTruncated: boolean;
  rows: BankImportPreviewRow[];
}

export interface BankImportResult {
  success: boolean;
  message: string;
  batchId: number;
  importedCount: number;
  duplicateCount: number;
  errorCount: number;
  categorization: {
    automatic: number;
    toReview: number;
    toCategorize: number;
  };
  reconciliation: {
    automatic: number;
    toReview: number;
    withoutForecast: number;
  };
}

export interface BankImportHistoryItem extends RecentImport {
  bank: string;
  accountIdentifier: string;
  canceledAt: string;
  parserProfile: string;
}

export interface BankImportHistory {
  items: BankImportHistoryItem[];
  count: number;
}

export interface BankImportCancelResult {
  success: boolean;
  message: string;
  batchId: number;
  deletedCount: number;
}

export interface ForecastAccount {
  id: number;
  name: string;
  bank: string;
  type: string;
}

export interface ForecastCategory {
  id: number;
  name: string;
  direction: "Recette" | "Dépense" | "Neutre";
  color: string;
}

export interface RecurrencePayload {
  accountId: number;
  name: string;
  category: string;
  direction: "Débit" | "Crédit";
  amount: number;
  frequency: "Ponctuel" | "Hebdomadaire" | "Mensuel" | "Trimestriel" | "Annuel";
  nextDate: string;
  endDate: string;
  scenario: "Prudent" | "Réaliste" | "Optimiste";
}

export interface RecurrenceActionResult {
  success: boolean;
  message: string;
  recurringItemId: number;
  generatedOccurrences: number;
}

export interface ReschedulableOccurrence {
  id: number;
  date: string;
  originalDate: string;
  label: string;
  amount: number;
  category: string;
  direction: string;
  accountId: number | null;
  accountName: string;
  bank: string;
  frequency: string;
  status: string;
  statusLabel: string;
  alreadyRescheduled: boolean;
}

export interface ReschedulableOccurrencesResult {
  referenceDate: string;
  minTargetDate: string;
  items: ReschedulableOccurrence[];
}

export interface OccurrenceRescheduleResult {
  success: boolean;
  message: string;
  updatedCount: number;
  targetDate: string;
  occurrenceIds: number[];
}

export interface RecurrenceItem {
  id: number;
  accountId: number;
  accountName: string;
  bank: string;
  name: string;
  category: string;
  direction: RecurrencePayload["direction"];
  amount: number;
  frequency: RecurrencePayload["frequency"];
  nextDate: string;
  endDate: string;
  scenario: RecurrencePayload["scenario"];
  status: string;
}

export interface ForecastPoint {
  date: string;
  label: string;
  balance: number;
  events: ForecastEvent[];
}

export interface ForecastEvent {
  date: string;
  name: string;
  category: string;
  amount: number;
  source: string;
  account: string;
  scenario: string;
  originalDate: string;
  recurringId: number | null;
}

export interface ForecastSnapshot {
  generatedAt: string;
  currency: string;
  filters: {
    accountId: number | null;
    accountLabel: string;
    horizonDays: number;
    scenario: string;
    startDate: string;
  };
  accounts: ForecastAccount[];
  categories: ForecastCategory[];
  recurrences: RecurrenceItem[];
  series: {
    selected: ForecastPoint[];
    realized: ForecastPoint[];
    prudent: ForecastPoint[];
    optimistic: ForecastPoint[];
  };
  summary: {
    startingCash: number;
    lowBalance: number;
    lowDate: string;
    endBalance: number;
    endDate: string;
    totalIn: number;
    totalOut: number;
    prudentDifference: number;
    alert: string;
  };
  upcoming: ForecastEvent[];
}

export interface BudgetTransaction {
  id: number;
  date: string;
  label: string;
  amount: number;
}

export interface BudgetCategoryRow {
  id: number | null;
  category: string;
  planned: number;
  actual: number;
  remaining: number;
  difference: number;
  usage: number;
  alertThreshold: number;
  status: string;
  notes: string;
  transactions: BudgetTransaction[];
}

export interface BudgetsSnapshot {
  generatedAt: string;
  currency: string;
  month: string;
  months: string[];
  summary: {
    totalPlanned: number;
    totalRealized: number;
    totalRemaining: number;
    usageTotal: number;
    categoryCount: number;
    overCount: number;
    warningCount: number;
    status: string;
    biggestGap: number;
    biggestGapCategory: string;
  };
  rows: BudgetCategoryRow[];
}

export interface ReconciliationAccount {
  id: number;
  name: string;
  bank: string;
}

export interface ReconciliationStatusOption {
  id: string;
  label: string;
}

export interface ReconciliationTransaction {
  id: number;
  date: string;
  label: string;
  beneficiary: string;
  amount: number;
  remainingAmount: number;
  category: string;
  accountId: number;
  accountName: string;
  bank: string;
  linkedStatus: string | null;
  linkedStatusLabel: string | null;
  linkedOccurrenceId: number | null;
  proposalOccurrenceId: number | null;
}

export interface ReconciliationOccurrence {
  id: number;
  date: string;
  label: string;
  amount: number;
  category: string;
  direction: string;
  accountId: number | null;
  accountName: string;
  bank: string;
  status: string;
  statusLabel: string;
  matchedAmount: number;
  remainingAmount: number;
  overageAmount: number;
  matchConfidence: number | null;
  matchReason: string;
}

export interface ReconciliationSuggestion {
  proposalId: number | null;
  transactionId: number;
  occurrenceId: number;
  score: number;
  reason: string;
  decision: "automatic" | "to_review" | "unmatched";
  amountDifference: number;
}

export interface ReconciliationSnapshot {
  generatedAt: string;
  currency: string;
  filters: {
    accountId: number | null;
    status: string;
  };
  accounts: ReconciliationAccount[];
  statusOptions: ReconciliationStatusOption[];
  rules: {
    automaticThreshold: number;
    reviewThreshold: number;
    dateToleranceDays: number;
  };
  summary: {
    unmatchedTransactions: number;
    openOccurrences: number;
    automaticProposals: number;
    averageScore: number;
    matched: number;
    toReview: number;
    partial: number;
  };
  transactions: ReconciliationTransaction[];
  occurrences: ReconciliationOccurrence[];
  suggestions: ReconciliationSuggestion[];
}

export interface ReconciliationActionResult {
  success: boolean;
  message: string;
}

export interface AssetFamily {
  name: string;
  value: number;
  weight: number;
  status: string;
}

export interface PatrimonialAsset {
  id: number;
  name: string;
  category: string;
  type: string;
  value: number;
  valuationDate: string;
  valuationMode: string;
  status: string;
  comment: string;
}

export interface AssetEvolutionPoint {
  date: string;
  net: number;
  assets: number;
  liabilities: number;
}

export interface AssetsSnapshot {
  generatedAt: string;
  currency: string;
  summary: {
    totalAssets: number;
    totalLiabilities: number;
    netWorth: number;
    liquidities: number;
    changePercent: number;
    assetCount: number;
    liabilityCount: number;
  };
  families: AssetFamily[];
  evolution: AssetEvolutionPoint[];
  assets: PatrimonialAsset[];
  liabilities: PatrimonialAsset[];
  leadingAssetId: number | null;
}

export interface SettingsCategory {
  id: number;
  name: string;
  kind: string;
  direction: string;
  color: string;
  budgetEnabled: boolean;
  isSystem: boolean;
  usage: {
    transactions: number;
    recurrences: number;
    budgets: number;
  };
}

export interface SettingsRule {
  id: number;
  name: string;
  description: string;
  active: boolean;
  priority: number;
  matchField: string;
  matchOperator: string;
  matchValue: string;
  transactionType: string;
  accountId: number | null;
  accountName: string;
  minAmount: number | null;
  maxAmount: number | null;
  targetCategoryId: number;
  targetCategory: string;
  confidence: number;
  summary: string;
}

export interface SettingsSnapshot {
  generatedAt: string;
  general: {
    currency: string;
    locale: string;
    currentMonth: string;
    databaseSizeKb: number;
    schemaVersion: string;
    integrity: string;
    lastBackup: string;
  };
  categories: SettingsCategory[];
  rules: SettingsRule[];
  options: {
    accounts: Array<{ id: number; name: string; bank: string }>;
    categories: Array<{ id: number; name: string }>;
    matchFields: Array<{ id: string; label: string }>;
    operators: Array<{ id: string; label: string }>;
    transactionTypes: string[];
  };
  balances: {
    accounts: Array<{
      id: number;
      name: string;
      bank: string;
      status: string;
      initialBalance: number;
      initialDate: string;
      movementTotal: number;
      currentBalance: number;
      currentDate: string;
    }>;
    summary: {
      accountCount: number;
      orphanTransactions: number;
      orphanImportLinks: number;
      revenuesGap: number;
      expensesGap: number;
    };
  };
  security: {
    encryptedVault: boolean;
    encryptedBackups: boolean;
    masterPassword: boolean;
    algorithm: string;
    keyStorage: string;
    sessionTimeoutMinutes: number;
    lastBackup: string;
  };
  ownership: Array<{ feature: string; owner: string; mode: string }>;
}

export interface SettingsCategoryPayload {
  name: string;
  kind: string;
  direction: string;
  color: string;
  budget_enabled: boolean;
}

export interface SettingsRulePayload {
  name: string;
  description: string;
  is_active: boolean;
  priority: number;
  match_field: string;
  match_operator: string;
  match_value: string;
  transaction_type: string | null;
  account_id: number | null;
  min_amount: number | null;
  max_amount: number | null;
  target_category_id: number;
  confidence: number;
}

export interface SettingsActionResult {
  success: boolean;
  message: string;
  id?: number;
}

export interface SettingsRulesPreview extends SettingsActionResult {
  matchedCount: number;
  byRule: Array<{ ruleId: number; count: number }>;
  samples: Array<{ transactionId: number; label: string; ruleId: number; category: string }>;
}

export interface ApiHealth {
  status: "ok";
  service: string;
  apiVersion: string;
}

export interface AuthStatus {
  configured: boolean;
  authenticated: boolean;
  timeoutSeconds: number;
}

export interface AuthSession {
  token: string;
  expiresIn: number;
}
