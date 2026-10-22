import { useEffect, useMemo, useRef, useState } from "react";

import type { ForecastPoint } from "../api/contracts";

interface ForecastStepChartProps {
  comparison?: { label: string; points: ForecastPoint[] };
  onPointSelect: (point: ForecastPoint) => void;
  points: ForecastPoint[];
  referenceDate: string;
  scenarioLabel: string;
  threshold: number;
}

const LEFT = 64;
const RIGHT = 24;
const TOP = 40;
const FLOW_HALF = 26;
const BELOW_PLOT = 112; // flux journaliers + axe des dates

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const moneyFull = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", minimumFractionDigits: 2 });
const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });

function niceStep(range: number): number {
  const raw = range / 4;
  const magnitude = 10 ** Math.floor(Math.log10(raw || 1));
  const normalized = raw / magnitude;
  const factor = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 2.5 ? 2.5 : normalized <= 5 ? 5 : 10;
  return factor * magnitude;
}

function formatShort(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : shortDate.format(date).replace(".", "");
}

/** Courbe en escalier : un palier par jour d'opération, avec aujourd'hui, le seuil, le point bas et les flux. */
export function ForecastStepChart({ comparison, onPointSelect, points, referenceDate, scenarioLabel, threshold }: ForecastStepChartProps) {
  const [hover, setHover] = useState<number>();
  const wrapRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 900, h: 372 });

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const measure = () => setSize({ w: Math.max(480, Math.round(node.clientWidth)), h: Math.max(300, Math.round(node.clientHeight)) });
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  const W = size.w;
  const H = size.h;
  const PLOT_BOTTOM = H - BELOW_PLOT;
  const FLOW_MID = PLOT_BOTTOM + 50;

  const geometry = useMemo(() => {
    const count = points.length;
    const values = [
      ...points.map((point) => point.balance),
      ...(comparison?.points ?? []).map((point) => point.balance),
      ...(threshold > 0 ? [threshold] : []),
    ];
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values, 1);
    const pad = (rawMax - rawMin) * 0.08 || 1;
    const step = niceStep(rawMax - rawMin + pad * 2);
    const min = Math.floor((rawMin - pad) / step) * step;
    const max = Math.ceil((rawMax + pad) / step) * step;
    const x = (index: number) => LEFT + (count > 1 ? (index * (W - LEFT - RIGHT)) / (count - 1) : 0);
    const y = (value: number) => PLOT_BOTTOM - ((value - min) / (max - min || 1)) * (PLOT_BOTTOM - TOP);
    const ticks: number[] = [];
    for (let tick = min; tick <= max + step / 2; tick += step) ticks.push(tick);
    const stepPath = (series: ForecastPoint[]) =>
      series.map((point, index) => (index === 0 ? `M${x(0)} ${y(point.balance)}` : `H${x(index)} V${y(point.balance)}`)).join(" ");
    const maxFlow = Math.max(1, ...points.map((point) => Math.max(point.inflow ?? 0, point.outflow ?? 0)));
    return { count, max, min, step, ticks, x, y, stepPath, maxFlow };
  }, [comparison, points, threshold, W, PLOT_BOTTOM]);

  if (points.length === 0) return <div className="forecast-step-wrap" ref={wrapRef}><p className="forecast-empty">Aucune donnée sur la période.</p></div>;

  const { count, ticks, x, y, stepPath, maxFlow } = geometry;
  const low = points.reduce((best, point, index) => (point.balance < points[best].balance ? index : best), 0);
  const last = count - 1;
  const todayIndex = Math.max(0, points.findIndex((point) => point.date >= referenceDate));
  const tickIndexes = Array.from(new Set(Array.from({ length: Math.min(7, count) }, (_, i) => Math.round((i * last) / Math.max(1, Math.min(7, count) - 1)))));
  const thresholdVisible = threshold > 0 && threshold >= geometry.min && threshold <= geometry.max;
  const area = `${stepPath(points)} V${PLOT_BOTTOM} H${x(0)} Z`;
  const hovered = hover !== undefined ? points[hover] : undefined;

  function indexFromEvent(event: React.MouseEvent<SVGSVGElement>): number {
    const box = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - box.left) / box.width;
    const raw = ((ratio * W - LEFT) / (W - LEFT - RIGHT)) * last;
    return Math.max(0, Math.min(last, Math.round(raw)));
  }

  const tooltipX = hover === undefined ? 0 : Math.min(W - 250, Math.max(LEFT + 4, x(hover) + 12));

  return (
    <div className="forecast-step-wrap" ref={wrapRef}>
    <svg
      aria-label={`Solde projeté ${scenarioLabel}, du ${formatShort(points[0].date)} au ${formatShort(points[last].date)}, en escalier`}
      className="forecast-step-chart"
      onClick={(event) => onPointSelect(points[indexFromEvent(event)])}
      onMouseLeave={() => setHover(undefined)}
      onMouseMove={(event) => setHover(indexFromEvent(event))}
      role="img"
      viewBox={`0 0 ${W} ${H}`}
      height={H}
      width={W}
    >
      <defs>
        <linearGradient id="forecast-step-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#2563eb" stopOpacity="0.16" />
          <stop offset="1" stopColor="#2563eb" stopOpacity="0.02" />
        </linearGradient>
      </defs>

      {thresholdVisible && <rect fill="var(--s-fee2e2)" height={Math.max(0, PLOT_BOTTOM - y(threshold))} opacity="0.55" width={W - LEFT - RIGHT} x={LEFT} y={y(threshold)} />}
      {ticks.map((tick) => (
        <g key={tick}>
          <line stroke="var(--s-e3e9f3)" x1={LEFT} x2={W - RIGHT} y1={y(tick)} y2={y(tick)} />
          <text fill="var(--t-52627d)" fontSize="12" fontWeight="600" textAnchor="end" x={LEFT - 8} y={y(tick) + 4}>{money.format(tick)}</text>
        </g>
      ))}

      {thresholdVisible && (
        <g>
          <line stroke="#dc2626" strokeDasharray="6 5" strokeWidth="2" x1={LEFT} x2={W - RIGHT} y1={y(threshold)} y2={y(threshold)} />
          <text fill="var(--t-b91c1c)" fontSize="12" fontWeight="700" textAnchor="end" x={W - RIGHT - 4} y={y(threshold) + 16}>Seuil de sécurité {money.format(threshold)} EUR</text>
        </g>
      )}

      <path d={area} fill="url(#forecast-step-fill)" />
      {comparison && comparison.points.length > 0 && (
        <path d={stepPath(comparison.points)} fill="none" stroke="#7c3aed" strokeDasharray="6 5" strokeWidth="2" />
      )}
      <path d={stepPath(points)} fill="none" stroke="#2563eb" strokeLinejoin="round" strokeWidth="3" />

      <line stroke="var(--t-0f1b3a)" strokeWidth="1.5" x1={x(todayIndex)} x2={x(todayIndex)} y1={TOP - 8} y2={FLOW_MID + FLOW_HALF + 6} />
      <rect fill="#0f1b3a" height="22" rx="11" width="128" x={x(todayIndex) + 6} y={TOP - 30} />
      <text fill="#fff" fontSize="12" fontWeight="700" textAnchor="middle" x={x(todayIndex) + 70} y={TOP - 15}>Aujourd’hui {formatShort(referenceDate)}</text>

      <circle cx={x(low)} cy={y(points[low].balance)} fill="#fff" r="6" stroke="#2563eb" strokeWidth="3" />
      <g>
        <rect fill="#0f1b3a" height="40" rx="8" width="178" x={Math.min(W - RIGHT - 178, x(low) + 10)} y={y(points[low].balance) + 10} />
        <text fill="#fff" fontSize="12" fontWeight="700" x={Math.min(W - RIGHT - 178, x(low) + 10) + 10} y={y(points[low].balance) + 26}>Point bas · {formatShort(points[low].date)}</text>
        <text fill="#cfe0ff" fontSize="12" x={Math.min(W - RIGHT - 178, x(low) + 10) + 10} y={y(points[low].balance) + 42}>{moneyFull.format(points[low].balance)}</text>
      </g>
      <circle cx={x(last)} cy={y(points[last].balance)} fill="#fff" r="6" stroke="#2563eb" strokeWidth="3" />
      <text fill="var(--t-1d4ed8)" fontSize="13" fontWeight="800" textAnchor="end" x={x(last) - 8} y={y(points[last].balance) - 12}>{moneyFull.format(points[last].balance)}</text>

      <line stroke="var(--s-cdd7e6)" x1={LEFT} x2={W - RIGHT} y1={FLOW_MID} y2={FLOW_MID} />
      {points.map((point, index) => {
        const barWidth = Math.max(2, Math.min(12, ((W - LEFT - RIGHT) / Math.max(1, count)) * 0.6));
        const inflow = ((point.inflow ?? 0) / maxFlow) * FLOW_HALF;
        const outflow = ((point.outflow ?? 0) / maxFlow) * FLOW_HALF;
        return (
          <g key={point.date}>
            {inflow > 0 && <rect fill="#16a34a" height={inflow} rx="2" width={barWidth} x={x(index) - barWidth / 2} y={FLOW_MID - inflow} />}
            {outflow > 0 && <rect fill="#dc2626" height={outflow} rx="2" width={barWidth} x={x(index) - barWidth / 2} y={FLOW_MID} />}
          </g>
        );
      })}
      <text fill="var(--t-166534)" fontSize="11" fontWeight="700" textAnchor="end" x={LEFT - 8} y={FLOW_MID - FLOW_HALF + 8}>+ {money.format(maxFlow)}</text>
      <text fill="var(--t-b91c1c)" fontSize="11" fontWeight="700" textAnchor="end" x={LEFT - 8} y={FLOW_MID + FLOW_HALF}>− {money.format(maxFlow)}</text>

      {tickIndexes.map((index, position) => (
        <text fill="var(--t-52627d)" fontSize="12" fontWeight="600" key={index} textAnchor={position === 0 ? "start" : position === tickIndexes.length - 1 ? "end" : "middle"} x={x(index)} y={H - 10}>{formatShort(points[index].date)}</text>
      ))}

      {hovered && hover !== undefined && (
        <g pointerEvents="none">
          <line stroke="#2563eb" strokeDasharray="3 3" x1={x(hover)} x2={x(hover)} y1={TOP - 8} y2={FLOW_MID + FLOW_HALF + 6} />
          <rect fill="#fff" height={52 + Math.min(3, hovered.events.length) * 16} rx="8" stroke="var(--s-cdd7e6)" width="238" x={tooltipX} y={TOP + 6} />
          <text fill="var(--t-0f1b3a)" fontSize="12" fontWeight="800" x={tooltipX + 10} y={TOP + 24}>{formatShort(hovered.date)} · {moneyFull.format(hovered.balance)}</text>
          <text fill="var(--t-52627d)" fontSize="11" x={tooltipX + 10} y={TOP + 40}>{hovered.events.length ? `${hovered.events.length} opération${hovered.events.length > 1 ? "s" : ""} (clic : détail)` : "Aucune opération"}</text>
          {hovered.events.slice(0, 3).map((event, index) => (
            <text fill={event.amount >= 0 ? "var(--t-15803d)" : "var(--t-b91c1c)"} fontSize="11" fontWeight="600" key={`${event.name}-${index}`} x={tooltipX + 10} y={TOP + 56 + index * 16}>{event.name.slice(0, 22)} · {event.amount >= 0 ? "+" : "−"} {money.format(Math.abs(event.amount))}</text>
          ))}
        </g>
      )}
    </svg>
    </div>
  );
}
