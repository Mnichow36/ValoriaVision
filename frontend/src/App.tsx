import { useEffect, useState } from "react";

import { closeSession, getAuthStatus, getDashboard, getHealth, openSession } from "./api/client";
import type { DashboardSnapshot } from "./api/contracts";
import type { ForecastAccount } from "./api/contracts";
import { AccountsPage } from "./components/AccountsPage";
import { AssetsPage } from "./components/AssetsPage";
import { AuthScreen } from "./components/AuthScreen";
import { BudgetsPage } from "./components/BudgetsPage";
import { Sidebar } from "./components/Sidebar";
import type { NavigationId } from "./components/Sidebar";
import { ForecastPage } from "./components/ForecastPage";
import { SettingsPage } from "./components/SettingsPage";
import { TransactionsPage } from "./components/TransactionsPage";
import type { TransactionsView } from "./components/TransactionsPage";
import type { Profile } from "./api/contracts";
import { InteractiveDonutChart } from "./components/InteractiveCharts";

type AppState =
  | { status: "booting" }
  | { status: "locked"; busy: boolean; error?: string; retryAfter?: number; preferredProfileId?: string | null }
  | { status: "ready"; snapshot: DashboardSnapshot; token: string }
  | { status: "error"; message: string };

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
    description: "Suivre le budget, le comparer au réalisé, le réviser.",
  },
  assets: {
    title: "Patrimoine",
    description: "Lire le patrimoine net, les familles d’actifs et leur évolution.",
  },
  settings: {
    title: "Paramètres",
    description: "Centraliser les règles, catégories, sauvegardes et préférences.",
  },
};

export function App() {
  const [state, setState] = useState<AppState>({ status: "booting" });
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [activeProfileId, setActiveProfileId] = useState<string | null>(null);
  const [activeModule, setActiveModule] = useState<NavigationId>("dashboard");
  const [accountStatusFilter, setAccountStatusFilter] = useState("Actif");
  const [forecastAccountId, setForecastAccountId] = useState("all");
  const [forecastAccounts, setForecastAccounts] = useState<ForecastAccount[]>([]);
  const [forecastHorizonDays, setForecastHorizonDays] = useState(30);
  const [forecastScenario, setForecastScenario] = useState("Réaliste");
  const [forecastRecurrenceRequestKey, setForecastRecurrenceRequestKey] = useState(0);
  const [dashboardAccountId, setDashboardAccountId] = useState("all");
  const [dashboardMonth, setDashboardMonth] = useState("");
  const [budgetMonth, setBudgetMonth] = useState("");
  const [budgetMonths, setBudgetMonths] = useState<string[]>([]);
  const [reconciliationRefreshKey, setReconciliationRefreshKey] = useState(0);
  const [transactionsView, setTransactionsView] = useState<TransactionsView>("journal");
  const [recurrenceRuleRequestKey, setRecurrenceRuleRequestKey] = useState(0);
  const [transactionImportRequestKey, setTransactionImportRequestKey] = useState(0);
  const [transactionCreateRequestKey, setTransactionCreateRequestKey] = useState(0);
  const [accountEditorRequestKey, setAccountEditorRequestKey] = useState(0);
  const [assetEditorRequestKey, setAssetEditorRequestKey] = useState(0);
  const [preferredImportAccountId, setPreferredImportAccountId] = useState<number>();

  useEffect(() => {
    const controller = new AbortController();
    waitForEngine(controller.signal)
      .then(() => getAuthStatus(controller.signal))
      .then((auth) => {
        setProfiles(auth.profiles ?? []);
        setState({ status: "locked", busy: false, retryAfter: auth.retryAfterSeconds || undefined });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setState({ status: "error", message: errorMessage(error) });
        }
      });
    return () => controller.abort();
  }, []);

  async function refreshProfiles() {
    const auth = await getAuthStatus().catch(() => undefined);
    if (auth) setProfiles(auth.profiles ?? []);
    return auth;
  }

  async function authenticate(profileId: string, password: string) {
    if (state.status !== "locked") return;
    setState({ status: "locked", busy: true });
    try {
      const session = await openSession(profileId, password);
      const snapshot = await getDashboard(session.token);
      setActiveProfileId(session.profileId ?? profileId);
      void refreshProfiles();
      setState({ status: "ready", snapshot, token: session.token });
    } catch (error: unknown) {
      setState({ status: "locked", busy: false, error: errorMessage(error), retryAfter: (error as { retryAfter?: number }).retryAfter });
    }
  }

  async function openAfterRecovery(token: string) {
    try {
      const snapshot = await getDashboard(token);
      const auth = await refreshProfiles();
      setActiveProfileId(auth?.activeProfileId ?? null);
      setState({ status: "ready", snapshot, token });
    } catch (error: unknown) {
      setState({ status: "locked", busy: false, error: errorMessage(error) });
    }
  }

  async function lock(switchProfile = false) {
    if (state.status !== "ready") return;
    const token = state.token;
    setState({ status: "locked", busy: false, preferredProfileId: switchProfile ? null : activeProfileId });
    await closeSession(token).catch(() => undefined);
    void refreshProfiles();
  }

  // « reconciliation » n'est plus un module : c'est un onglet de Transactions.
  function navigate(destination: NavigationId | "reconciliation") {
    if (destination === "reconciliation") {
      setTransactionsView("reconciliation");
      setActiveModule("transactions");
      return;
    }
    if (destination === "transactions" && ["import", "history"].includes(transactionsView)) setTransactionsView("journal");
    setActiveModule(destination);
  }

  function openBankImport(accountId?: number) {
    setPreferredImportAccountId(accountId);
    setActiveModule("transactions");
    setTransactionsView("import");
    setTransactionImportRequestKey((key) => key + 1);
  }

  async function refreshDashboard(filters?: { accountId?: string; month?: string }) {
    if (state.status !== "ready") return;
    const snapshot = await getDashboard(state.token, filters ?? { accountId: dashboardAccountId, month: dashboardMonth }).catch(() => undefined);
    if (snapshot) setState({ status: "ready", snapshot, token: state.token });
  }

  function changeDashboardAccount(accountId: string) {
    setDashboardAccountId(accountId);
    void refreshDashboard({ accountId, month: dashboardMonth });
  }

  function changeDashboardMonth(month: string) {
    setDashboardMonth(month);
    void refreshDashboard({ accountId: dashboardAccountId, month });
  }

  if (state.status === "booting") {
    return <div className="splash-state"><span>V</span><p>Démarrage du moteur local…</p></div>;
  }

  if (state.status === "locked") {
    return <AuthScreen busy={state.busy} error={state.error} onProfilesChanged={async () => { await refreshProfiles(); }} onRecovered={openAfterRecovery} onUnlock={authenticate} preferredProfileId={state.preferredProfileId} profiles={profiles} retryAfter={state.retryAfter} />;
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

  const module = activeModule === "transactions"
    ? transactionsView === "reconciliation"
      ? { title: "Transactions", description: "Associer les transactions réelles aux prévisions attendues." }
      : transactionsView === "recurrences" || transactionsView === "rules"
      ? modules.transactions
      : transactionsView !== "journal"
        ? {
            title: transactionsView === "history" ? "Lots d’import" : "Imports bancaires",
            description: transactionsView === "history"
              ? "Consulter les derniers relevés traités localement."
              : "Importer un fichier local, prévisualiser puis valider.",
          }
        : modules.transactions
    : modules[activeModule];

  return (
    <div className="app-shell">
      <Sidebar active={activeModule} onLock={() => void lock()} onNavigate={navigate} onSwitchProfile={() => void lock(true)} profile={profiles.find((p) => p.id === activeProfileId) ?? null} />
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
            dashboardAccountId={dashboardAccountId}
            dashboardMonth={dashboardMonth}
            onDashboardAccountChange={changeDashboardAccount}
            onDashboardMonthChange={changeDashboardMonth}
            budgetMonth={budgetMonth}
            budgetMonths={budgetMonths}
            forecastAccountId={forecastAccountId}
            forecastAccounts={forecastAccounts}
            forecastHorizonDays={forecastHorizonDays}
            onAccountStatusChange={setAccountStatusFilter}
            onAddAccount={() => setAccountEditorRequestKey((key) => key + 1)}
            onAddAsset={() => setAssetEditorRequestKey((key) => key + 1)}
            onBudgetMonthChange={setBudgetMonth}
            onForecastAccountChange={setForecastAccountId}
            onForecastHorizonChange={setForecastHorizonDays}
            onCreateRecurrence={() => setForecastRecurrenceRequestKey((key) => key + 1)}
            onOpenTransactionImport={() => openBankImport()}
            onCreateTransaction={() => setTransactionCreateRequestKey((key) => key + 1)}
            onCreateRecurrenceRule={() => setRecurrenceRuleRequestKey((key) => key + 1)}
            transactionView={transactionsView}
            onTransactionViewChange={setTransactionsView}
          />
        </header>
        <div className="workspace-content">
          {activeModule === "dashboard" && <Dashboard onImport={() => openBankImport()} onNavigate={navigate} snapshot={state.snapshot} />}
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
              createRequestKey={transactionCreateRequestKey}
              importRequestKey={transactionImportRequestKey}
              onDataChanged={() => {
                void refreshDashboard();
                setReconciliationRefreshKey((key) => key + 1);
              }}
              onNavigateSettings={() => setActiveModule("settings")}
              onViewChange={setTransactionsView}
              reconciliationBadge={state.snapshot.quality?.reconciliationPending ?? 0}
              reconciliationRefreshKey={reconciliationRefreshKey}
              preferredImportAccountId={preferredImportAccountId}
              ruleCreateRequestKey={recurrenceRuleRequestKey}
              token={state.token}
              view={transactionsView}
            />
          )}
          {activeModule === "forecast" && (
            <ForecastPage
              accountId={forecastAccountId}
              editorRequestKey={forecastRecurrenceRequestKey}
              horizonDays={forecastHorizonDays}
              onAccountsChange={setForecastAccounts}
              onDataChanged={() => {
                void refreshDashboard();
                setReconciliationRefreshKey((key) => key + 1);
              }}
              onOpenRecurrences={() => {
                setTransactionsView("recurrences");
                setActiveModule("transactions");
              }}
              onScenarioChange={setForecastScenario}
              scenario={forecastScenario}
              token={state.token}
            />
          )}
          {activeModule === "budgets" && <BudgetsPage month={budgetMonth} onMonthChange={setBudgetMonth} onMonthsChange={setBudgetMonths} token={state.token} />}
          {activeModule === "assets" && <AssetsPage editorRequestKey={assetEditorRequestKey} onDataChanged={() => void refreshDashboard()} token={state.token} />}
          {activeModule === "settings" && <SettingsPage onNavigate={navigate} onProfileChanged={() => void refreshProfiles()} profile={profiles.find((p) => p.id === activeProfileId) ?? null} token={state.token} />}
          {activeModule !== "dashboard" && activeModule !== "accounts" && activeModule !== "transactions" && activeModule !== "forecast" && activeModule !== "budgets" && activeModule !== "assets" && activeModule !== "settings" && <ModulePlaceholder module={module} />}
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
  dashboardAccountId,
  dashboardMonth,
  onDashboardAccountChange,
  onDashboardMonthChange,
  forecastAccountId,
  forecastAccounts,
  forecastHorizonDays,
  onAccountStatusChange,
  onAddAccount,
  onAddAsset,
  onBudgetMonthChange,
  onForecastAccountChange,
  onForecastHorizonChange,
  onCreateRecurrence,
  onOpenTransactionImport,
  onCreateTransaction,
  onCreateRecurrenceRule,
  transactionView,
  onTransactionViewChange,
}: {
  accountStatusFilter: string;
  activeModule: NavigationId;
  budgetMonth: string;
  budgetMonths: string[];
  dashboard: DashboardSnapshot;
  dashboardAccountId: string;
  dashboardMonth: string;
  onDashboardAccountChange: (value: string) => void;
  onDashboardMonthChange: (value: string) => void;
  forecastAccountId: string;
  forecastAccounts: ForecastAccount[];
  forecastHorizonDays: number;
  onAccountStatusChange: (value: string) => void;
  onAddAccount: () => void;
  onAddAsset: () => void;
  onBudgetMonthChange: (value: string) => void;
  onForecastAccountChange: (value: string) => void;
  onForecastHorizonChange: (value: number) => void;
  onCreateRecurrence: () => void;
  onOpenTransactionImport: () => void;
  onCreateTransaction: () => void;
  onCreateRecurrenceRule: () => void;
  transactionView: TransactionsView;
  onTransactionViewChange: (view: TransactionsView) => void;
}) {
  if (activeModule === "dashboard") {
    return (
      <div className="header-actions">
        <select aria-label="Compte du tableau de bord" onChange={(event) => onDashboardAccountChange(event.target.value)} value={dashboardAccountId}>
          <option value="all">Tous les comptes</option>
          {(dashboard.accounts ?? []).map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
        </select>
        <select aria-label="Mois du tableau de bord" onChange={(event) => onDashboardMonthChange(event.target.value)} value={dashboardMonth || dashboard.period}>
          {(dashboard.months ?? [dashboard.period]).map((month) => <option key={month} value={month}>{formatPeriod(month)}</option>)}
        </select>
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
    if (transactionView === "reconciliation") {
      return (
        <div className="header-actions">
          <button onClick={onOpenTransactionImport} type="button">Importer un relevé</button>
        </div>
      );
    }
    if (transactionView === "recurrences" || transactionView === "rules") {
      return (
        <div className="header-actions">
          {transactionView === "rules" && <button className="secondary-button" onClick={onCreateRecurrenceRule} type="button">Nouvelle récurrence</button>}
          <button onClick={onOpenTransactionImport} type="button">Importer un relevé</button>
        </div>
      );
    }
    return (
      <div className="header-actions">
        <button className="secondary-button" onClick={() => onTransactionViewChange("history")} type="button">Annuler un import</button>
        <button className="secondary-button" onClick={onCreateTransaction} type="button">Nouvelle transaction</button>
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
        <div aria-label="Horizon de la projection" className="segmented" role="group">
          {[[15, "15 j"], [30, "30 j"], [90, "3 mois"], [365, "12 mois"]].map(([days, label]) => (
            <button aria-pressed={forecastHorizonDays === days} className={forecastHorizonDays === days ? "segmented__item segmented__item--active" : "segmented__item"} key={days} onClick={() => onForecastHorizonChange(days as number)} type="button">{label}</button>
          ))}
        </div>
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
      </div>
    );
  }
  if (activeModule === "assets") {
    return (
      <div className="header-actions">
        <button onClick={onAddAsset} type="button">Ajouter un actif</button>
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

/**
 * Keeps every item in the chart so the slices always add up to the announced
 * total: the largest items first, the smallest ones grouped under "Autres".
 */
function groupSlices(items: { label: string; value: number }[], palette: string[], maxSlices = 6) {
  const sorted = [...items].sort((left, right) => right.value - left.value);
  const kept = sorted.length > maxSlices ? sorted.slice(0, maxSlices - 1) : sorted;
  const rest = sorted.length > maxSlices ? sorted.slice(maxSlices - 1) : [];
  const slices = rest.length > 0
    ? [...kept, { label: "Autres", value: rest.reduce((total, item) => total + item.value, 0) }]
    : kept;
  return slices.map((item, index) => ({ ...item, color: palette[index % palette.length] }));
}

function Dashboard({ onImport, onNavigate, snapshot }: { onImport: () => void; onNavigate: (module: NavigationId | "reconciliation") => void; snapshot: DashboardSnapshot }) {
  const kpis = new Map(snapshot.kpis.map((kpi) => [kpi.id, kpi]));
  const cash = kpis.get("cash")?.value ?? 0;
  const netWorth = kpis.get("net-worth")?.value ?? 0;
  const income = kpis.get("income")?.value ?? 0;
  const expenses = kpis.get("expenses")?.value ?? snapshot.budget.totalRealized;
  const savings = income - expenses;
  const expenseRows = snapshot.expensesByCategory
    ?? snapshot.budget.rows.filter((row) => row.actual > 0).map((row) => ({ label: row.category, value: row.actual }));
  const expenseTotal = expenseRows.reduce((total, row) => total + row.value, 0);
  const assetTotal = snapshot.assets.reduce((total, item) => total + item.value, 0);
  const comparable = snapshot.budgetComparable ?? true;
  const budgetVariance = snapshot.budget.totalRealized - snapshot.budget.totalPlanned;
  const toProcess = snapshot.toProcess ?? snapshot.alerts.filter((alert) => alert.level === "warning" || alert.level === "critical").length;
  const filtered = snapshot.filters?.accountId != null;
  const expenseSlices = groupSlices(
    expenseRows.map((row) => ({ label: row.label, value: row.value })),
    ["#2563eb", "#06b6d4", "#f59e0b", "#dc2626", "#7c3aed", "var(--s-64748b)"],
  );
  const assetSlices = groupSlices(
    snapshot.assets.filter((item) => item.value > 0).map((item) => ({ label: item.label, value: item.value })),
    ["#2563eb", "#7c3aed", "#06b6d4", "#22c55e", "#f59e0b", "var(--s-64748b)"],
  );
  const flowMaximum = Math.max(income, expenses, Math.abs(savings), 1);
  const quality = snapshot.quality;
  const varianceLabel = comparable ? `${budgetVariance > 0 ? "+ " : ""}${moneyCode.format(budgetVariance)} vs budget` : "Compte seul · budget global non comparable";

  return (
    <div className="r8-dashboard">
      <section className="r8-kpi-grid" aria-label="Indicateurs principaux">
        <DashboardKpi label="Cash disponible" value={moneyCode.format(cash)} detail={filtered ? "Solde du compte sélectionné" : "Comptes courants et épargne"} tone="cyan" />
        <DashboardKpi label="Patrimoine net" value={moneyCode.format(netWorth)} detail="Actifs moins passifs (global)" tone="purple" />
        <DashboardKpi label="Dépenses mois" value={moneyCode.format(expenses)} detail={varianceLabel} tone="red" />
        <DashboardKpi label="À traiter" value={String(toProcess)} detail={toProcess > 0 ? "Voir les alertes en bas de page" : "Rien à signaler"} tone="amber" />
      </section>

      <section className="r8-dashboard-main">
        <article className="card r8-panel r8-expenses-panel">
          <div className="panel-heading"><div><h2>Répartition des dépenses</h2><p>{formatPeriod(snapshot.period)} · total {moneyCode.format(expenseTotal)}.</p></div></div>
          <div className="r8-expenses-content r8-expenses-content--interactive">
            <InteractiveDonutChart ariaLabel="Répartition des dépenses par catégorie" slices={expenseSlices} valueFormatter={(value) => moneyCode.format(value)} />
          </div>
          {comparable && <span className={budgetVariance > 0 ? "r8-variance r8-variance--warning" : "r8-variance"}>{varianceLabel}</span>}
        </article>
        <article className="card r8-panel r8-assets-panel">
          <div className="panel-heading"><div><h2>Patrimoine</h2><p>Total des actifs · {moneyCode.format(assetTotal)} · tous comptes.</p></div></div>
          <InteractiveDonutChart ariaLabel="Répartition du patrimoine par famille" slices={assetSlices} valueFormatter={(value) => moneyCode.format(value)} />
        </article>
        <article className="card r8-panel r8-flow-panel">
          <div className="panel-heading"><div><h2>Flux du mois</h2><p>Revenus, dépenses et épargne nette · hors transferts.</p></div></div>
          <FlowBar label="Revenus" maximum={flowMaximum} tone="green" value={income} />
          <FlowBar label="Dépenses" maximum={flowMaximum} tone="red" value={expenses} />
          <FlowBar label="Épargne nette" maximum={flowMaximum} tone="blue" value={savings} />
        </article>
      </section>

      <section className="r8-dashboard-bottom">
        <article className="card r8-panel r8-alerts-panel">
          <div className="panel-heading"><div><h2>Alertes utiles</h2></div>{toProcess > 0 && <span className="dash-count">{toProcess}</span>}</div>
          <ul>
            {snapshot.alerts.slice(0, 4).map((alert) => (
              <li className={`dash-alert dash-alert--${alert.level}`} key={`${alert.title}-${alert.detail}`}>
                <button disabled={!alert.target} onClick={() => alert.target && onNavigate(alert.target)} type="button">
                  <span><strong>{alert.title}</strong><small>{alert.detail}</small></span>
                  {alert.target && <b>{DASH_TARGETS[alert.target]} ›</b>}
                </button>
              </li>
            ))}
          </ul>
        </article>
        <article className="card r8-panel r8-quality-panel">
          <div className="panel-heading"><div><h2>Qualité des données</h2><p>Ce qu’il reste à traiter pour des chiffres fiables.</p></div></div>
          {quality ? (
            <>
              <div className="dash-quality__rate"><span>Transactions catégorisées</span><b className={quality.categorizedPercent >= 95 ? "bgt-good" : quality.categorizedPercent >= 80 ? "bgt-warn" : "bgt-bad"}>{quality.categorizedPercent.toLocaleString("fr-FR")} %</b></div>
              <div className="r8-quality-track"><span style={{ width: `${Math.min(100, quality.categorizedPercent)}%` }} /></div>
              <div className="dash-rows">
                <button onClick={() => onNavigate("transactions")} type="button"><span>À catégoriser</span><b>{quality.uncategorized} ›</b></button>
                <button onClick={() => onNavigate("reconciliation")} type="button"><span>Rapprochements en attente</span><b>{quality.reconciliationPending} ›</b></button>
                <button onClick={onImport} type="button"><span>Dernier import</span><b>{quality.lastImport ? (quality.daysSinceImport === 0 ? "aujourd’hui" : `il y a ${quality.daysSinceImport} j`) : "aucun"} ›</b></button>
              </div>
            </>
          ) : <p className="bgt-empty">Indicateurs indisponibles.</p>}
        </article>
        <article className="card r8-panel r8-upcoming-panel">
          <div className="panel-heading"><div><h2>Prochaines échéances</h2><p>Les 5 prochains mouvements prévus.</p></div><button className="bgt-link" onClick={() => onNavigate("forecast")} type="button">Prévisionnel ›</button></div>
          {(snapshot.upcoming ?? []).length === 0 && <p className="bgt-empty">Aucun mouvement prévu prochainement.</p>}
          <ul className="dash-upcoming">
            {(snapshot.upcoming ?? []).map((item, index) => (
              <li key={`${item.date}-${item.label}-${index}`}>
                <span>{item.date.slice(8, 10)}/{item.date.slice(5, 7)}</span>
                <strong title={item.label}>{item.label}</strong>
                <b className={item.amount >= 0 ? "bgt-good" : ""}>{item.amount > 0 ? "+ " : item.amount < 0 ? "- " : ""}{moneyCode.format(Math.abs(item.amount))}</b>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  );
}

const DASH_TARGETS: Record<string, string> = {
  budgets: "Budgets",
  forecast: "Prévisionnel",
  transactions: "Transactions",
  reconciliation: "Rapprochements",
};

function DashboardKpi({ detail, label, tone, value }: { detail: string; label: string; tone: string; value: string }) {
  return (
    <article className="card r8-kpi">
      <div><span>{label}</span><i className={`r8-kpi-dot r8-kpi-dot--${tone}`} /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
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
