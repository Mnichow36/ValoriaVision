import { useEffect, useMemo, useState } from "react";

import { getBudgets } from "../api/client";
import type { BudgetCategoryRow, BudgetsSnapshot } from "../api/contracts";

interface BudgetsPageProps {
  month: string;
  onMonthChange: (month: string) => void;
  onMonthsChange: (months: string[]) => void;
  token: string;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

export function BudgetsPage({ month, onMonthChange, onMonthsChange, token }: BudgetsPageProps) {
  const [snapshot, setSnapshot] = useState<BudgetsSnapshot>();
  const [selectedCategory, setSelectedCategory] = useState("");
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getBudgets(token, month, controller.signal)
      .then((data) => {
        setSnapshot(data);
        onMonthsChange(data.months);
        if (!month) onMonthChange(data.month);
        setSelectedCategory((current) => data.rows.some((row) => row.category === current)
          ? current
          : data.summary.biggestGapCategory || data.rows[0]?.category || "");
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les budgets ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [month, onMonthChange, onMonthsChange, refreshKey, token]);

  const chartRows = useMemo(() => {
    if (!snapshot) return [];
    return [...snapshot.rows]
      .filter((row) => row.planned > 0 || row.actual > 0)
      .sort((left, right) => Math.max(right.planned, right.actual) - Math.max(left.planned, left.actual))
      .slice(0, 5);
  }, [snapshot]);

  if (error) {
    return (
      <section className="error-state">
        <strong>Les budgets ne peuvent pas être affichés.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Calcul des budgets par le moteur Python…</div>;
  }

  const selected = snapshot.rows.find((row) => row.category === selectedCategory) ?? snapshot.rows[0];
  const maximum = Math.max(...chartRows.flatMap((row) => [row.planned, row.actual]), 1);
  const gapTone = snapshot.summary.biggestGap > 0 ? "danger" : "success";

  return (
    <div className="budgets-page">
      <section className="budget-kpis" aria-label="Indicateurs budgétaires">
        <BudgetKpi detail="Période mensuelle" label="Budget prévu" tone="blue" value={formatMoney(snapshot.summary.totalPlanned)} />
        <BudgetKpi detail={`${snapshot.summary.usageTotal.toLocaleString("fr-FR")} % consommé`} label="Réalisé" tone="cyan" value={formatMoney(snapshot.summary.totalRealized)} />
        <BudgetKpi detail={`${snapshot.summary.biggestGapCategory} ${snapshot.summary.biggestGap > 0 ? "à surveiller" : "maîtrisé"}`} label="Écart" tone="amber" value={signedMoney(snapshot.summary.biggestGap)} valueTone={gapTone} />
        <BudgetKpi detail={`${snapshot.summary.overCount} en dépassement`} label="Catégories" tone="purple" value={String(snapshot.summary.categoryCount)} />
      </section>

      <section className="budget-main-grid">
        <article className="card budget-chart-card">
          <div className="budget-heading"><h2>Prévu vs réalisé</h2><p>Lecture immédiate des principaux postes.</p></div>
          <div className="budget-bars">
            {chartRows.length > 0 ? chartRows.map((row) => (
              <BudgetBar maximum={maximum} onSelect={() => setSelectedCategory(row.category)} row={row} selected={row.category === selected?.category} key={row.category} />
            )) : <p className="budget-empty">Aucune donnée budgétaire pour ce mois.</p>}
          </div>
          <div className="budget-legend"><span><i className="budget-legend__planned" />Prévu</span><span><i className="budget-legend__actual" />Réalisé</span></div>
        </article>

        <BudgetDetail row={selected} />
      </section>
    </div>
  );
}

function BudgetKpi({ detail, label, tone, value, valueTone }: { detail: string; label: string; tone: string; value: string; valueTone?: "danger" | "success" }) {
  return (
    <article className="card budget-kpi">
      <div><span>{label}</span><i className={`budget-kpi__mark budget-kpi__mark--${tone}`} /></div>
      <strong className={valueTone ? `budget-kpi__value--${valueTone}` : ""}>{value}</strong>
      <small className={valueTone === "danger" ? "budget-kpi__detail--danger" : ""}>{detail}</small>
    </article>
  );
}

function BudgetBar({ maximum, onSelect, row, selected }: { maximum: number; onSelect: () => void; row: BudgetCategoryRow; selected: boolean }) {
  return (
    <button aria-pressed={selected} className={selected ? "budget-bar budget-bar--selected" : "budget-bar"} onClick={onSelect} type="button">
      <strong>{row.category}</strong>
      <div className="budget-bar__tracks">
        <span><i className="budget-bar__planned" style={{ width: `${Math.min(100, (row.planned / maximum) * 100)}%` }} /></span>
        <span><i className="budget-bar__actual" style={{ width: `${Math.min(100, (row.actual / maximum) * 100)}%` }} /></span>
      </div>
      <b>{formatMoney(row.actual)}</b>
    </button>
  );
}

function BudgetDetail({ row }: { row?: BudgetCategoryRow }) {
  if (!row) {
    return <aside className="card budget-detail"><div className="budget-heading"><h2>Volet catégorie</h2><p>Aucune catégorie disponible.</p></div></aside>;
  }
  return (
    <aside className="card budget-detail">
      <div className="budget-heading"><h2>Volet catégorie</h2><p>{row.category} sélectionnée.</p></div>
      <strong className={row.difference > 0 ? "budget-detail__amount budget-detail__amount--danger" : "budget-detail__amount"}>{formatMoney(row.actual)}</strong>
      <span className="budget-detail__meta">Réalisé sur {formatMoney(row.planned)} prévus</span>
      <span className={row.difference > 0 ? "budget-gap budget-gap--danger" : "budget-gap budget-gap--success"}>{signedMoney(row.difference)}</span>
      <div className="budget-detail__transactions">
        {row.transactions.length > 0 ? row.transactions.map((transaction) => (
          <div key={transaction.id}><strong>{transaction.label}</strong><span>{signedMoney(transaction.amount)}</span></div>
        )) : <p>Aucune transaction détaillée pour cette catégorie.</p>}
      </div>
      <button aria-disabled="true" title="Édition budgétaire prévue dans l’incrément suivant" type="button">Ajuster budget</button>
    </aside>
  );
}

function signedMoney(value: number): string {
  if (value === 0) return formatMoney(value);
  return `${value > 0 ? "+ " : "- "}${formatMoney(Math.abs(value))}`;
}

function formatMoney(value: number): string {
  return currencyFormatter.format(value);
}
