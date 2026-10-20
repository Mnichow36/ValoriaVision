import type { DashboardKpi } from "../api/contracts";

const numberFormat = new Intl.NumberFormat("fr-FR", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export function KpiCard({ kpi }: { kpi: DashboardKpi }) {
  return (
    <article className={`card kpi kpi--${kpi.tone}`}>
      <div className="kpi-heading">
        <span>{kpi.label}</span>
        <i aria-hidden="true" />
      </div>
      <strong>{numberFormat.format(kpi.value)} {kpi.currency}</strong>
      <small>{kpi.detail}</small>
    </article>
  );
}
