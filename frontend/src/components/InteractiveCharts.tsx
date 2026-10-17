import { useId, useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";

export interface InteractiveLineDetail {
  label: string;
  value: number;
  meta?: string;
  color?: string;
}

export interface InteractiveLinePoint {
  date: string;
  value: number;
  details?: InteractiveLineDetail[];
}

export interface InteractiveLineSeries {
  id: string;
  label: string;
  color: string;
  points: InteractiveLinePoint[];
  dashed?: boolean;
  area?: boolean;
}

export interface InteractiveDonutSlice {
  label: string;
  value: number;
  color: string;
}

export interface InteractiveBarRow {
  label: string;
  planned: number;
  actual: number;
}

interface InteractiveLineChartProps {
  ariaLabel: string;
  series: InteractiveLineSeries[];
  valueFormatter?: (value: number) => string;
  dateFormatter?: (value: string) => string;
}

interface InteractiveDonutChartProps {
  ariaLabel: string;
  slices: InteractiveDonutSlice[];
  valueFormatter?: (value: number) => string;
  showLegend?: boolean;
}

interface InteractiveGroupedBarChartProps {
  ariaLabel: string;
  rows: InteractiveBarRow[];
  selectedLabel?: string;
  onSelect: (label: string) => void;
  valueFormatter?: (value: number) => string;
}

const compactNumber = new Intl.NumberFormat("fr-FR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const percentNumber = new Intl.NumberFormat("fr-FR", {
  maximumFractionDigits: 1,
});

export function InteractiveLineChart({
  ariaLabel,
  series,
  valueFormatter = (value) => compactNumber.format(value),
  dateFormatter = formatDate,
}: InteractiveLineChartProps) {
  const width = 780;
  const height = 330;
  const plot = { left: 76, right: 24, top: 24, bottom: 50 };
  const chartWidth = width - plot.left - plot.right;
  const chartHeight = height - plot.top - plot.bottom;
  const domainLength = Math.max(0, ...series.map((item) => item.points.length));
  const values = series.flatMap((item) => item.points.map((point) => point.value));
  const rawMinimum = values.length ? Math.min(...values) : 0;
  const rawMaximum = values.length ? Math.max(...values) : 1;
  const padding = Math.max((rawMaximum - rawMinimum) * 0.1, Math.abs(rawMaximum || 1) * 0.02, 1);
  const minimum = rawMinimum - padding;
  const maximum = rawMaximum + padding;
  const range = maximum - minimum || 1;
  const x = (index: number) => plot.left + (domainLength <= 1 ? chartWidth / 2 : index / (domainLength - 1) * chartWidth);
  const y = (value: number) => plot.top + (maximum - value) / range * chartHeight;
  const yTicks = Array.from({ length: 5 }, (_, index) => maximum - index * range / 4);
  const tickIndexes = uniqueIndexes(domainLength, 5);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const gradientId = `chartArea${useId().replace(/:/g, "")}`;
  const coordinates = useMemo(
    () => series.map((item) => item.points.map((point, index) => ({ x: x(index), y: y(point.value) }))),
    [series, domainLength, minimum, maximum],
  );

  function move(event: PointerEvent<HTMLDivElement>) {
    if (domainLength <= 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(rect.width, 1)));
    setActiveIndex(Math.round(ratio * (domainLength - 1)));
  }

  const activeDate = activeIndex === null
    ? ""
    : series.find((item) => item.points[activeIndex])?.points[activeIndex]?.date ?? "";
  const activeDetails = activeIndex === null
    ? []
    : series[0]?.points[activeIndex]?.details ?? [];

  if (!domainLength || !values.length) {
    return <div className="interactive-chart-empty">Données insuffisantes pour afficher le graphique.</div>;
  }

  return (
    <div className="interactive-line-chart" onPointerLeave={() => setActiveIndex(null)} onPointerMove={move}>
      <svg aria-label={ariaLabel} role="img" viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={series[0]?.color ?? "#2563eb"} stopOpacity=".24" />
            <stop offset="100%" stopColor={series[0]?.color ?? "#2563eb"} stopOpacity=".02" />
          </linearGradient>
        </defs>
        {yTicks.map((tick, index) => {
          const tickY = y(tick);
          return (
            <g key={index}>
              <line className="interactive-line-chart__grid" x1={plot.left} x2={width - plot.right} y1={tickY} y2={tickY} />
              <text className="interactive-line-chart__axis interactive-line-chart__axis--y" x={plot.left - 12} y={tickY + 4}>{valueFormatter(tick)}</text>
            </g>
          );
        })}
        {tickIndexes.map((index) => {
          const point = series.find((item) => item.points[index])?.points[index];
          if (!point) return null;
          return (
            <g key={index}>
              <line className="interactive-line-chart__tick" x1={x(index)} x2={x(index)} y1={height - plot.bottom} y2={height - plot.bottom + 5} />
              <text className="interactive-line-chart__axis interactive-line-chart__axis--x" x={x(index)} y={height - 17}>{dateFormatter(point.date)}</text>
            </g>
          );
        })}
        {coordinates[0]?.length > 1 && (
          <path
            className="interactive-line-chart__area"
            d={`${smoothPath(coordinates[0])} L ${x(coordinates[0].length - 1)} ${height - plot.bottom} L ${x(0)} ${height - plot.bottom} Z`}
            fill={`url(#${gradientId})`}
          />
        )}
        {series.map((item, seriesIndex) => (
          <path
            className="interactive-line-chart__line"
            d={smoothPath(coordinates[seriesIndex] ?? [])}
            key={item.id}
            style={{
              stroke: item.color,
              strokeDasharray: item.dashed ? "8 7" : undefined,
              strokeWidth: seriesIndex === 0 ? 3.5 : 2.25,
            }}
          />
        ))}
        {tickIndexes.map((index) => series.map((item, seriesIndex) => {
          const point = item.points[index];
          const coordinate = coordinates[seriesIndex]?.[index];
          if (!point || !coordinate) return null;
          return <circle className="interactive-line-chart__point interactive-line-chart__point--muted" cx={coordinate.x} cy={coordinate.y} key={`${item.id}-${index}`} r="2.6" style={{ fill: item.color }} />;
        }))}
        {series[0]?.points.map((point, index) => {
          const coordinate = coordinates[0]?.[index];
          if (!coordinate || !point.details?.length) return null;
          return (
            <circle
              className="interactive-line-chart__event-marker"
              cx={coordinate.x}
              cy={coordinate.y}
              key={`event-${point.date}-${index}`}
              r="4.5"
            >
              <title>{`${point.details.length} mouvement(s) · ${dateFormatter(point.date)}`}</title>
            </circle>
          );
        })}
        {activeIndex !== null && (
          <>
            <line className="interactive-line-chart__crosshair" x1={x(activeIndex)} x2={x(activeIndex)} y1={plot.top} y2={height - plot.bottom} />
            {series.map((item, seriesIndex) => {
              const point = item.points[activeIndex];
              const coordinate = coordinates[seriesIndex]?.[activeIndex];
              if (!point || !coordinate) return null;
              return <circle className="interactive-line-chart__point" cx={coordinate.x} cy={coordinate.y} key={item.id} r="6" style={{ fill: item.color }} />;
            })}
          </>
        )}
      </svg>
      {activeIndex !== null && (
        <div
          className={`interactive-chart-tooltip ${activeIndex < domainLength / 2 ? "interactive-chart-tooltip--right" : "interactive-chart-tooltip--left"}`}
          style={{ left: `${x(activeIndex) / width * 100}%` }}
        >
          <strong>{dateFormatter(activeDate)}</strong>
          {series.map((item) => {
            const point = item.points[activeIndex];
            return point ? (
              <span key={item.id}><i style={{ background: item.color }} />{item.label}<b>{valueFormatter(point.value)}</b></span>
            ) : null;
          })}
          {activeDetails.length > 0 && (
            <div className="interactive-chart-tooltip__details">
              <small>Mouvements du jour</small>
              {activeDetails.slice(0, 5).map((detail, index) => (
                <span key={`${detail.label}-${index}`}>
                  <i style={{ background: detail.color ?? (detail.value >= 0 ? "#22c55e" : "#ef4444") }} />
                  <span>{detail.label}<small>{detail.meta}</small></span>
                  <b>{detail.value > 0 ? "+ " : detail.value < 0 ? "- " : ""}{valueFormatter(Math.abs(detail.value))}</b>
                </span>
              ))}
              {activeDetails.length > 5 && <em>+ {activeDetails.length - 5} autre(s) mouvement(s)</em>}
            </div>
          )}
        </div>
      )}
      <div className="interactive-chart-legend">
        {series.map((item) => <span key={item.id}><i style={{ background: item.color }} />{item.label}</span>)}
      </div>
    </div>
  );
}

export function InteractiveDonutChart({
  ariaLabel,
  slices,
  valueFormatter = (value) => compactNumber.format(value),
  showLegend = true,
}: InteractiveDonutChartProps) {
  const positiveSlices = slices.filter((slice) => slice.value > 0);
  const total = positiveSlices.reduce((sum, slice) => sum + slice.value, 0);
  const [activeIndex, setActiveIndex] = useState(() => {
    let selected = 0;
    positiveSlices.forEach((slice, index) => {
      if (slice.value > (positiveSlices[selected]?.value ?? -Infinity)) selected = index;
    });
    return selected;
  });
  const active = positiveSlices[activeIndex] ?? positiveSlices[0];
  let cursor = -90;
  const segments = positiveSlices.map((slice, index) => {
    const sweep = total ? slice.value / total * 360 : 0;
    const start = cursor;
    cursor += sweep;
    return { ...slice, index, start, end: cursor };
  });

  if (!total) {
    return <div className="interactive-chart-empty">Aucune valeur à représenter.</div>;
  }

  return (
    <div className={showLegend ? "interactive-donut interactive-donut--with-legend" : "interactive-donut"}>
      <div className="interactive-donut__visual">
        <svg aria-label={ariaLabel} role="img" viewBox="0 0 220 220">
          <circle className="interactive-donut__track" cx="110" cy="110" r="78" />
          {segments.map((segment) => (
            <path
              aria-label={`${segment.label} : ${valueFormatter(segment.value)}`}
              className={segment.index === activeIndex ? "interactive-donut__segment interactive-donut__segment--active" : "interactive-donut__segment"}
              d={donutSegmentPath(
                110,
                110,
                88,
                60,
                segment.start + Math.min(.7, (segment.end - segment.start) / 4),
                segment.end - Math.min(.7, (segment.end - segment.start) / 4),
              )}
              key={segment.label}
              onBlur={() => undefined}
              onFocus={() => setActiveIndex(segment.index)}
              onPointerEnter={() => setActiveIndex(segment.index)}
              role="button"
              style={{ fill: segment.color }}
              tabIndex={0}
            />
          ))}
        </svg>
        <div className="interactive-donut__center">
          <span>{active?.label ?? "Total"}</span>
          <strong>{valueFormatter(active?.value ?? total)}</strong>
          <small>{percentNumber.format((active?.value ?? total) / total * 100)} %</small>
        </div>
      </div>
      {showLegend && (
        <div className="interactive-donut__legend">
          {positiveSlices.map((slice, index) => (
            <button className={index === activeIndex ? "interactive-donut__legend-item interactive-donut__legend-item--active" : "interactive-donut__legend-item"} key={slice.label} onFocus={() => setActiveIndex(index)} onPointerEnter={() => setActiveIndex(index)} type="button">
              <i style={{ background: slice.color }} />
              <span>{slice.label}<small>{percentNumber.format(slice.value / total * 100)} %</small></span>
              <strong>{valueFormatter(slice.value)}</strong>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function InteractiveGroupedBarChart({
  ariaLabel,
  rows,
  selectedLabel,
  onSelect,
  valueFormatter = (value) => compactNumber.format(value),
}: InteractiveGroupedBarChartProps) {
  const width = 780;
  const rowHeight = 58;
  const plot = { left: 150, right: 72, top: 28, bottom: 46 };
  const height = Math.max(250, plot.top + plot.bottom + rows.length * rowHeight);
  const chartWidth = width - plot.left - plot.right;
  const maximum = Math.max(1, ...rows.flatMap((row) => [row.planned, row.actual]));
  const [hoveredLabel, setHoveredLabel] = useState<string>();
  const activeLabel = hoveredLabel ?? selectedLabel ?? rows[0]?.label;
  const activeRow = rows.find((row) => row.label === activeLabel) ?? rows[0];
  const ticks = Array.from({ length: 5 }, (_, index) => maximum * index / 4);
  const barWidth = (value: number) => Math.max(0, value / maximum * chartWidth);

  function keySelect(event: KeyboardEvent<SVGGElement>, label: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(label);
    }
  }

  if (!rows.length) {
    return <div className="interactive-chart-empty">Aucune donnée budgétaire pour cette période.</div>;
  }

  return (
    <div className="interactive-bar-shell">
      {activeRow && (
        <div className="interactive-bar-summary" role="status">
          <strong>{activeRow.label}</strong>
          <span>Prévu <b>{valueFormatter(activeRow.planned)}</b></span>
          <span>Réalisé <b>{valueFormatter(activeRow.actual)}</b></span>
          <span className={activeRow.actual > activeRow.planned ? "interactive-bar-summary__gap interactive-bar-summary__gap--danger" : "interactive-bar-summary__gap"}>
            Écart <b>{valueFormatter(activeRow.actual - activeRow.planned)}</b>
          </span>
        </div>
      )}
      <svg aria-label={ariaLabel} className="interactive-bar-chart" role="img" viewBox={`0 0 ${width} ${height}`}>
        {ticks.map((tick, index) => {
          const tickX = plot.left + index * chartWidth / 4;
          return (
            <g key={index}>
              <line className="interactive-bar-chart__grid" x1={tickX} x2={tickX} y1={plot.top} y2={height - plot.bottom} />
              <text className="interactive-bar-chart__axis" x={tickX} y={height - 16}>{valueFormatter(tick)}</text>
            </g>
          );
        })}
        {rows.map((row, index) => {
          const y = plot.top + index * rowHeight;
          const active = row.label === activeLabel;
          return (
            <g
              aria-label={`${row.label}, prévu ${valueFormatter(row.planned)}, réalisé ${valueFormatter(row.actual)}`}
              className={active ? "interactive-bar-chart__row interactive-bar-chart__row--active" : "interactive-bar-chart__row"}
              key={row.label}
              onBlur={() => setHoveredLabel(undefined)}
              onClick={() => onSelect(row.label)}
              onFocus={() => setHoveredLabel(row.label)}
              onKeyDown={(event) => keySelect(event, row.label)}
              onPointerEnter={() => setHoveredLabel(row.label)}
              onPointerLeave={() => setHoveredLabel(undefined)}
              role="button"
              tabIndex={0}
            >
              <rect className="interactive-bar-chart__row-bg" height={rowHeight - 5} rx="8" width={width - 12} x="6" y={y - 8} />
              <text className="interactive-bar-chart__label" x={plot.left - 14} y={y + 17}>{row.label}</text>
              <rect className="interactive-bar-chart__planned" height="10" rx="5" width={barWidth(row.planned)} x={plot.left} y={y + 2} />
              <rect className="interactive-bar-chart__actual" height="10" rx="5" width={barWidth(row.actual)} x={plot.left} y={y + 20} />
              <text className="interactive-bar-chart__value" x={Math.min(width - plot.right + 8, plot.left + barWidth(row.actual) + 8)} y={y + 30}>{valueFormatter(row.actual)}</text>
            </g>
          );
        })}
      </svg>
      <div className="interactive-chart-legend">
        <span><i className="interactive-legend-planned" />Prévu</span>
        <span><i className="interactive-legend-actual" />Réalisé</span>
        <small>Survolez ou sélectionnez une catégorie pour afficher son détail.</small>
      </div>
    </div>
  );
}

function uniqueIndexes(length: number, count: number): number[] {
  if (length <= 0) return [];
  const indexes = Array.from({ length: Math.min(count, length) }, (_, index) => Math.round(index * (length - 1) / Math.max(1, Math.min(count, length) - 1)));
  return [...new Set(indexes)];
}

function smoothPath(points: Array<{ x: number; y: number }>): string {
  if (!points.length) return "";
  if (points.length === 1) return `M ${points[0].x} ${points[0].y}`;
  return points.reduce((path, point, index) => {
    if (index === 0) return `M ${point.x} ${point.y}`;
    const previous = points[index - 1];
    const controlX = (previous.x + point.x) / 2;
    return `${path} C ${controlX} ${previous.y}, ${controlX} ${point.y}, ${point.x} ${point.y}`;
  }, "");
}

function donutSegmentPath(
  centerX: number,
  centerY: number,
  outerRadius: number,
  innerRadius: number,
  startAngle: number,
  endAngle: number,
): string {
  const safeEnd = endAngle - startAngle >= 359.99 ? startAngle + 359.99 : endAngle;
  const outerStart = polar(centerX, centerY, outerRadius, startAngle);
  const outerEnd = polar(centerX, centerY, outerRadius, safeEnd);
  const innerStart = polar(centerX, centerY, innerRadius, safeEnd);
  const innerEnd = polar(centerX, centerY, innerRadius, startAngle);
  const largeArc = safeEnd - startAngle > 180 ? 1 : 0;
  return [
    `M ${outerStart.x} ${outerStart.y}`,
    `A ${outerRadius} ${outerRadius} 0 ${largeArc} 1 ${outerEnd.x} ${outerEnd.y}`,
    `L ${innerStart.x} ${innerStart.y}`,
    `A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${innerEnd.x} ${innerEnd.y}`,
    "Z",
  ].join(" ");
}

function polar(centerX: number, centerY: number, radius: number, angle: number) {
  const radians = angle * Math.PI / 180;
  return {
    x: centerX + radius * Math.cos(radians),
    y: centerY + radius * Math.sin(radians),
  };
}

function formatDate(value: string): string {
  if (!value) return "—";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" }).format(parsed).replace(".", "");
}
