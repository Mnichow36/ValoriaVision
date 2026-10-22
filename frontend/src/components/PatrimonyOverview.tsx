import { useEffect, useMemo, useRef, useState } from "react";

import type { AssetCategoryInsight, AssetDebtInsight, AssetsSnapshot } from "../api/contracts";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", maximumFractionDigits: 0 });
const PALETTE: Record<string, string> = {
  "Immobilier": "#1e40af",
  "Liquidités": "#0891b2",
  "Placements financiers": "#d97706",
  "Assurance-vie": "#7c3aed",
  "Autres actifs": "#be185d",
  "Véhicules": "#475569",
};
const FALLBACK = ["#0f766e", "#65a30d", "#c2410c", "#4338ca", "#a16207"];

export function categoryColor(name: string, index: number): string {
  return PALETTE[name] ?? FALLBACK[index % FALLBACK.length];
}

export function formatDay(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("fr-FR").format(date);
}

function signedMoney(value: number): string {
  return `${value > 0 ? "+ " : value < 0 ? "- " : ""}${money.format(Math.abs(value))}`;
}

function percent(value: number | null, digits = 1): string {
  return value === null ? "—" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: digits })} %`;
}

function signedPercent(value: number | null): string {
  return value === null ? "" : `${value > 0 ? "+ " : value < 0 ? "- " : ""}${Math.abs(value).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

interface PatrimonyOverviewProps {
  onOpenCategory: (name: string) => void;
  onOpenDebt: (id: number) => void;
  snapshot: AssetsSnapshot;
}

export function PatrimonyOverview({ onOpenCategory, onOpenDebt, snapshot }: PatrimonyOverviewProps) {
  const { headline, summary } = snapshot;
  const change = headline?.change ?? null;
  const annual = headline?.annualReturn ?? null;
  const tone = change && change.amount < 0 ? "pat-negative" : "pat-positive";

  return (
    <div className="pat">
      <section aria-label="Indicateurs principaux" className="pat-top3">
        <article className="pat-kpi pat-kpi--net">
          <span>Patrimoine net</span>
          <strong>{money.format(summary.netWorth)}</strong>
          <small>{money.format(summary.totalAssets)} d’actifs − {money.format(summary.totalLiabilities)} de dettes</small>
        </article>
        <article className="pat-kpi">
          <span>Évolution sur 12 mois</span>
          {change ? (
            <>
              <div className={`pat-kpi__row ${tone}`}><strong>{signedMoney(change.amount)}</strong><b>{signedPercent(change.percent)}</b></div>
              <small>{change.complete ? `Entre le ${formatDay(change.fromDate)} et aujourd’hui` : `Depuis le ${formatDay(change.fromDate)} · ${change.months.toLocaleString("fr-FR")} mois d’historique`}</small>
            </>
          ) : (
            <>
              <strong className="pat-kpi__na">Non disponible</strong>
              <small>Historique inférieur à un mois.</small>
            </>
          )}
        </article>
        <article className="pat-kpi">
          <span>Rendement annuel moyen</span>
          {annual && annual.percent !== null ? (
            <>
              <div className="pat-kpi__row"><strong>{percent(annual.percent)}</strong><em>hors liquidités</em></div>
              <small>{annual.months >= 12 ? "12 mois glissants" : `Annualisé sur ${annual.months.toLocaleString("fr-FR")} mois`} · estimation</small>
            </>
          ) : (
            <>
              <strong className="pat-kpi__na">Non disponible</strong>
              <small>{annual?.reason || "Historique insuffisant."}</small>
            </>
          )}
        </article>
      </section>

      <section className="pat-main">
        <AllocationCard categories={snapshot.categories} onOpen={onOpenCategory} totalAssets={summary.totalAssets} />
        <EvolutionCard debts={snapshot.debts} onOpenDebt={onOpenDebt} snapshot={snapshot} />
      </section>
    </div>
  );
}

function AllocationCard({ categories, onOpen, totalAssets }: { categories: AssetCategoryInsight[]; onOpen: (name: string) => void; totalAssets: number }) {
  const [hovered, setHovered] = useState<string>();
  const active = categories.find((category) => category.name === hovered) ?? categories[0];
  const radius = 135;
  const circumference = 2 * Math.PI * radius;
  const total = categories.reduce((sum, category) => sum + category.value, 0) || 1;
  const segments = useMemo(() => {
    let cumulative = 0;
    return categories.map((category, index) => {
      const length = (category.value / total) * circumference;
      const segment = { category, color: categoryColor(category.name, index), length, offset: cumulative };
      cumulative += length;
      return segment;
    });
  }, [categories, circumference, total]);

  return (
    <article className="pat-card pat-allocation">
      <div className="pat-card__heading">
        <h2>Allocation des actifs</h2>
        <span>Survol : aperçu · Clic : ouvrir la catégorie</span>
      </div>
      {categories.length === 0 ? (
        <p className="pat-empty">Aucun actif à afficher. Utilise « Ajouter un actif » pour commencer.</p>
      ) : (
        <>
          <div className="pat-allocation__body">
            <div className="pat-donut">
              <svg aria-label={`Répartition des actifs : ${categories.map((category) => `${category.name} ${category.weight.toLocaleString("fr-FR")} %`).join(", ")}`} role="img" viewBox="0 0 340 340">
                <g transform="rotate(-90 170 170)">
                  {segments.map(({ category, color, length, offset }) => {
                    const isActive = category.name === active?.name;
                    return (
                      <circle
                        aria-label={`${category.name} : ${money.format(category.value)}`}
                        className="pat-donut__segment"
                        cx="170"
                        cy="170"
                        fill="none"
                        key={category.name}
                        onBlur={() => setHovered(undefined)}
                        onClick={() => onOpen(category.name)}
                        onFocus={() => setHovered(category.name)}
                        onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpen(category.name); } }}
                        onMouseEnter={() => setHovered(category.name)}
                        onMouseLeave={() => setHovered(undefined)}
                        r={radius}
                        role="button"
                        stroke={color}
                        strokeDasharray={`${Math.max(length - 3, 0.5)} ${circumference}`}
                        strokeDashoffset={-offset}
                        strokeWidth={isActive ? 56 : 46}
                        style={{ opacity: isActive ? 1 : 0.4 }}
                        tabIndex={0}
                      />
                    );
                  })}
                </g>
              </svg>
              <div className="pat-donut__center">
                <span>Actifs</span>
                <strong>{money.format(totalAssets)}</strong>
                <small>{categories.length} catégorie{categories.length > 1 ? "s" : ""}</small>
              </div>
            </div>
            <ul className="pat-legend">
              {segments.map(({ category, color }) => (
                <li key={category.name}>
                  <button
                    className={category.name === active?.name ? "is-active" : ""}
                    onBlur={() => setHovered(undefined)}
                    onClick={() => onOpen(category.name)}
                    onFocus={() => setHovered(category.name)}
                    onMouseEnter={() => setHovered(category.name)}
                    onMouseLeave={() => setHovered(undefined)}
                    type="button"
                  >
                    <i style={{ background: color }} />
                    <span>{category.name}<small>{category.weight.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % des actifs</small></span>
                    <b>{money.format(category.value)}</b>
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {active && (
            <div className="pat-preview" aria-live="polite">
              <div><small>{hovered ? "Survol" : "Catégorie principale"}</small><strong>{active.name}</strong></div>
              <div><small>Valeur</small><strong>{money.format(active.value)}</strong></div>
              <div><small>TRI</small><strong title={active.triReason}>{active.tri === null ? "non disponible" : percent(active.tri)}</strong></div>
              <div><small>Volatilité</small><strong title={active.volatilityReason}>{active.volatility === null ? "non disponible" : percent(active.volatility)}</strong></div>
            </div>
          )}
        </>
      )}
    </article>
  );
}

type Series = "net" | "assets" | "liabilities";

function EvolutionCard({ debts, onOpenDebt, snapshot }: { debts: AssetDebtInsight[]; onOpenDebt: (id: number) => void; snapshot: AssetsSnapshot }) {
  const [series, setSeries] = useState<Series>("net");
  const points = snapshot.evolution.map((point) => ({ date: point.date, value: series === "liabilities" ? Math.abs(point.liabilities) : point[series] }));
  const { summary } = snapshot;
  const debtRatio = summary.totalAssets ? (summary.totalLiabilities / summary.totalAssets) * 100 : 0;
  const labels: Record<Series, string> = { net: "Net", assets: "Actifs", liabilities: "Passifs" };

  return (
    <article className="pat-card pat-evolution">
      <div className="pat-card__heading">
        <h2>Évolution sur 12 mois</h2>
        <div aria-label="Série affichée" className="pat-toggle" role="group">
          {(Object.keys(labels) as Series[]).map((key) => (
            <button aria-pressed={series === key} className={series === key ? "is-active" : ""} key={key} onClick={() => setSeries(key)} type="button">{labels[key]}</button>
          ))}
        </div>
      </div>
      <EvolutionChart label={labels[series]} points={points} />
      <div className="pat-ratio">
        <div className="pat-card__heading pat-card__heading--small">
          <h3>Actifs et passifs</h3>
          <span>Taux d’endettement {debtRatio.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %</span>
        </div>
        <div aria-label={`Passifs : ${debtRatio.toFixed(0)} % des actifs`} className="pat-ratio__bar" role="img">
          <i style={{ flex: Math.max(100 - debtRatio, 0) }} />
          <b style={{ flex: Math.min(debtRatio, 100) }} />
        </div>
        <div className="pat-ratio__legend">
          <span><strong className="pat-blue">Actifs</strong> {money.format(summary.totalAssets)}</span>
          <span><strong className="pat-red">Passifs</strong> {money.format(summary.totalLiabilities)}</span>
        </div>
        <div className="pat-debts">
          {debts.map((debt) => (
            <button className="pat-debt" key={debt.id} onClick={() => onOpenDebt(debt.id)} type="button">
              <span><b>{debt.name}</b> · capital restant</span>
              <strong>{money.format(debt.balance)} ›</strong>
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function EvolutionChart({ label, points }: { label: string; points: { date: string; value: number }[] }) {
  const host = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 440, height: 232 });
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const update = () => setSize({ width: Math.max(element.clientWidth, 280), height: Math.max(element.clientHeight, 180) });
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const { width, height } = size;
  const left = 54;
  const right = width - 12;
  const top = 26;
  const bottom = height - 28;
  if (points.length < 2) return <div className="pat-chart-host" ref={host}><p className="pat-empty">Historique insuffisant pour tracer la courbe.</p></div>;
  const values = points.map((point) => point.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (max === min) { max += 1; min -= 1; }
  const pad = (max - min) * 0.1;
  min -= pad;
  max += pad;
  const x = (index: number) => left + (index / (points.length - 1)) * (right - left);
  const y = (value: number) => bottom - ((value - min) / (max - min)) * (bottom - top);
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
  const area = `${line} L${right} ${bottom} L${left} ${bottom} Z`;
  const last = points[points.length - 1];
  const grid = [0, 1, 2, 3].map((index) => min + ((max - min) * (index + 0.5)) / 4);
  const compact = (value: number) => `${Math.round(value / 1000).toLocaleString("fr-FR")} k`;
  const month = (value: string) => new Intl.DateTimeFormat("fr-FR", { month: "short" }).format(new Date(`${value}T12:00:00`)).replace(".", "");
  const labelIndexes = [0, Math.floor((points.length - 1) / 3), Math.floor(((points.length - 1) * 2) / 3), points.length - 1];

  return (
    <div className="pat-chart-host" ref={host}>
      <svg aria-label={`${label} : de ${money.format(points[0].value)} à ${money.format(last.value)}`} className="pat-chart" height={height} role="img" viewBox={`0 0 ${width} ${height}`} width={width}>
        {grid.map((value) => (
          <g key={value}>
            <line stroke="#e3e9f3" x1={left} x2={right} y1={y(value)} y2={y(value)} />
            <text fill="#52627d" fontSize="11" textAnchor="end" x={left - 8} y={y(value) + 4}>{compact(value)}</text>
          </g>
        ))}
        <path d={area} fill="#2563eb" opacity="0.1" />
        <path d={line} fill="none" stroke="#2563eb" strokeLinejoin="round" strokeWidth="2.8" />
        {points.map((point, index) => (
          <circle cx={x(index)} cy={y(point.value)} fill={index === points.length - 1 ? "#fff" : "transparent"} key={point.date} r={index === points.length - 1 ? 5.5 : 8} stroke={index === points.length - 1 ? "#2563eb" : "none"} strokeWidth="2.5">
            <title>{`${formatDay(point.date)} : ${money.format(point.value)}`}</title>
          </circle>
        ))}
        <text fill="#1d4ed8" fontSize="12" fontWeight="700" textAnchor="end" x={right - 10} y={Math.max(y(last.value) - 12, 14)}>{money.format(last.value)}</text>
        {labelIndexes.map((index, position) => (
          <text fill="#52627d" fontSize="11" key={index} textAnchor={position === 0 ? "start" : position === labelIndexes.length - 1 ? "end" : "middle"} x={x(index)} y={height - 6}>{month(points[index].date)}</text>
        ))}
      </svg>
    </div>
  );
}
