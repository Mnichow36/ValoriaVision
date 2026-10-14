import { useEffect, useMemo, useState } from "react";

import { getForecast } from "../api/client";
import type { ForecastAccount, ForecastEvent, ForecastPoint, ForecastSnapshot } from "../api/contracts";

interface ForecastPageProps {
  accountId: string;
  horizonDays: number;
  onAccountsChange: (accounts: ForecastAccount[]) => void;
  onScenarioChange: (scenario: string) => void;
  scenario: string;
  token: string;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function ForecastPage({ accountId, horizonDays, onAccountsChange, onScenarioChange, scenario, token }: ForecastPageProps) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getForecast(token, { accountId, horizonDays, scenario }, controller.signal)
      .then((data) => {
        setSnapshot(data);
        onAccountsChange(data.accounts);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "La projection ne peut pas être chargée.");
        }
      });
    return () => controller.abort();
  }, [accountId, horizonDays, onAccountsChange, refreshKey, scenario, token]);

  if (error) {
    return (
      <section className="error-state">
        <strong>Le prévisionnel ne peut pas être affiché.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Calcul de la projection par le moteur Python…</div>;
  }

  return (
    <div className="forecast-page">
      <article className="card forecast-projection">
        <div className="forecast-card-heading">
          <div><h2>Projection journalière</h2><p>Solde de départ + transactions réelles + occurrences prévues.</p></div>
          <div className="forecast-scenarios" role="tablist" aria-label="Scénario de projection">
            <ScenarioButton active={scenario === "Réaliste"} onClick={() => onScenarioChange("Réaliste")}>Réaliste</ScenarioButton>
            <ScenarioButton active={scenario === "Optimiste"} onClick={() => onScenarioChange("Optimiste")}>Optimiste</ScenarioButton>
          </div>
        </div>

        <ForecastChart snapshot={snapshot} />

        <div className="forecast-legend" aria-label="Légende du graphique">
          <span><i className="forecast-legend__dot forecast-legend__dot--selected" />Solde prévu</span>
          <span><i className="forecast-legend__dot forecast-legend__dot--realized" />Réalisé</span>
          <span><i className="forecast-legend__dot forecast-legend__dot--prudent" />Scénario prudent</span>
        </div>

        <div className="forecast-summary-cards">
          <ForecastSummaryCard
            badge={snapshot.summary.lowBalance >= 5000 ? "Cash stable" : snapshot.summary.alert}
            label="Point bas"
            meta={`Atteint le ${formatDate(snapshot.summary.lowDate)}`}
            tone={snapshot.summary.lowBalance >= 5000 ? "success" : "warning"}
            value={formatMoney(snapshot.summary.lowBalance)}
          />
          <ForecastSummaryCard
            badge={percentageChange(snapshot.summary.startingCash, snapshot.summary.endBalance)}
            label="Solde final"
            meta={`Projection au ${formatDate(snapshot.summary.endDate)}`}
            tone="blue"
            value={formatMoney(snapshot.summary.endBalance)}
          />
        </div>
      </article>

      <aside className="forecast-side">
        <article className="card forecast-upcoming">
          <div className="forecast-card-heading"><div><h2>Récurrences à venir</h2><p>Occurrences traçables par statut.</p></div></div>
          <div className="forecast-upcoming-list">
            {snapshot.upcoming.length > 0
              ? snapshot.upcoming.map((event, index) => <UpcomingEvent event={event} key={`${event.date}-${event.name}-${index}`} />)
              : <p className="forecast-empty">Aucune récurrence sur cette période.</p>}
          </div>
        </article>

        <article className="card forecast-reading">
          <div className="forecast-card-heading"><div><h2>Lecture immédiate</h2><p>Ce qui change sur la période.</p></div></div>
          <Metric label="Encaissements prévus" tone="positive" value={signedMoney(snapshot.summary.totalIn)} />
          <Metric label="Décaissements prévus" tone="negative" value={signedMoney(-snapshot.summary.totalOut)} />
          <Metric label="Écart vs scénario prudent" tone="blue" value={signedMoney(snapshot.summary.prudentDifference)} />
        </article>
      </aside>
    </div>
  );
}

function ScenarioButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button aria-selected={active} className={active ? "forecast-scenario forecast-scenario--active" : "forecast-scenario"} onClick={onClick} role="tab" type="button">{children}</button>;
}

function ForecastChart({ snapshot }: { snapshot: ForecastSnapshot }) {
  const geometry = useMemo(() => chartGeometry([
    snapshot.series.selected,
    snapshot.series.realized,
    snapshot.series.prudent,
  ]), [snapshot]);
  const selectedDots = geometry.selected.filter((_, index) => index % Math.max(1, Math.floor(geometry.selected.length / 6)) === 0 || index === geometry.selected.length - 1);

  return (
    <div className="forecast-chart-r8" aria-label={`Projection ${snapshot.filters.scenario} sur ${snapshot.filters.horizonDays} jours`} role="img">
      <svg viewBox="0 0 720 310">
        {[36, 104, 172, 240, 308].map((y) => <line className="forecast-grid-line" key={y} x1="30" x2="700" y1={y} y2={y} />)}
        <polyline className="forecast-line-r8 forecast-line-r8--prudent" points={geometry.prudent.map(pointPair).join(" ")} />
        <polyline className="forecast-line-r8 forecast-line-r8--realized" points={geometry.realized.map(pointPair).join(" ")} />
        <polyline className="forecast-line-r8 forecast-line-r8--selected" points={geometry.selected.map(pointPair).join(" ")} />
        {selectedDots.map((point, index) => <circle className="forecast-point-r8" cx={point.x} cy={point.y} key={index} r="5" />)}
      </svg>
    </div>
  );
}

function ForecastSummaryCard({ badge, label, meta, tone, value }: { badge: string; label: string; meta: string; tone: "blue" | "success" | "warning"; value: string }) {
  return (
    <section className="forecast-summary-card">
      <h3>{label}</h3>
      <strong>{value}</strong>
      <p>{meta}</p>
      <span className={`forecast-badge forecast-badge--${tone}`}>{badge}</span>
    </section>
  );
}

function UpcomingEvent({ event }: { event: ForecastEvent }) {
  const tone = event.amount > 0 ? "success" : event.category.toLocaleLowerCase("fr").includes("épargne") ? "cyan" : "warning";
  return (
    <div className="forecast-event">
      <div><strong>{event.name}</strong><span>{formatDate(event.date)} · {signedMoney(event.amount)}</span></div>
      <span className={`forecast-badge forecast-badge--${tone}`}>Prévue</span>
    </div>
  );
}

function Metric({ label, tone, value }: { label: string; tone: "blue" | "negative" | "positive"; value: string }) {
  return <div className="forecast-metric"><span>{label}</span><strong className={`forecast-metric__value forecast-metric__value--${tone}`}>{value}</strong></div>;
}

interface ChartCoordinate { x: number; y: number }

function chartGeometry(series: ForecastPoint[][]): { selected: ChartCoordinate[]; realized: ChartCoordinate[]; prudent: ChartCoordinate[] } {
  const values = series.flat().map((point) => point.balance);
  const minimum = values.length ? Math.min(...values) : 0;
  const maximum = values.length ? Math.max(...values) : 1;
  const padding = Math.max((maximum - minimum) * 0.1, 1);
  const minY = minimum - padding;
  const maxY = maximum + padding;
  const toCoordinates = (points: ForecastPoint[]) => points.map((point, index) => ({
    x: 32 + (points.length <= 1 ? 0 : (index / (points.length - 1)) * 666),
    y: 306 - ((point.balance - minY) / (maxY - minY)) * 266,
  }));
  return {
    selected: toCoordinates(series[0]),
    realized: toCoordinates(series[1]),
    prudent: toCoordinates(series[2]),
  };
}

function pointPair(point: ChartCoordinate): string {
  return `${point.x.toFixed(1)},${point.y.toFixed(1)}`;
}

function percentageChange(start: number, end: number): string {
  if (!start) return "Projection calculée";
  const change = ((end - start) / Math.abs(start)) * 100;
  return `${change >= 0 ? "+ " : "- "}${Math.abs(change).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

function signedMoney(value: number): string {
  if (value === 0) return formatMoney(value);
  return `${value > 0 ? "+ " : "- "}${formatMoney(Math.abs(value))}`;
}

function formatMoney(value: number): string {
  return currencyFormatter.format(value);
}

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}
