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
