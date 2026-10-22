import { useEffect, useRef, useState } from "react";

import type { BudgetsSnapshot } from "../api/contracts";
import { formatMoney, signedMoney } from "./budgetFormat";

interface BudgetsTrackingProps {
  isCurrentMonth: boolean;
  onOpenComparative: () => void;
  onRevise: (category: string) => void;
  snapshot: BudgetsSnapshot;
}

/** Onglet 1 : KPI et indicateurs pour suivre le budget du mois. */
export function BudgetsTracking({ isCurrentMonth, onOpenComparative, onRevise, snapshot }: BudgetsTrackingProps) {
  const { summary, tracking } = snapshot;
  const over = summary.overCount;
  const finished = !isCurrentMonth && tracking.elapsedDays >= tracking.daysInMonth;
  const projectionTone = tracking.projectionGap === null ? "" : tracking.projectionGap > 0 ? "bgt-bad" : "bgt-good";
  return (
    <div className="bgt-tab">
      <section aria-label="Indicateurs budgétaires" className="bgt-kpis">
        <article className="bgt-kpi">
          <span>Budget prévu</span>
          <strong>{formatMoney(summary.totalPlanned)}</strong>
          <small>{summary.categoryCount} catégories suivies</small>
        </article>
        <article className="bgt-kpi">
          <span>Réalisé</span>
          <strong>{formatMoney(summary.totalRealized)}</strong>
          <small className={summary.usageTotal > 100 ? "bgt-bad" : ""}>{summary.usageTotal.toLocaleString("fr-FR")} % du budget consommé</small>
        </article>
        <article className="bgt-kpi">
          <span>Reste à dépenser</span>
          <strong className={summary.totalRemaining < 0 ? "bgt-bad" : ""}>{formatMoney(Math.max(0, summary.totalRemaining))}</strong>
          <small>
            {summary.totalRemaining < 0
              ? `Budget dépassé de ${formatMoney(-summary.totalRemaining)}`
              : finished ? "Mois terminé"
                : tracking.perDay !== null ? `${tracking.daysLeft} jour${tracking.daysLeft > 1 ? "s" : ""} · ${formatMoney(tracking.perDay)} par jour` : `${tracking.daysLeft} jours restants`}
          </small>
        </article>
        <article className="bgt-kpi">
          <span>Projection fin de mois</span>
          <strong className={projectionTone}>{tracking.projection === null ? "—" : formatMoney(tracking.projection)}</strong>
          <small className={projectionTone} title={tracking.projectionMethod}>
            {tracking.projectionGap === null ? "Mois à venir" : `${signedMoney(tracking.projectionGap)} vs budget`}
          </small>
        </article>
        <article className="bgt-kpi">
          <span>En dépassement</span>
          <strong className={over > 0 ? "bgt-bad" : ""}>{over}<em> sur {summary.categoryCount}</em></strong>
          <small>{summary.warningCount > 0 ? `${summary.warningCount} autre${summary.warningCount > 1 ? "s" : ""} à surveiller` : "Aucune autre alerte"}</small>
        </article>
      </section>

      <section className="bgt-main">
        <article className="bgt-card">
          <div className="bgt-card__heading"><h2>Rythme du budget</h2><span>Budget cumulé comparé au réalisé cumulé, jour par jour</span></div>
          <RhythmChart snapshot={snapshot} />
          <div className="bgt-legend">
            <span><i className="bgt-legend__budget" />Budget cumulé</span>
            <span><i className="bgt-legend__actual" />Réalisé cumulé</span>
            {tracking.projection !== null && isCurrentMonth && <span><i className="bgt-legend__projection" />Projection</span>}
          </div>
        </article>

        <article className="bgt-card bgt-watch">
          <div className="bgt-card__heading"><h2>À surveiller</h2><span>Catégories hors budget ou proches du seuil</span></div>
          {tracking.watch.length === 0 && <p className="bgt-empty">Aucune catégorie à surveiller ce mois-ci.</p>}
          <ul>
            {tracking.watch.map((item) => (
              <li key={item.category}>
                <button onClick={() => onRevise(item.category)} type="button">
                  <div className="bgt-watch__line">
                    <strong>{item.category}</strong>
                    <b className={item.status === "Dépassement" || item.status === "Non budgété" ? "bgt-bad" : "bgt-warn"}>{formatMoney(item.actual)} / {item.planned > 0 ? formatMoney(item.planned) : "—"}</b>
                  </div>
                  <div className="bgt-watch__bar"><i className={item.status === "Dépassement" ? "is-over" : "is-warn"} style={{ width: `${Math.min(100, item.usage)}%` }} /></div>
                  <small>
                    {item.status}
                    {item.suggestRevision && <> · dépasse depuis {item.monthsOver} mois : <u>réviser ?</u></>}
                  </small>
                </button>
              </li>
            ))}
          </ul>
          <div className="bgt-watch__footer">
            <span>{tracking.watchOthers > 0 ? `+ ${tracking.watchOthers} autre${tracking.watchOthers > 1 ? "s" : ""} catégorie${tracking.watchOthers > 1 ? "s" : ""}` : ""}</span>
            <button className="bgt-link" onClick={onOpenComparative} type="button">Voir le comparatif →</button>
          </div>
        </article>
      </section>
    </div>
  );
}

function RhythmChart({ snapshot }: { snapshot: BudgetsSnapshot }) {
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 700, height: 260 });
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const update = () => setSize({ width: Math.max(element.clientWidth, 320), height: Math.max(element.clientHeight, 180) });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const { tracking, summary } = snapshot;
  const { width, height } = size;
  const left = 56;
  const right = width - 14;
  const top = 18;
  const bottom = height - 28;
  const days = tracking.curve.length;
  const last = [...tracking.curve].reverse().find((point) => point.actual !== null);
  const values = [summary.totalPlanned, ...tracking.curve.map((point) => point.actual ?? 0)];
  if (tracking.projection !== null) values.push(tracking.projection);
  const max = Math.max(...values, 1) * 1.08;
  const x = (day: number) => left + ((day - 1) / Math.max(1, days - 1)) * (right - left);
  const y = (value: number) => bottom - (value / max) * (bottom - top);
  const budgetPath = tracking.curve.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.day).toFixed(1)} ${y(point.budget).toFixed(1)}`).join(" ");
  const actualPoints = tracking.curve.filter((point) => point.actual !== null);
  const actualPath = actualPoints.map((point, index) => `${index === 0 ? "M" : "L"}${x(point.day).toFixed(1)} ${y(point.actual ?? 0).toFixed(1)}`).join(" ");
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((ratio) => ratio * max);
  const dayTicks = [1, 8, 15, 22, days].filter((day, index, all) => day <= days && all.indexOf(day) === index);
  const showProjection = last && tracking.projection !== null && last.day < days;
  return (
    <div className="bgt-chart-host" ref={host}>
      <svg aria-label="Budget cumulé et réalisé cumulé du mois" className="bgt-chart" role="img" viewBox={`0 0 ${width} ${height}`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line stroke="var(--s-e3e9f3)" x1={left} x2={right} y1={y(tick)} y2={y(tick)} />
            <text fill="var(--t-52627d)" fontSize="11" textAnchor="end" x={left - 8} y={y(tick) + 4}>{formatMoney(Math.round(tick / 50) * 50)}</text>
          </g>
        ))}
        {dayTicks.map((day) => <text fill="var(--t-52627d)" fontSize="11" key={day} textAnchor="middle" x={x(day)} y={height - 8}>{day}</text>)}
        <path d={budgetPath} fill="none" stroke="var(--s-94a3b8)" strokeDasharray="6 5" strokeWidth="2" />
        {actualPath && <path d={actualPath} fill="none" stroke="#2563eb" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />}
        {showProjection && last && (
          <path d={`M${x(last.day)} ${y(last.actual ?? 0)} L${x(days)} ${y(tracking.projection ?? 0)}`} fill="none" stroke="#dc2626" strokeDasharray="6 4" strokeWidth="2.4" />
        )}
        {last && (
          <g>
            <line stroke="var(--t-0f1b3a)" strokeWidth="1.2" x1={x(last.day)} x2={x(last.day)} y1={top} y2={bottom} />
            <circle cx={x(last.day)} cy={y(last.actual ?? 0)} fill="#fff" r="5" stroke="#2563eb" strokeWidth="3" />
            <text fill="var(--t-0f1b3a)" fontSize="11" fontWeight="700" x={Math.min(x(last.day) + 8, right - 80)} y={top + 10}>{tracking.elapsedDays < days ? "Aujourd’hui" : "Fin de mois"}</text>
          </g>
        )}
      </svg>
    </div>
  );
}
