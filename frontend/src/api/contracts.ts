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

export interface TransactionAccount {
  id: number;
  name: string;
  bank: string;
  status: string;
}

export interface TransactionCategory {
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
  category: string;
  status: string;
  amount: number;
  type: string;
  source: string;
  importBatchId: number | null;
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

export interface ForecastAccount {
  id: number;
  name: string;
  bank: string;
  type: string;
}

export interface ForecastPoint {
  date: string;
  label: string;
  balance: number;
}

export interface ForecastEvent {
  date: string;
  name: string;
  category: string;
  amount: number;
  source: string;
  account: string;
  scenario: string;
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
