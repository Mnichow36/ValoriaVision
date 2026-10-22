import { useMemo } from "react";
import type { MouseEvent } from "react";

import type { BudgetAnnualCategory, BudgetsSnapshot } from "../api/contracts";
import { MONTH_SHORT, formatMoney, signedMoney } from "./budgetFormat";

export type ComparativePeriod = "month" | "quarter" | "year";
export type ComparativeView = "revised" | "initial";

interface BudgetsComparativeProps {
  onMenu: (event: MouseEvent, category: string) => void;
  onPeriodChange: (period: ComparativePeriod) => void;
  onRevise: (category: string) => void;
  onViewChange: (view: ComparativeView) => void;
  onYearChange: (year: number) => void;
  period: ComparativePeriod;
  snapshot: BudgetsSnapshot;
  view: ComparativeView;
  years: number[];
}

interface Line {
  budget: number;
  category: BudgetAnnualCategory;
  gap: number;
  realized: number;
  toDate: number;
  usage: number;
}

/** Onglet 2 : budget comparatif réalisé / budgété, mensuel, trimestriel et annuel. */
export function BudgetsComparative({ onMenu, onPeriodChange, onRevise, onViewChange, onYearChange, period, snapshot, view, years }: BudgetsComparativeProps) {
  const { annual } = snapshot;
  const monthIndex = Number(snapshot.month.slice(5, 7)) - 1;
  const indices = useMemo(() => {
    if (period === "month") return [monthIndex];
    if (period === "quarter") {
      const first = Math.floor(monthIndex / 3) * 3;
      return [first, first + 1, first + 2];
    }
    return Array.from({ length: 12 }, (_, index) => index);
  }, [monthIndex, period]);
  const elapsed = annual.elapsedMonths;

  const lines: Line[] = useMemo(() => annual.categories.map((category) => {
    const amounts = view === "initial" ? category.initial : category.planned;
    const budget = indices.reduce((sum, index) => sum + amounts[index], 0);
    const toDate = indices.filter((index) => index < elapsed).reduce((sum, index) => sum + amounts[index], 0);
    const realized = indices.filter((index) => index < elapsed).reduce((sum, index) => sum + category.actual[index], 0);
    return { budget, category, gap: realized - toDate, realized, toDate, usage: toDate ? (realized / toDate) * 100 : realized ? 100 : 0 };
  }).filter((line) => line.budget > 0 || line.realized > 0), [annual.categories, elapsed, indices, view]);

  const totals = lines.reduce((sum, line) => ({ budget: sum.budget + line.budget, toDate: sum.toDate + line.toDate, realized: sum.realized + line.realized }), { budget: 0, toDate: 0, realized: 0 });
  const totalGap = totals.realized - totals.toDate;
  const periodTitle = period === "month" ? MONTH_SHORT[monthIndex] : period === "quarter" ? `T${Math.floor(monthIndex / 3) + 1}` : String(annual.year);

  return (
    <div className="bgt-tab">
      <section className="bgt-toolbar">
        <div className="bgt-segmented" role="group" aria-label="Période">
          {([["month", "Mois"], ["quarter", "Trimestre"], ["year", "Année"]] as const).map(([id, label]) => (
            <button aria-pressed={period === id} className={period === id ? "is-active" : ""} key={id} onClick={() => onPeriodChange(id)} type="button">{label}</button>
          ))}
        </div>
        <div className="bgt-toolbar__summary">
          <span><b>Budget {periodTitle}</b> {formatMoney(totals.budget)}</span>
          <span><b>Réalisé</b> {formatMoney(totals.realized)}</span>
          {period === "year" && annual.year === Number(annual.currentMonth.slice(0, 4)) && (
            <span className={annual.totals.projectedYear > annual.totals.annual ? "bgt-bad" : "bgt-good"}>
              <b>Projection fin d’année</b> {formatMoney(annual.totals.projectedYear)} ({signedMoney(annual.totals.projectedYear - annual.totals.annual)})
            </span>
          )}
        </div>
        <div className="bgt-toolbar__selects">
          <select aria-label="Année" onChange={(event) => onYearChange(Number(event.target.value))} value={annual.year}>
            {years.map((year) => <option key={year} value={year}>{year}</option>)}
          </select>
          <select aria-label="Version du budget" onChange={(event) => onViewChange(event.target.value as ComparativeView)} value={view}>
            <option value="revised">Budget : révisé</option>
            <option value="initial">Budget : initial</option>
          </select>
        </div>
      </section>

      <article className="bgt-card bgt-table-card">
        <div className="bgt-row bgt-row--head">
          <span>Catégorie</span><span className="is-num">Budget</span><span className="is-num">Budget à ce jour</span><span className="is-num">Réalisé</span><span className="is-num">Écart</span><span>Consommation</span><span>12 mois (janv. → déc.)</span><span>Révision</span>
        </div>
        <div className="bgt-rows">
          {lines.length === 0 && <p className="bgt-empty">Aucun budget ni dépense sur cette période.</p>}
          {lines.map((line) => (
            <div className="bgt-row bgt-row--body" key={line.category.category} onClick={() => onRevise(line.category.category)} onContextMenu={(event) => onMenu(event, line.category.category)} role="button" tabIndex={0}
              onKeyDown={(event) => { if (event.key === "Enter") onRevise(line.category.category); }}>
              <strong>{line.category.category}</strong>
              <span className="is-num">{formatMoney(line.budget)}</span>
              <span className="is-num bgt-muted">{formatMoney(line.toDate)}</span>
              <span className="is-num"><b>{formatMoney(line.realized)}</b></span>
              <span className={`is-num ${line.gap > 0 ? "bgt-bad" : "bgt-good"}`}><b>{signedMoney(line.gap)}</b></span>
              <div className="bgt-usage">
                <div><i className={line.usage > 105 ? "is-over" : line.usage > 100 ? "is-warn" : ""} style={{ width: `${Math.min(100, line.usage)}%` }} /></div>
                <em>{Math.round(line.usage)} %</em>
              </div>
              <MiniBars category={line.category} indices={indices} view={view} />
              <RevisionBadge category={line.category} view={view} />
            </div>
          ))}
        </div>
        <div className="bgt-row bgt-row--total">
          <strong>Total</strong>
          <span className="is-num">{formatMoney(totals.budget)}</span>
          <span className="is-num bgt-muted">{formatMoney(totals.toDate)}</span>
          <span className="is-num">{formatMoney(totals.realized)}</span>
          <span className={`is-num ${totalGap > 0 ? "bgt-bad" : "bgt-good"}`}>{signedMoney(totalGap)}</span>
          <span className="bgt-muted bgt-small">{totals.toDate ? `${Math.round((totals.realized / totals.toDate) * 100)} % du budget à ce jour` : ""}</span>
          <span className="bgt-muted bgt-small">Pointillé : budget mensuel</span>
          <span />
        </div>
      </article>

      <footer className="bgt-hint">
        <span>Clic ou clic droit sur une ligne : réviser le budget, consulter l’historique des révisions.</span>
        <span>Barre rouge : mois au-dessus du budget. « À ce jour » inclut le mois en cours en entier.</span>
      </footer>
    </div>
  );
}

function MiniBars({ category, indices, view }: { category: BudgetAnnualCategory; indices: number[]; view: ComparativeView }) {
  const amounts = view === "initial" ? category.initial : category.planned;
  const top = Math.max(...amounts, ...category.actual, 1) * 1.05;
  return (
    <div aria-label="Réalisé mensuel : barre rouge quand le mois dépasse le budget" className="bgt-mini" role="img">
      {category.actual.map((value, index) => (
        <i
          className={`${value > amounts[index] && amounts[index] > 0 ? "is-over" : ""} ${indices.includes(index) ? "" : "is-dim"}`}
          key={index}
          style={{ height: `${Math.max(2, (value / top) * 100)}%` }}
          title={`${MONTH_SHORT[index]} : ${formatMoney(value)} (budget ${formatMoney(amounts[index])})`}
        />
      ))}
      {amounts.some((value) => value > 0) && <b style={{ bottom: `${(Math.max(...amounts) / top) * 100}%` }} />}
    </div>
  );
}

function RevisionBadge({ category, view }: { category: BudgetAnnualCategory; view: ComparativeView }) {
  if (category.suggestRevision && view === "revised") return <span className="bgt-badge bgt-badge--warn">À réviser</span>;
  if (category.revisionCount > 0) return <span className="bgt-badge bgt-badge--blue">Révisé · {category.revisionCount}×</span>;
  return <span className="bgt-badge">Budget initial</span>;
}
