import { useEffect, useState } from "react";

import { closeSession, getAuthStatus, getDashboard, getHealth, openSession } from "./api/client";
import type { DashboardSnapshot } from "./api/contracts";
import type { ForecastAccount } from "./api/contracts";
import type { ReconciliationAccount } from "./api/contracts";
import { AccountsPage } from "./components/AccountsPage";
import { AssetsPage } from "./components/AssetsPage";
import { AuthScreen } from "./components/AuthScreen";
import { BudgetsPage } from "./components/BudgetsPage";
import { Sidebar } from "./components/Sidebar";
import type { NavigationId } from "./components/Sidebar";
import { ForecastPage } from "./components/ForecastPage";
import { ReconciliationPage } from "./components/ReconciliationPage";
import { SettingsPage } from "./components/SettingsPage";
import { TransactionsPage } from "./components/TransactionsPage";
import type { TransactionsView } from "./components/TransactionsPage";

type AppState =
  | { status: "booting" }
  | { status: "locked"; configured: boolean; busy: boolean; error?: string }
  | { status: "ready"; snapshot: DashboardSnapshot; token: string }
  | { status: "error"; message: string };

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const moneyCode = new Intl.NumberFormat("fr-FR", {
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
  style: "currency",
});

interface ModuleDefinition {
  title: string;
  description: string;
}

const modules: Record<NavigationId, ModuleDefinition> = {
  dashboard: {
    title: "Bonjour François",
    description: "Vue synthétique du cash, des comptes et du patrimoine.",
  },
  accounts: {
    title: "Comptes bancaires",
    description: "Suivre les soldes, identifiants d’import et soldes de référence.",
  },
  transactions: {
    title: "Transactions",
    description: "Rechercher, catégoriser et valider les opérations importées.",
  },
  forecast: {
    title: "Prévisionnel de trésorerie",
    description: "Comparer le réalisé, les échéances prévues et les scénarios.",
  },
  budgets: {
    title: "Budgets",
    description: "Comparer le prévu, le réalisé et les écarts par catégorie.",
  },
  assets: {
    title: "Patrimoine",
    description: "Lire le patrimoine net, les familles d’actifs et leur évolution.",
  },
  reconciliation: {
    title: "Rapprochements",
    description: "Contrôler les correspondances entre prévisionnel et réalisé.",
  },
  settings: {
    title: "Paramètres",
    description: "Centraliser les règles, catégories, sauvegardes et préférences.",
  },
};

export function App() {
  const [state, setState] = useState<AppState>({ status: "booting" });
  const [activeModule, setActiveModule] = useState<NavigationId>("dashboard");
  const [accountStatusFilter, setAccountStatusFilter] = useState("Tous");
  const [forecastAccountId, setForecastAccountId] = useState("all");
  const [forecastAccounts, setForecastAccounts] = useState<ForecastAccount[]>([]);
  const [forecastHorizonDays, setForecastHorizonDays] = useState(90);
  const [forecastScenario, setForecastScenario] = useState("Réaliste");
  const [budgetMonth, setBudgetMonth] = useState("");
  const [budgetMonths, setBudgetMonths] = useState<string[]>([]);
  const [reconciliationAccountId, setReconciliationAccountId] = useState("all");
  const [reconciliationAccounts, setReconciliationAccounts] = useState<ReconciliationAccount[]>([]);
  const [reconciliationStatus, setReconciliationStatus] = useState("active");
  const [reconciliationRefreshKey, setReconciliationRefreshKey] = useState(0);
  const [transactionsView, setTransactionsView] = useState<TransactionsView>("journal");
  const [transactionImportRequestKey, setTransactionImportRequestKey] = useState(0);
  const [accountEditorRequestKey, setAccountEditorRequestKey] = useState(0);
  const [preferredImportAccountId, setPreferredImportAccountId] = useState<number>();

  useEffect(() => {
    const controller = new AbortController();
    waitForEngine(controller.signal)
      .then(() => getAuthStatus(controller.signal))
      .then((auth) => setState({ status: "locked", configured: auth.configured, busy: false }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: "error", message: errorMessage(error) });
        }
      });
    return () => controller.abort();
  }, []);

  async function authenticate(password: string) {
    if (state.status !== "locked") return;
    const configured = state.configured;
    setState({ status: "locked", configured, busy: true });
    try {
      const session = await openSession(password, configured);
      const snapshot = await getDashboard(session.token);
      setState({ status: "ready", snapshot, token: session.token });
    } catch (error: unknown) {
      setState({ status: "locked", configured, busy: false, error: errorMessage(error) });
    }
  }

  async function lock() {
    if (state.status !== "ready") return;
    const token = state.token;
    setState({ status: "locked", configured: true, busy: false });
    await closeSession(token).catch(() => undefined);
  }

  function openBankImport(accountId?: number) {
    setPreferredImportAccountId(accountId);
    setActiveModule("transactions");
    setTransactionsView("import");
    setTransactionImportRequestKey((key) => key + 1);
  }

  async function refreshDashboard() {
    if (state.status !== "ready") return;
    const snapshot = await getDashboard(state.token).catch(() => undefined);
    if (snapshot) setState({ status: "ready", snapshot, token: state.token });
  }

  if (state.status === "booting") {
    return <div className="splash-state"><span>V</span><p>Démarrage du moteur local…</p></div>;
  }

  if (state.status === "locked") {
    return <AuthScreen configured={state.configured} busy={state.busy} error={state.error} onSubmit={authenticate} />;
  }

  if (state.status === "error") {
    return (
      <main className="fatal-state">
        <strong>Le moteur local ne peut pas démarrer</strong>
        <p>{state.message}</p>
        <small>En développement, lancez <code>python -m app.api.run</code> puis actualisez.</small>
      </main>
    );
  }

  const module = activeModule === "transactions" && transactionsView !== "journal"
    ? {
        title: transactionsView === "history" ? "Lots d’import" : "Imports bancaires",
        description: transactionsView === "history"
          ? "Consulter les derniers relevés traités localement."
          : "Importer un fichier local, prévisualiser puis valider.",
      }
    : modules[activeModule];

  return (
    <div className="app-shell">
      <Sidebar active={activeModule} onLock={lock} onNavigate={setActiveModule} />
      <main className="workspace">
        <header className="module-header">
          <div>
            <h1>{module.title}</h1>
            <p>{module.description}</p>
          </div>
          <HeaderActions
            activeModule={activeModule}
            accountStatusFilter={accountStatusFilter}
            dashboard={state.snapshot}
            budgetMonth={budgetMonth}
            budgetMonths={budgetMonths}
            forecastAccountId={forecastAccountId}
            forecastAccounts={forecastAccounts}
            forecastHorizonDays={forecastHorizonDays}
            onAccountStatusChange={setAccountStatusFilter}
            onAddAccount={() => setAccountEditorRequestKey((key) => key + 1)}
            onBudgetMonthChange={setBudgetMonth}
            onForecastAccountChange={setForecastAccountId}
            onForecastHorizonChange={setForecastHorizonDays}
            onOpenTransactionImport={() => openBankImport()}
            onReconciliationAccountChange={setReconciliationAccountId}
            onReconciliationRefresh={() => setReconciliationRefreshKey((key) => key + 1)}
            onReconciliationStatusChange={setReconciliationStatus}
            reconciliationAccountId={reconciliationAccountId}
            reconciliationAccounts={reconciliationAccounts}
            reconciliationStatus={reconciliationStatus}
            transactionView={transactionsView}
            onTransactionViewChange={setTransactionsView}
          />
        </header>
        <div className="workspace-content">
          {activeModule === "dashboard" && <Dashboard snapshot={state.snapshot} />}
          {activeModule === "accounts" && (
            <AccountsPage
              editorRequestKey={accountEditorRequestKey}
              onAccountChanged={() => void refreshDashboard()}
              onAttachImport={openBankImport}
              statusFilter={accountStatusFilter}
              token={state.token}
            />
          )}
          {activeModule === "transactions" && (
            <TransactionsPage
              importRequestKey={transactionImportRequestKey}
              onImportCompleted={() => void refreshDashboard()}
              onNavigateSettings={() => setActiveModule("settings")}
              onViewChange={setTransactionsView}
              preferredImportAccountId={preferredImportAccountId}
              token={state.token}
              view={transactionsView}
            />
          )}
          {activeModule === "forecast" && (
            <ForecastPage
              accountId={forecastAccountId}
              horizonDays={forecastHorizonDays}
              onAccountsChange={setForecastAccounts}
              onScenarioChange={setForecastScenario}
              scenario={forecastScenario}
              token={state.token}
            />
          )}
          {activeModule === "budgets" && <BudgetsPage month={budgetMonth} onMonthChange={setBudgetMonth} onMonthsChange={setBudgetMonths} token={state.token} />}
          {activeModule === "assets" && <AssetsPage token={state.token} />}
          {activeModule === "reconciliation" && (
            <ReconciliationPage
              accountId={reconciliationAccountId}
              onAccountsChange={setReconciliationAccounts}
              refreshKey={reconciliationRefreshKey}
              status={reconciliationStatus}
              token={state.token}
            />
          )}
          {activeModule === "settings" && <SettingsPage onNavigate={setActiveModule} token={state.token} />}
          {activeModule !== "dashboard" && activeModule !== "accounts" && activeModule !== "transactions" && activeModule !== "forecast" && activeModule !== "budgets" && activeModule !== "assets" && activeModule !== "reconciliation" && activeModule !== "settings" && <ModulePlaceholder module={module} />}
        </div>
      </main>
    </div>
  );
}

function HeaderActions({
  accountStatusFilter,
  activeModule,
  budgetMonth,
  budgetMonths,
  dashboard,
  forecastAccountId,
  forecastAccounts,
  forecastHorizonDays,
  onAccountStatusChange,
  onAddAccount,
  onBudgetMonthChange,
  onForecastAccountChange,
  onForecastHorizonChange,
  onOpenTransactionImport,
  onReconciliationAccountChange,
  onReconciliationRefresh,
  onReconciliationStatusChange,
  reconciliationAccountId,
  reconciliationAccounts,
  reconciliationStatus,
  transactionView,
  onTransactionViewChange,
}: {
  accountStatusFilter: string;
  activeModule: NavigationId;
  budgetMonth: string;
  budgetMonths: string[];
  dashboard: DashboardSnapshot;
  forecastAccountId: string;
  forecastAccounts: ForecastAccount[];
  forecastHorizonDays: number;
  onAccountStatusChange: (value: string) => void;
  onAddAccount: () => void;
  onBudgetMonthChange: (value: string) => void;
  onForecastAccountChange: (value: string) => void;
  onForecastHorizonChange: (value: number) => void;
  onOpenTransactionImport: () => void;
  onReconciliationAccountChange: (value: string) => void;
  onReconciliationRefresh: () => void;
  onReconciliationStatusChange: (value: string) => void;
  reconciliationAccountId: string;
  reconciliationAccounts: ReconciliationAccount[];
  reconciliationStatus: string;
  transactionView: TransactionsView;
  onTransactionViewChange: (view: TransactionsView) => void;
}) {
  if (activeModule === "dashboard") {
    return (
      <div className="header-actions">
        <button className="secondary-button" type="button">Tous les comptes</button>
        <button className="secondary-button" type="button">{formatPeriod(dashboard.period)}</button>
        <button onClick={onOpenTransactionImport} type="button">Importer</button>
      </div>
    );
  }
  if (activeModule === "accounts") {
    return (
      <div className="header-actions">
        <button onClick={onAddAccount} type="button">Ajouter un compte</button>
        <select aria-label="Filtrer les comptes par statut" onChange={(event) => onAccountStatusChange(event.target.value)} value={accountStatusFilter}>
          <option>Tous</option>
          <option>Actif</option>
          <option>Archivé</option>
          <option>Clos</option>
        </select>
      </div>
    );
  }
  if (activeModule === "transactions") {
    if (transactionView === "import") {
      return (
        <div className="header-actions">
          <button className="secondary-button" onClick={() => onTransactionViewChange("history")} type="button">Historique</button>
          <button onClick={onOpenTransactionImport} type="button">Choisir un fichier</button>
        </div>
      );
    }
    if (transactionView === "history") {
      return (
        <div className="header-actions">
          <button className="secondary-button" onClick={() => onTransactionViewChange("journal")} type="button">Transactions</button>
          <button onClick={onOpenTransactionImport} type="button">Nouvel import</button>
        </div>
      );
    }
    return (
      <div className="header-actions">
        <button className="secondary-button" onClick={() => onTransactionViewChange("history")} type="button">Annuler un import</button>
        <button onClick={onOpenTransactionImport} type="button">Importer un relevé</button>
      </div>
    );
  }
  if (activeModule === "forecast") {
    return (
      <div className="header-actions">
        <select aria-label="Compte de la projection" onChange={(event) => onForecastAccountChange(event.target.value)} value={forecastAccountId}>
          <option value="all">Tous les comptes</option>
          {forecastAccounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} - ` : ""}{account.name}</option>)}
        </select>
        <select aria-label="Horizon de la projection" onChange={(event) => onForecastHorizonChange(Number(event.target.value))} value={forecastHorizonDays}>
          <option value={30}>30 jours</option>
          <option value={60}>60 jours</option>
          <option value={90}>90 jours</option>
        </select>
        <button aria-disabled="true" className="header-action-disabled" title="Création de récurrence prévue dans l’incrément d’édition" type="button">Nouvelle récurrence</button>
      </div>
    );
  }
  if (activeModule === "budgets") {
    return (
      <div className="header-actions">
        <select aria-label="Mois budgétaire" onChange={(event) => onBudgetMonthChange(event.target.value)} value={budgetMonth}>
          {!budgetMonth && <option value="">Mois courant</option>}
          {budgetMonths.map((month) => <option key={month} value={month}>{formatBudgetMonth(month)}</option>)}
        </select>
        <button aria-disabled="true" className="header-action-disabled" title="Création de budget prévue dans l’incrément d’édition" type="button">Nouveau budget</button>
      </div>
    );
  }
  if (activeModule === "assets") {
    return (
      <div className="header-actions">
        <button aria-disabled="true" className="header-action-disabled" title="Ajout d’actif prévu dans l’incrément d’écriture" type="button">Ajouter un actif</button>
        <button aria-disabled="true" className="secondary-button header-action-disabled" title="La synthèse patrimoniale est affichée sur cette page" type="button">Synthèse</button>
      </div>
    );
  }
  if (activeModule === "reconciliation") {
    return (
      <div className="header-actions">
        <select aria-label="Compte des rapprochements" onChange={(event) => onReconciliationAccountChange(event.target.value)} value={reconciliationAccountId}>
          <option value="all">Tous les comptes</option>
          {reconciliationAccounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} - ` : ""}{account.name}</option>)}
        </select>
        <select aria-label="Statut des rapprochements" onChange={(event) => onReconciliationStatusChange(event.target.value)} value={reconciliationStatus}>
          <option value="active">À traiter</option>
          <option value="to_review">À vérifier</option>
          <option value="partially_matched">Partielles</option>
          <option value="finalized">Finalisées</option>
          <option value="all">Tous les statuts</option>
        </select>
        <button onClick={onReconciliationRefresh} type="button">Actualiser</button>
      </div>
    );
  }
  if (activeModule === "settings") {
    return <div className="header-actions"><button form="settings-active-form" type="submit">Sauvegarder</button></div>;
  }
  return null;
}

function ModulePlaceholder({ module }: { module: ModuleDefinition }) {
  return (
    <section className="module-placeholder card" aria-live="polite">
      <span className="module-placeholder__mark" aria-hidden="true">V</span>
      <span className="eyebrow">Navigation opérationnelle</span>
      <h2>{module.title}</h2>
      <p>
        Cet espace est maintenant accessible. Son raccordement aux services métier Python
        sera réalisé dans le prochain incrément fonctionnel.
      </p>
      <div className="module-placeholder__status"><i aria-hidden="true" />Interface React active</div>
    </section>
  );
}

function Dashboard({ snapshot }: { snapshot: DashboardSnapshot }) {
  const kpis = new Map(snapshot.kpis.map((kpi) => [kpi.id, kpi]));
  const cash = kpis.get("cash")?.value ?? 0;
  const netWorth = kpis.get("net-worth")?.value ?? 0;
  const income = kpis.get("income")?.value ?? 0;
  const expenses = kpis.get("expenses")?.value ?? snapshot.budget.totalRealized;
  const savings = income - expenses;
  const expenseRows = snapshot.budget.rows.filter((row) => row.actual > 0).slice(0, 4);
  const expenseTotal = expenseRows.reduce((total, row) => total + row.actual, 0);
  const assetTotal = snapshot.assets.reduce((total, item) => total + item.value, 0);
  const budgetVariance = snapshot.budget.totalRealized - snapshot.budget.totalPlanned;
  const toProcess = snapshot.alerts.filter((alert) => alert.level === "warning" || alert.level === "critical").length
    + snapshot.budget.rows.filter((row) => row.usage > 100).length;
  const expenseGradient = buildGradient(expenseRows.map((row) => row.actual), ["#2563eb", "#06b6d4", "#f59e0b", "#dc2626"]);
  const assetGradient = buildGradient(snapshot.assets.map((item) => item.value), ["#2563eb", "#7c3aed", "#06b6d4", "#22c55e", "#f59e0b"]);
  const flowMaximum = Math.max(income, expenses, Math.abs(savings), 1);

  return (
    <div className="r8-dashboard">
      <section className="r8-kpi-grid" aria-label="Indicateurs principaux">
        <DashboardKpi label="Cash disponible" value={moneyCode.format(cash)} detail="Comptes courants et épargne" tone="cyan" />
        <DashboardKpi label="Patrimoine net" value={moneyCode.format(netWorth)} detail="Actifs moins passifs" tone="purple" />
        <DashboardKpi label="Dépenses mois" value={moneyCode.format(expenses)} detail={`${budgetVariance > 0 ? "+ " : ""}${moneyCode.format(budgetVariance)} vs budget`} tone="red" />
        <DashboardKpi label="À traiter" value={String(toProcess)} detail={`${snapshot.alerts.length} alerte(s) à surveiller`} tone="amber" />
      </section>

      <section className="r8-dashboard-main">
        <article className="card r8-panel r8-expenses-panel">
          <div className="panel-heading"><div><h2>Répartition des dépenses</h2><p>Dépenses du mois par catégorie.</p></div></div>
          <div className="r8-expenses-content">
            <Donut gradient={expenseGradient} primary={money.format(expenseTotal)} secondary="EUR" />
            <ul className="r8-legend-list">
              {expenseRows.map((row, index) => (
                <li key={row.category}><i className={`r8-dot r8-dot--${index}`} /><strong>{row.category}</strong><span>{moneyCode.format(row.actual)}</span></li>
              ))}
            </ul>
          </div>
          <span className={budgetVariance > 0 ? "r8-variance r8-variance--warning" : "r8-variance"}>{budgetVariance > 0 ? "+ " : ""}{moneyCode.format(budgetVariance)} vs budget</span>
        </article>
        <article className="card r8-panel r8-assets-panel">
          <div className="panel-heading"><div><h2>Patrimoine</h2><p>Actifs nets par famille.</p></div></div>
          <Donut gradient={assetGradient} primary={money.format(assetTotal / 1000)} secondary="kEUR" />
          <ul>
            {snapshot.assets.slice(0, 3).map((item) => <li key={item.label}><span>{item.label}</span><strong>{assetTotal ? Math.round((item.value / assetTotal) * 100) : 0} %</strong></li>)}
          </ul>
        </article>
        <article className="card r8-panel r8-flow-panel">
          <div className="panel-heading"><div><h2>Flux du mois</h2><p>Revenus, dépenses et épargne nette.</p></div></div>
          <FlowBar label="Revenus" maximum={flowMaximum} tone="green" value={income} />
          <FlowBar label="Dépenses" maximum={flowMaximum} tone="red" value={expenses} />
          <FlowBar label="Épargne nette" maximum={flowMaximum} tone="blue" value={savings} />
          <span className="category-chip">Flux hors transferts</span>
        </article>
      </section>

      <section className="r8-dashboard-bottom">
        <article className="card r8-panel r8-alerts-panel">
          <div className="panel-heading"><div><h2>Alertes utiles</h2></div></div>
          <ul>{snapshot.alerts.slice(0, 2).map((alert) => <li key={`${alert.title}-${alert.detail}`}><strong>{alert.title}</strong><small>{alert.detail}</small></li>)}</ul>
        </article>
        <article className="card r8-panel r8-quality-panel">
          <div className="panel-heading"><div><h2>Qualité données</h2></div></div>
          <span className="status-chip status-chip--success">100 % calculées localement</span>
          <div className="r8-quality-track"><span /></div>
          <p>{snapshot.budget.rows.length} catégorie(s) budgétaires analysée(s)</p>
        </article>
        <article className="card r8-panel r8-summary-panel">
          <div className="panel-heading"><div><h2>Synthèse rapide</h2></div></div>
          <dl>
            <div><dt>Cash disponible</dt><dd>{moneyCode.format(cash)}</dd></div>
            <div><dt>Patrimoine net</dt><dd>{moneyCode.format(netWorth)}</dd></div>
            <div><dt>Épargne nette</dt><dd>{moneyCode.format(savings)}</dd></div>
          </dl>
          <span className="category-chip category-chip--warning">Bêta en cours</span>
        </article>
      </section>
    </div>
  );
}

function DashboardKpi({ detail, label, tone, value }: { detail: string; label: string; tone: string; value: string }) {
  return (
    <article className="card r8-kpi">
      <div><span>{label}</span><i className={`r8-kpi-dot r8-kpi-dot--${tone}`} /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function Donut({ gradient, primary, secondary }: { gradient: string; primary: string; secondary: string }) {
  return (
    <div className="r8-donut" style={{ background: gradient }}>
      <div><strong>{primary}</strong><span>{secondary}</span></div>
    </div>
  );
}

function FlowBar({ label, maximum, tone, value }: { label: string; maximum: number; tone: string; value: number }) {
  const width = Math.max(0, Math.min(100, (Math.abs(value) / maximum) * 100));
  return (
    <div className="r8-flow-row">
      <div><strong>{label}</strong><span className={`r8-flow-value r8-flow-value--${tone}`}>{moneyCode.format(value)}</span></div>
      <div className="r8-flow-track"><span className={`r8-flow-fill r8-flow-fill--${tone}`} style={{ width: `${width}%` }} /></div>
    </div>
  );
}

function formatPeriod(period: string): string {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) return period;
  const result = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
  return result.charAt(0).toUpperCase() + result.slice(1);
}

function formatBudgetMonth(period: string): string {
  const [year, month] = period.split("-").map(Number);
  if (!year || !month) return period;
  const result = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
  return result.charAt(0).toUpperCase() + result.slice(1);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Le moteur Python ne répond pas.";
}

async function waitForEngine(signal: AbortSignal): Promise<void> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 40; attempt += 1) {
    try {
      await getHealth(signal);
      return;
    } catch (error: unknown) {
      if (signal.aborted) throw error;
      lastError = error;
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Le moteur local ne répond pas.");
}

function buildGradient(values: number[], colors: string[]): string {
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0);
  if (!total) return "#e2e8f0";
  let cursor = 0;
  const segments = values.map((value, index) => {
    const start = cursor;
    cursor += (Math.max(0, value) / total) * 100;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}
