import { useEffect, useState } from "react";

import { getDashboard, getHealth } from "./api/client";
import type { DashboardSnapshot } from "./api/contracts";
import { BudgetPanel } from "./components/BudgetPanel";
import { ForecastChart } from "./components/ForecastChart";
import { KpiCard } from "./components/KpiCard";
import { Sidebar } from "./components/Sidebar";

type LoadState =
  | { status: "loading" }
  | { status: "ready"; snapshot: DashboardSnapshot }
  | { status: "error"; message: string };

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

export function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [apiOnline, setApiOnline] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    Promise.all([getHealth(controller.signal), getDashboard(controller.signal)])
      .then(([, snapshot]) => {
        setApiOnline(true);
        setState({ status: "ready", snapshot });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setApiOnline(false);
        setState({
          status: "error",
          message: error instanceof Error ? error.message : "Le moteur Python ne répond pas.",
        });
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="workspace">
        <header className="module-header">
          <div>
            <span className="eyebrow">Vue d’ensemble</span>
            <h1>Bonjour</h1>
            <p>Votre situation financière, calculée par le moteur local Valoria Vision.</p>
          </div>
          <div className="header-actions">
            <span className={`api-status ${apiOnline ? "api-status--online" : ""}`}>
              <i aria-hidden="true" />
              {apiOnline ? "Moteur local connecté" : "Moteur local indisponible"}
            </span>
            <button type="button">Importer</button>
          </div>
        </header>

        {state.status === "loading" && (
          <section className="loading-state" aria-live="polite">
            <span />
            Connexion au moteur Python…
          </section>
        )}

        {state.status === "error" && (
          <section className="error-state" role="alert">
            <strong>Impossible d’afficher les données locales</strong>
            <p>{state.message}</p>
            <small>Démarrez l’API avec <code>python -m app.api.run</code>, puis actualisez cette page.</small>
          </section>
        )}

        {state.status === "ready" && <Dashboard snapshot={state.snapshot} />}
      </main>
    </div>
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
          <div className="panel-heading">
            <div>
              <h2>Trésorerie prévisionnelle</h2>
              <p>Projection issue du scénario réaliste</p>
            </div>
            <span className="badge">60 jours</span>
          </div>
          <ForecastChart points={snapshot.forecast} />
        </article>

        <article className="card panel">
          <div className="panel-heading">
            <div>
              <h2>Patrimoine</h2>
              <p>Répartition par famille</p>
            </div>
          </div>
          <div className="asset-panel">
            <div className="donut" style={{ background: assetGradient }}>
              <div><strong>{money.format(assetTotal)}</strong><span>€</span></div>
            </div>
            <ul>
              {snapshot.assets.slice(0, 5).map((item, index) => (
                <li key={item.label}>
                  <i className={`legend legend--${index % 5}`} />
                  <span>{item.label}</span>
                  <strong>{money.format(item.value)} €</strong>
                </li>
              ))}
            </ul>
          </div>
        </article>
      </section>

      <section className="dashboard-grid dashboard-grid--bottom">
        <article className="card panel">
          <div className="panel-heading">
            <div>
              <h2>Budget du mois</h2>
              <p>{snapshot.budget.month}</p>
            </div>
            <strong>{money.format(snapshot.budget.totalRealized)} €</strong>
          </div>
          <BudgetPanel rows={snapshot.budget.rows} />
        </article>

        <article className="card panel alerts-panel">
          <div className="panel-heading"><div><h2>Alertes utiles</h2><p>À surveiller</p></div></div>
          <ul>
            {snapshot.alerts.map((alert) => (
              <li className={`alert alert--${alert.level}`} key={`${alert.title}-${alert.detail}`}>
                <i aria-hidden="true" />
                <span><strong>{alert.title}</strong><small>{alert.detail}</small></span>
              </li>
            ))}
          </ul>
        </article>

        <article className="card panel confidence-panel">
          <div className="panel-heading"><div><h2>Qualité des données</h2><p>Lecture locale</p></div></div>
          <div className="confidence-score">100<span>%</span></div>
          <div className="confidence-track"><span /></div>
          <p>Les montants affichés proviennent directement du moteur Python.</p>
        </article>
      </section>
    </div>
  );
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
