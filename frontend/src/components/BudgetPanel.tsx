import type { BudgetRow } from "../api/contracts";

const money = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });

export function BudgetPanel({ rows }: { rows: BudgetRow[] }) {
  const visibleRows = [...rows].sort((a, b) => b.actual - a.actual).slice(0, 5);

  if (!visibleRows.length) {
    return <div className="empty-chart">Aucune consommation budgétaire</div>;
  }

  return (
    <div className="budget-list">
      {visibleRows.map((row) => {
        const ratio = row.planned > 0 ? Math.min(100, (row.actual / row.planned) * 100) : 100;
        return (
          <div className="budget-row" key={row.category}>
            <div>
              <strong>{row.category}</strong>
              <span>{money.format(row.actual)} € / {money.format(row.planned)} €</span>
            </div>
            <div className="budget-track" aria-label={`${row.category} : ${Math.round(row.usage)} %`}>
              <span className={row.actual > row.planned && row.planned > 0 ? "over" : ""} style={{ width: `${ratio}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
