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
  target?: "budgets" | "forecast" | "transactions" | "reconciliation" | null;
}

export interface DashboardQuality {
  total: number;
  uncategorized: number;
  uncategorizedLarge: number;
  categorizedPercent: number;
  lastImport: string | null;
  daysSinceImport: number | null;
  reconciliationPending: number;
}

export interface DashboardUpcoming {
  date: string;
  label: string;
  amount: number;
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
  filters?: { accountId: number | null; month: string };
  accounts?: { id: number; name: string; status: string }[];
  months?: string[];
  toProcess?: number;
  expensesByCategory?: { label: string; value: number }[];
  budgetComparable?: boolean;
  flowHistory?: { month: string; income: number; expenses: number }[];
  assetDetails?: Record<string, { name: string; value: number }[]>;
  quality?: DashboardQuality;
  upcoming?: DashboardUpcoming[];
}

export interface ReconciliationBadge {
  reconciled: boolean;
  label: string;
  matchType: string;
  occurrenceId: number | null;
}

export interface ReconciliationLinkSummary {
  linkId: number;
  transactionId: number;
  occurrenceId: number;
  label: string;
  sourceType: string;
  appliedAmount: number;
  matchType: string;
}

export interface ReconciliationHistoryItem extends ReconciliationLinkSummary {
  occurrenceLabel: string;
  occurrenceDate: string;
  occurrenceAmount: number;
  recurrenceName: string;
  transactionLabel: string;
  transactionDate: string;
  transactionAmount: number;
  confidence: number;
  reason: string;
  createdAt: string;
  cancelledAt: string | null;
  active: boolean;
}

export interface ReconciliationHistory {
  items: ReconciliationHistoryItem[];
}

export interface AccountTransaction {
  id: number;
  date: string;
  label: string;
  category: string;
  amount: number;
  status: string;
  reconciliation?: ReconciliationBadge;
}

export interface AccountInsights {
  categories: { name: string; amount: number; share: number }[];
  expensesTotal: number;
  averageMonthlyExpense: number;
  averageMonthlyIncome: number;
  monthsCovered: number;
  largestExpense: { label: string; amount: number; date: string } | null;
  uncategorizedCount: number;
  reconciledCount: number;
  lastImportDate: string;
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
  transactionCount: number;
  balanceHistory: { month: string; balance: number }[];
  insights: AccountInsights;
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
  reconciliation?: ReconciliationBadge;
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

export interface TransactionCreatePayload {
  accountId: number;
  date: string;
  label: string;
  beneficiary: string;
  category: string;
  direction: "Débit" | "Crédit";
  amount: number;
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
  status: string;
}

export interface ForecastSimulationMetrics {
  daysBelow: number;
  firstBelow: string | null;
  lastBelow: string | null;
  minBalance: number;
  minDate: string;
  finalBalance: number;
}

export interface ForecastSimulationResult {
  kind: "Dépense" | "Recette";
  label: string;
  date: string;
  amount: number;
  accountId: number | null;
  scenario: string;
  threshold: number;
  verdict: "ok" | "ko" | "no_threshold";
  passes: boolean;
  without: ForecastSimulationMetrics;
  with: ForecastSimulationMetrics;
  suggestion: { date: string; minBalance: number; daysBelow: number } | null;
  series: { date: string; without: number; with: number }[];
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
  kind?: "Abonnement" | "Charge fixe" | "Revenu" | "Autre";
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
  referenceDate: string;
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
  nextOccurrenceDate: string;
  nextScheduledDate: string;
  nextRescheduledDate: string;
  forecastOccurrenceCount: number;
  rescheduledOccurrenceCount: number;
  endDate: string;
  scenario: RecurrencePayload["scenario"];
  kind: NonNullable<RecurrencePayload["kind"]>;
  status: string;
}

export interface ForecastPoint {
  date: string;
  label: string;
  balance: number;
  inflow?: number;
  outflow?: number;
  net?: number;
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
    referenceDate: string;
    startDate: string;
    endDate: string;
  };
  accounts: ForecastAccount[];
  categories: ForecastCategory[];
  recurrences: RecurrenceItem[];
  series: {
    selected: ForecastPoint[];
    realized: ForecastPoint[];
    realistic: ForecastPoint[];
    prudent: ForecastPoint[];
    optimistic: ForecastPoint[];
    custom: Record<string, ForecastPoint[]>;
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
    safetyThreshold: number;
    daysBelowThreshold: number;
    totalDays: number;
    overdueOccurrences: number;
    alert: string;
  };
  upcoming: ForecastEvent[];
}

export interface ScenarioEventTypeOption {
  id: string;
  label: string;
  nature: string;
  sense: string;
}

export interface ScenarioFrequencyOption {
  id: string;
  label: string;
}

export interface ScenarioEventItem {
  id: number;
  scenarioId: number;
  eventType: string;
  eventTypeLabel: string;
  label: string;
  description: string;
  eventDate: string;
  endDate: string;
  amount: number;
  currencyCode: string;
  frequency: string;
  frequencyLabel: string;
  durationMonths: number;
  accountId: number | null;
  accountName: string;
  isActive: boolean;
  nature: string;
  sense: string;
}

export interface ScenarioDefinition {
  id: number;
  name: string;
  description: string;
  scenarioType: string;
  startDate: string;
  endDate: string;
  horizonMonths: number;
  currencyCode: string;
  isReference: boolean;
  isActive: boolean;
  eventCount: number;
  events: ScenarioEventItem[];
}

export interface ScenarioPreset {
  name: "Prudent" | "Réaliste" | "Optimiste";
  description: string;
  incomePercent: number;
  expensePercent: number;
  color: string;
}

export interface ScenarioPresetPayload {
  incomePercent: number;
  expensePercent: number;
}

export interface ScenarioSettingsSnapshot {
  scenarioTypes: string[];
  eventTypes: ScenarioEventTypeOption[];
  frequencies: ScenarioFrequencyOption[];
  accounts: ForecastAccount[];
  presets: ScenarioPreset[];
  scenarios: ScenarioDefinition[];
}

export interface ScenarioPayload {
  name: string;
  description: string;
  scenarioType: string;
  startDate: string;
  endDate: string;
  horizonMonths: number;
  currencyCode: string;
  isActive: boolean;
}

export interface ScenarioEventPayload {
  eventType: string;
  label: string;
  description: string;
  eventDate: string;
  endDate: string;
  amount: number;
  currencyCode: string;
  frequency: string;
  durationMonths: number;
  accountId: number | null;
  isActive: boolean;
}

export interface ScenarioActionResult {
  success: boolean;
  message: string;
  scenarioId?: number;
  eventId?: number;
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

export interface BudgetRevision {
  id: number;
  scope: "month" | "from" | "year";
  fromMonth: string;
  toMonth: string;
  oldAmount: number;
  newAmount: number;
  reason: string;
  createdAt: string;
}

export interface BudgetTrackingPoint {
  day: number;
  budget: number;
  actual: number | null;
}

export interface BudgetWatchItem {
  category: string;
  planned: number;
  actual: number;
  usage: number;
  status: string;
  monthsOver: number;
  suggestRevision: boolean;
}

export interface BudgetTracking {
  daysInMonth: number;
  elapsedDays: number;
  daysLeft: number;
  perDay: number | null;
  projection: number | null;
  projectionGap: number | null;
  projectionMethod: string;
  curve: BudgetTrackingPoint[];
  watch: BudgetWatchItem[];
  watchOthers: number;
}

export interface BudgetAnnualCategory {
  category: string;
  planned: number[];
  initial: number[];
  actual: number[];
  annual: number;
  initialAnnual: number;
  cumul: number;
  initialCumul: number;
  realized: number;
  gap: number;
  usage: number;
  projectedYear: number;
  monthsOver: number;
  suggestRevision: boolean;
  revisionCount: number;
  revisions: BudgetRevision[];
}

export interface BudgetAnnual {
  year: number;
  elapsedMonths: number;
  currentMonth: string;
  categories: BudgetAnnualCategory[];
  totals: { annual: number; initialAnnual: number; cumul: number; initialCumul: number; realized: number; projectedYear: number; gap: number };
}

export interface BudgetSettingsCategory {
  category: string;
  active: boolean;
  amount: number;
  initialAmount: number;
  mode: string;
  alertThreshold: number;
  notes: string;
  lastRevision: string | null;
  revisions: BudgetRevision[];
}

export interface BudgetSettings {
  defaultAlertThreshold: number;
  modes: string[];
  categories: BudgetSettingsCategory[];
  available: string[];
}

export interface BudgetActionResult {
  success: boolean;
  message: string;
}

export interface BudgetsSnapshot {
  tracking: BudgetTracking;
  annual: BudgetAnnual;
  settings: BudgetSettings;
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
  reconciled: boolean;
  links: ReconciliationLinkSummary[];
  manualCandidate: {
    occurrenceId: number;
    label: string;
    date: string;
    dayGap: number;
    reason: string;
  } | null;
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
  displayStatus: string;
  matchMode: string;
  reconciled: boolean;
  links: ReconciliationLinkSummary[];
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
  view: {
    transactionsTitle: string;
    transactionsSubtitle: string;
    occurrencesTitle: string;
    occurrencesSubtitle: string;
  };
  accounts: ReconciliationAccount[];
  statusOptions: ReconciliationStatusOption[];
  rules: {
    automaticThreshold: number;
    reviewThreshold: number;
    dateToleranceDays: number;
    amountToleranceAbs: number;
    amountTolerancePercent: number;
    manualWindowDays: number;
    manualAmountTolerancePercent: number;
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

export interface ReconciliationRulesPayload {
  dateToleranceDays: number;
  amountToleranceAbs: number;
  amountTolerancePercent: number;
  manualWindowDays: number;
  manualAmountTolerancePercent: number;
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
  details: Record<string, string>;
}

export interface PatrimonialAssetPayload {
  name: string;
  category: string;
  assetType: string;
  value: number;
  valuationDate: string;
  valuationMode: string;
  comment: string;
  details: Record<string, string>;
  status: string;
}

export interface PatrimonialAssetActionResult {
  success: boolean;
  message: string;
  assetId: number;
}

export interface AssetEvolutionPoint {
  date: string;
  net: number;
  assets: number;
  liabilities: number;
}

export interface AssetSeriesPoint {
  date: string;
  value: number;
}

export interface AssetCategoryInsight {
  name: string;
  value: number;
  weight: number;
  assetIds: number[];
  count: number;
  isCash: boolean;
  series: AssetSeriesPoint[];
  change: { amount: number; percent: number | null } | null;
  volatility: number | null;
  volatilityReason: string;
  tri: number | null;
  triReason: string;
}

export interface AssetDebtInsight {
  id: number;
  name: string;
  category: string;
  balance: number;
  shareOfAssets: number;
  monthlyPayment: number | null;
  endDate: string | null;
  monthsLeft: number | null;
  rate: number | null;
  initialAmount: number | null;
  repaidPercent: number | null;
  interestLeft: number | null;
  series: AssetSeriesPoint[];
}

export interface AssetsHeadline {
  netWorth: number;
  change: { amount: number; percent: number | null; fromDate: string; months: number; complete: boolean } | null;
  annualReturn: { percent: number | null; months: number; reason: string };
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
  headline: AssetsHeadline | null;
  categories: AssetCategoryInsight[];
  debts: AssetDebtInsight[];
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
  usageCount: number;
  lastUsedAt: string;
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
  pendingCount: number;
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

export interface PendingRulesPreview {
  pendingCount: number;
  matchedCount: number;
  unmatchedCount: number;
  byRule: Array<{ ruleId: number; ruleName: string; summary: string; category: string; count: number }>;
  items: Array<{ id: number; date: string; label: string; amount: number; account: string; ruleId: number; category: string }>;
}

export interface PendingRulesApplyResult extends SettingsActionResult {
  classified: number;
  toReview: number;
}

export interface ApiHealth {
  status: "ok";
  service: string;
  apiVersion: string;
}

export interface Profile {
  id: string;
  name: string;
  color: string;
  kind: "personal" | "demo";
  avatar: string | null;
  lastLoginAt: string | null;
  configured: boolean;
  recoveryKeyConfigured: boolean;
  removable: boolean;
  role?: "admin" | "contributor" | "reader";
  roleLabel?: string;
  scopeAccounts?: number;
  scopeAssets?: number;
  totalAccounts?: number;
  totalAssets?: number;
}

export interface ProfileCreatePayload {
  name: string;
  color?: string;
  kind: "personal" | "demo";
  role?: "admin" | "contributor" | "reader";
  password?: string;
  avatar?: string | null;
  accounts?: number[];
  assets?: number[];
}

export interface ProfileUpdatePayload {
  name?: string;
  color?: string;
  role?: "admin" | "contributor" | "reader";
  avatar?: string | null;
  clear_avatar?: boolean;
}

export interface AccessResource {
  type: "account" | "asset";
  id: number;
  name: string;
  visibleTo: string[];
}

export interface AccessMatrix {
  users: Profile[];
  resources: AccessResource[];
}

export interface ProfileAccessPayload {
  accounts: number[];
  assets: number[];
}

/** Ce que le profil ouvert peut voir et faire. */
export interface Me {
  id: string;
  name: string;
  role: "admin" | "contributor" | "reader";
  roleLabel: string;
  canWrite: boolean;
  restricted: boolean;
  visibleAccounts: number;
  totalAccounts: number;
  visibleAssets: number;
  totalAssets: number;
}

export interface AuthStatus {
  profiles?: Profile[];
  activeProfileId?: string | null;
  configured: boolean;
  authenticated: boolean;
  timeoutSeconds: number;
  retryAfterSeconds?: number;
  recoveryKeyConfigured?: boolean;
  me?: Me | null;
}

export interface SecurityStatus {
  recoveryKeyConfigured: boolean;
  recoveryKeyCreatedAt: string | null;
  passwordChangedAt: string | null;
}

export interface RecoveryRequestResult extends AuthSession {
  recoveryKey: string;
}

export interface SecurityEvent {
  type: string;
  message: string;
  at: string;
}

export interface AuthSession {
  token: string;
  expiresIn: number;
  profileId?: string;
}

export interface RecurrenceOccurrence {
  id: number;
  recurrenceId: number | null;
  date: string;
  originalDate: string;
  shifted: boolean;
  edited: boolean;
  label: string;
  category: string;
  amount: number;
  direction: string;
  accountId: number | null;
  accountName: string;
  frequency: string;
  status: string;
  statusLabel: string;
  reconciled: boolean;
  canEdit: boolean;
  canShift: boolean;
  canDelete: boolean;
  canRestore: boolean;
  lockReason: string;
}

export interface RecurrenceOccurrencesSnapshot {
  referenceDate: string;
  items: RecurrenceOccurrence[];
  total: number;
  counts: Record<string, number>;
}

export interface RecurrenceOccurrenceActionResult {
  success: boolean;
  message: string;
  updatedCount?: number;
}

export interface BackupCounts {
  accounts?: number;
  assets?: number;
  transactions?: number;
  users?: number;
  budgets?: number;
}

export interface BackupInfo extends BackupCounts {
  name: string;
  size: number;
  modifiedAt: string;
  createdAt?: string;
  /** manual | pre-restore | pre-reset | legacy | unknown */
  kind: string;
  legacy?: boolean;
  damaged?: boolean;
}

export interface BackupList {
  backups: BackupInfo[];
  lastBackupAt: string | null;
  reminderDays: number;
}

export interface BackupFile {
  name: string;
  data: string;
  info?: BackupCounts & { createdAt: string };
}

export interface BackupInspection {
  backup: BackupCounts & { createdAt?: string; kind?: string; legacy: boolean; verified: boolean };
  current: BackupCounts;
}

export interface RuleSuggestion {
  key: string;
  matchValue: string;
  category: string;
  categoryId: number;
  transactionType: "Débit" | "Crédit" | null;
  support: number;
  agreeing: number;
  reliability: number;
  recommended: boolean;
  matches: number;
}

export interface RuleSuggestionsSnapshot {
  suggestions: RuleSuggestion[];
  discardedCount: number;
  minReliability: number;
  totalMatches: number;
}

export interface RuleSuggestionPreviewRow {
  id: number;
  date: string;
  label: string;
  amount: number;
  account: string;
}

export interface RuleSuggestionApplyItem {
  match_value: string;
  target_category_id: number;
  transaction_type: string | null;
  transaction_ids: number[];
}

export interface RuleSuggestionApplyResult {
  success: boolean;
  created: number;
  classified: number;
  message: string;
}
