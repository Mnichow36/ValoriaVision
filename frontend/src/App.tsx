import { useEffect, useState } from "react";

import { closeSession, getAuthStatus, getDashboard, getHealth, openSession } from "./api/client";
import type { DashboardSnapshot } from "./api/contracts";
import { AuthScreen } from "./components/AuthScreen";
import { BudgetPanel } from "./components/BudgetPanel";
import { ForecastChart } from "./components/ForecastChart";
import { KpiCard } from "./components/KpiCard";
import { Sidebar } from "./components/Sidebar";
import type { NavigationId } from "./components/Sidebar";

type AppState =
  | { status: "booting" }
  | { status: "locked"; configured: boolean; busy: boolean; error?: string }
  | { status: "ready"; snapshot: DashboardSnapshot; token: string }
  | { status: "error"; message: string };

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

interface ModuleDefinition {
  eyebrow: string;
  title: string;
  description: string;
}

const modules: Record<NavigationId, ModuleDefinition> = {
  dashboard: {
    eyebrow: "Vue d’ensemble",
    title: "Bonjour",
    description: "Votre situation financière, calculée par le moteur local Valoria Vision.",
  },
  accounts: {
    eyebrow: "Gestion financière",
    title: "Comptes",
    description: "Consultez et organisez vos comptes détenus localement.",
  },
  transactions: {
    eyebrow: "Gestion financière",
    title: "Transactions",
    description: "Analysez vos mouvements et préparez leur catégorisation.",
  },
  forecast: {
    eyebrow: "Projection",
    title: "Prévisionnel",
    description: "Projetez votre trésorerie selon vos scénarios locaux.",
  },
  budgets: {
    eyebrow: "Pilotage",
    title: "Budgets",
    description: "Suivez vos objectifs et vos consommations par catégorie.",
  },
  assets: {
    eyebrow: "Patrimoine",
    title: "Patrimoine",
    description: "Visualisez la composition et la valeur de votre patrimoine.",
  },
  reconciliation: {
    eyebrow: "Contrôle",
    title: "Rapprochements",
    description: "Contrôlez la cohérence entre comptes, mouvements et justificatifs.",
  },
  settings: {
    eyebrow: "Configuration",
    title: "Paramètres",
    description: "Configurez votre environnement local Valoria Vision.",
  },
};

export function App() {
  const [state, setState] = useState<AppState>({ status: "booting" });
  const [activeModule, setActiveModule] = useState<NavigationId>("dashboard");

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

  const module = modules[activeModule];

  return (
    <div className="app-shell">
      <Sidebar active={activeModule} onNavigate={setActiveModule} />
      <main className="workspace">
        <header className="module-header">
          <div>
            <span className="eyebrow">{module.eyebrow}</span>
            <h1>{module.title}</h1>
            <p>{module.description}</p>
          </div>
          <div className="header-actions">
            <span className="api-status api-status--online"><i aria-hidden="true" />Moteur local connecté</span>
            <button className="secondary-button" onClick={lock} type="button">Verrouiller</button>
          </div>
        </header>
        {activeModule === "dashboard"
          ? <Dashboard snapshot={state.snapshot} />
          : <ModulePlaceholder module={module} />}
      </main>
    </div>
  );
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
  const assetTotal = snapshot.assets.reduce((total, item) => total + item.value, 0);
  const assetGradient = snapshot.assets.length
    ? buildGradient(snapshot.assets.map((item) => item.value))
    : "#e8ecf6";

  return (
    <div className="dashboard">
      <section className="kpi-grid" aria-label="Indicateurs principaux">
        {snapshot.kpis.map((kpi) => <KpiCard key={kpi.id} kpi={kpi} />)}
      </section>

      <section className="dashboard-grid dashboard-grid--main">
        <article className="card panel panel--wide">
          <div className="panel-heading"><div><h2>Trésorerie prévisionnelle</h2><p>Projection issue du scénario réaliste</p></div><span className="badge">60 jours</span></div>
          <ForecastChart points={snapshot.forecast} />
        </article>
        <article className="card panel">
          <div className="panel-heading"><div><h2>Patrimoine</h2><p>Répartition par famille</p></div></div>
          <div className="asset-panel">
            <div className="donut" style={{ background: assetGradient }}><div><strong>{money.format(assetTotal)}</strong><span>€</span></div></div>
            <ul>{snapshot.assets.slice(0, 5).map((item, index) => <li key={item.label}><i className={`legend legend--${index % 5}`} /><span>{item.label}</span><strong>{money.format(item.value)} €</strong></li>)}</ul>
          </div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-grid--bottom">
        <article className="card panel">
          <div className="panel-heading"><div><h2>Budget du mois</h2><p>{snapshot.budget.month}</p></div><strong>{money.format(snapshot.budget.totalRealized)} €</strong></div>
          <BudgetPanel rows={snapshot.budget.rows} />
        </article>
        <article className="card panel alerts-panel">
          <div className="panel-heading"><div><h2>Alertes utiles</h2><p>À surveiller</p></div></div>
          <ul>{snapshot.alerts.map((alert) => <li className={`alert alert--${alert.level}`} key={`${alert.title}-${alert.detail}`}><i aria-hidden="true" /><span><strong>{alert.title}</strong><small>{alert.detail}</small></span></li>)}</ul>
        </article>
        <article className="card panel confidence-panel">
          <div className="panel-heading"><div><h2>Qualité des données</h2><p>Lecture locale</p></div></div>
          <div className="confidence-score">100<span>%</span></div><div className="confidence-track"><span /></div><p>Les montants affichés proviennent directement du moteur Python.</p>
        </article>
      </section>
    </div>
  );
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

function buildGradient(values: number[]): string {
  const colors = ["#5c78ff", "#51d5a4", "#9a72ef", "#58b9e8", "#f4b740"];
  const total = values.reduce((sum, value) => sum + Math.max(0, value), 0) || 1;
  let cursor = 0;
  const segments = values.map((value, index) => {
    const start = cursor;
    cursor += (Math.max(0, value) / total) * 100;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${segments.join(", ")})`;
}
