import { useCallback, useEffect, useMemo, useState } from "react";
import type { MouseEvent } from "react";

import { getBudgets, removeBudgetCategory, saveBudgetCategory } from "../api/client";
import type { BudgetsSnapshot } from "../api/contracts";
import { CategoryDrawer, ReviseDrawer, RulesDrawer } from "./BudgetDrawers";
import { BudgetsComparative, type ComparativePeriod, type ComparativeView } from "./BudgetsComparative";
import { BudgetsSettings } from "./BudgetsSettings";
import { BudgetsTracking } from "./BudgetsTracking";
import type { BudgetDrawerState } from "./budgetFormat";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";

interface BudgetsPageProps {
  month: string;
  onMonthChange: (month: string) => void;
  onMonthsChange: (months: string[]) => void;
  token: string;
}

type BudgetTab = "tracking" | "comparative" | "settings";

const TABS: Array<{ id: BudgetTab; label: string }> = [
  { id: "tracking", label: "Suivi" },
  { id: "comparative", label: "Budget comparatif" },
  { id: "settings", label: "Paramétrage" },
];

export function BudgetsPage({ month, onMonthChange, onMonthsChange, token }: BudgetsPageProps) {
  const [snapshot, setSnapshot] = useState<BudgetsSnapshot>();
  const [tab, setTab] = useState<BudgetTab>("tracking");
  const [period, setPeriod] = useState<ComparativePeriod>("year");
  const [view, setView] = useState<ComparativeView>("revised");
  const [drawer, setDrawer] = useState<BudgetDrawerState>();
  const [menu, setMenu] = useState<ContextMenuState>();
  const [notice, setNotice] = useState<string>();
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
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les budgets ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [month, onMonthChange, onMonthsChange, refreshKey, token]);

  const refresh = useCallback(() => setRefreshKey((key) => key + 1), []);
  const saved = useCallback((message: string) => {
    setDrawer(undefined);
    setNotice(message);
    refresh();
  }, [refresh]);

  const years = useMemo(() => {
    const found = new Set((snapshot?.months ?? []).map((item) => Number(item.slice(0, 4))).filter(Boolean));
    if (snapshot) found.add(snapshot.annual.year);
    return [...found].sort((left, right) => right - left);
  }, [snapshot]);

  useEffect(() => {
    if (!notice) return undefined;
    const timer = window.setTimeout(() => setNotice(undefined), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  if (error) {
    return (
      <section className="error-state">
        <strong>Les budgets ne peuvent pas être affichés.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={refresh} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Calcul des budgets par le moteur Python…</div>;
  }

  const selectedMonth = snapshot.month;
  const currentMonth = snapshot.annual.currentMonth;

  async function toggle(category: string, active: boolean) {
    try {
      const result = await saveBudgetCategory(token, { category, month: selectedMonth, active });
      setNotice(result.message);
      refresh();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Le changement n’a pas pu être enregistré.");
    }
  }

  async function remove(category: string) {
    try {
      const result = await removeBudgetCategory(token, category, selectedMonth);
      setNotice(result.message);
      refresh();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La catégorie n’a pas pu être retirée.");
    }
  }

  function openComparativeMenu(event: MouseEvent, category: string) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Réviser le budget…", onSelect: () => setDrawer({ kind: "revise", category }) },
        { label: "Historique des révisions", onSelect: () => setDrawer({ kind: "revise", category }) },
      ],
    });
  }

  function openSettingsMenu(event: MouseEvent, category: string) {
    event.preventDefault();
    const row = snapshot?.settings.categories.find((item) => item.category === category);
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Paramétrer…", onSelect: () => setDrawer({ kind: "category", category }) },
        { label: "Réviser le budget…", onSelect: () => setDrawer({ kind: "revise", category }), disabled: !row?.active },
        { label: row?.active ? "Désactiver" : "Activer", onSelect: () => void toggle(category, !row?.active) },
        { label: "Retirer du budget", onSelect: () => void remove(category), danger: true },
      ],
    });
  }

  const reviseTarget = (category?: string) => category ?? snapshot.annual.categories[0]?.category ?? "";

  return (
    <div className="bgt">
      {notice && <div className="account-notice bgt-toast" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      <div className="bgt-tabs">
        <div aria-label="Sections du budget" role="tablist">
          {TABS.map((item) => (
            <button aria-selected={tab === item.id} className={tab === item.id ? "bgt-tab-button is-active" : "bgt-tab-button"} key={item.id} onClick={() => setTab(item.id)} role="tab" type="button">{item.label}</button>
          ))}
        </div>
        {tab !== "settings" && snapshot.annual.categories.length > 0 && (
          <button className="bgt-primary" onClick={() => setDrawer({ kind: "revise", category: reviseTarget() })} type="button">Réviser le budget</button>
        )}
      </div>

      {tab === "tracking" && (
        <BudgetsTracking
          isCurrentMonth={selectedMonth === currentMonth}
          onOpenComparative={() => { setPeriod("month"); setTab("comparative"); }}
          onRevise={(category) => setDrawer({ kind: "revise", category })}
          snapshot={snapshot}
        />
      )}
      {tab === "comparative" && (
        <BudgetsComparative
          onMenu={openComparativeMenu}
          onPeriodChange={setPeriod}
          onRevise={(category) => setDrawer({ kind: "revise", category })}
          onViewChange={setView}
          onYearChange={(year) => onMonthChange(`${year}-${selectedMonth.slice(5)}`)}
          period={period}
          snapshot={snapshot}
          view={view}
          years={years}
        />
      )}
      {tab === "settings" && (
        <BudgetsSettings
          onEdit={(category) => setDrawer({ kind: "category", category })}
          onMenu={openSettingsMenu}
          onRules={() => setDrawer({ kind: "rules" })}
          onToggle={(category, active) => void toggle(category, active)}
          snapshot={snapshot}
        />
      )}

      {drawer?.kind === "revise" && <ReviseDrawer category={drawer.category} month={selectedMonth} onClose={() => setDrawer(undefined)} onSaved={saved} snapshot={snapshot} token={token} />}
      {drawer?.kind === "category" && <CategoryDrawer category={drawer.category} month={selectedMonth} onClose={() => setDrawer(undefined)} onSaved={saved} snapshot={snapshot} token={token} />}
      {drawer?.kind === "rules" && <RulesDrawer onClose={() => setDrawer(undefined)} onSaved={saved} snapshot={snapshot} token={token} />}
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
    </div>
  );
}
