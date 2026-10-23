import { type MouseEvent, useEffect, useMemo, useState } from "react";

import { deleteRecurrence, getForecast } from "../api/client";
import type { ForecastSnapshot, RecurrenceActionResult, RecurrenceItem } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { RecurrenceEditor } from "./RecurrenceEditor";
import { type RecurrenceKind, kindLabel, monthlyAmount, recurrenceKinds } from "./recurrenceKinds";
import { SideDrawer } from "./SideDrawer";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", minimumFractionDigits: 2 });
const dateFormat = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

function signed(value: number): string {
  return `${value >= 0 ? "+ " : "- "}${money.format(Math.abs(value))}`;
}

/** Onglet « Règles de récurrence » : les règles à l'origine des occurrences. */
export function RecurrenceRulesTab({ createRequestKey, onDataChanged, token }: { createRequestKey: number; onDataChanged: () => void; token: string }) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [accountId, setAccountId] = useState("all");
  const [search, setSearch] = useState("");
  const [kindFilter, setKindFilter] = useState<RecurrenceKind | "all">("all");
  const [menu, setMenu] = useState<ContextMenuState>();
  const [editing, setEditing] = useState<RecurrenceItem>();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deleting, setDeleting] = useState<RecurrenceItem>();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (createRequestKey > 0) { setEditing(undefined); setEditorOpen(true); }
  }, [createRequestKey]);

  useEffect(() => {
    const controller = new AbortController();
    getForecast(token, { accountId, horizonDays: 90, scenario: "Réaliste" }, controller.signal)
      .then((value) => { setSnapshot(value); setError(undefined); })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Les règles ne peuvent pas être chargées.");
      });
    return () => controller.abort();
  }, [accountId, refreshKey, token]);

  const query = search.trim().toLocaleLowerCase("fr");
  const rules = useMemo(() => (snapshot?.recurrences ?? []).filter((item) => {
    if (accountId !== "all" && item.accountId !== Number(accountId)) return false;
    if (kindFilter !== "all" && item.kind !== kindFilter) return false;
    return !query || [item.name, item.accountName, item.bank, item.category, item.frequency, item.scenario, item.kind].some((value) => value.toLocaleLowerCase("fr").includes(query));
  }), [accountId, kindFilter, query, snapshot]);

  function completed(result: RecurrenceActionResult) {
    setEditorOpen(false);
    setEditing(undefined);
    setDeleting(undefined);
    setBusy(false);
    setNotice(result.message);
    setRefreshKey((key) => key + 1);
    onDataChanged();
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setError(undefined);
    try {
      completed(await deleteRecurrence(token, deleting.id));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La règle ne peut pas être supprimée.");
      setBusy(false);
    }
  }

  if (error && !snapshot) {
    return (
      <section className="error-state">
        <strong>Les règles de récurrence ne peuvent pas être affichées.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }
  if (!snapshot) return <div className="loading-state"><span aria-hidden="true" />Chargement des règles…</div>;

  const activeRules = snapshot.recurrences.filter((item) => item.status === "Actif");
  const countOf = (kind: RecurrenceKind) => snapshot.recurrences.filter((item) => item.kind === kind).length;
  const monthlyOf = (kind: RecurrenceKind) => activeRules.filter((item) => item.kind === kind).reduce((sum, item) => sum + monthlyAmount(item), 0);
  const subscriptionsMonthly = monthlyOf("Abonnement");
  const kindFilters: Array<{ id: RecurrenceKind | "all"; label: string; count: number }> = [
    { id: "all", label: "Tous", count: snapshot.recurrences.length },
    ...recurrenceKinds.map((kind) => ({ id: kind.id, label: kind.plural, count: countOf(kind.id) })),
  ];

  function openMenu(event: MouseEvent, item: RecurrenceItem) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Modifier la règle…", onSelect: () => { setEditing(item); setEditorOpen(true); } },
        { label: "Supprimer la règle…", danger: true, onSelect: () => setDeleting(item) },
      ],
    });
  }

  return (
    <div className="rcr-fill">
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      {error && <p className="account-form-error" role="alert">{error}</p>}
      <article className="card stg-panel">
        <div className="stg-toolbar">
          <div className="stg-toolbar__left">
            <input aria-label="Rechercher une règle" onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher une règle…" type="search" value={search} />
            <div className="stg-segment" role="group" aria-label="Filtrer par type">
              {kindFilters.map((item) => (
                <button aria-pressed={kindFilter === item.id} key={item.id} onClick={() => setKindFilter(item.id)} type="button">{item.label} · {item.count}</button>
              ))}
            </div>
            <select aria-label="Compte des règles" onChange={(event) => setAccountId(event.target.value)} value={accountId}>
              <option value="all">Tous les comptes</option>
              {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}
            </select>
          </div>
        </div>

        <div className="stg-kpis stg-kpis--3">
          <div className="rcr-kpi--blue"><b>{money.format(subscriptionsMonthly)}</b> d’abonnements par mois <span>· {activeRules.filter((item) => item.kind === "Abonnement").length} actif(s) · {money.format(subscriptionsMonthly * 12)} par an</span></div>
          <div><b>{money.format(monthlyOf("Charge fixe"))}</b> de charges fixes par mois</div>
          <div className="stg-kpis__ok"><b>{money.format(monthlyOf("Revenu"))}</b> de revenus réguliers par mois</div>
        </div>

        <div className="stg-table-wrap">
          <table className="stg-table stg-table--rules">
            <thead>
              <tr><th>Nom</th><th>Type</th><th>Catégorie</th><th>Fréquence</th><th className="num">Montant</th><th>Prochaine échéance</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {rules.map((item) => (
                <tr key={item.id} onContextMenu={(event) => openMenu(event, item)} onDoubleClick={() => { setEditing(item); setEditorOpen(true); }} title="Double-clic : modifier · clic droit : actions">
                  <td><strong>{item.name}</strong> <small>· {item.bank ? `${item.bank} · ` : ""}{item.accountName}</small></td>
                  <td><span className={`rcr-pill rcr-pill--${kindClass(item.kind)}`}>{kindLabel(item.kind)}</span></td>
                  <td>{item.category}</td>
                  <td>{item.frequency}</td>
                  <td className={item.direction === "Crédit" ? "num positive" : "num negative"}><b>{signed(item.direction === "Crédit" ? item.amount : -item.amount)}</b></td>
                  <td>{item.nextOccurrenceDate ? formatDate(item.nextOccurrenceDate) : "Aucune"}</td>
                  <td><span className={item.status === "Actif" ? "status-chip status-chip--success" : "status-chip status-chip--muted"}>{item.status === "Actif" ? "Active" : item.status}</span></td>
                </tr>
              ))}
              {rules.length === 0 && <tr><td className="stg-empty" colSpan={7}>Aucune règle trouvée. Modifiez les filtres ou créez une récurrence (clic droit sur une opération du journal › Créer une récurrence…).</td></tr>}
            </tbody>
          </table>
        </div>

        <p className="stg-footnote">Les totaux ramènent chaque fréquence à un mois (annuel ÷ 12, trimestriel ÷ 3, hebdomadaire × 52 ÷ 12), règles actives seulement. Clic droit sur une règle : Modifier · Supprimer. Une règle génère les occurrences de l’onglet « Récurrences ».</p>
      </article>
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}

      {editorOpen && (
        <RecurrenceEditor
          accounts={snapshot.accounts}
          categories={snapshot.categories}
          defaultAccountId={accountId}
          defaultScenario="Réaliste"
          key={editing?.id ?? "new"}
          onClose={() => { setEditorOpen(false); setEditing(undefined); }}
          onCompleted={completed}
          recurrence={editing}
          token={token}
        />
      )}
      {deleting && (
        <SideDrawer
          eyebrow="Règle de récurrence"
          footer={(<><button className="secondary-button" disabled={busy} onClick={() => setDeleting(undefined)} type="button">Annuler</button><button className="danger-button" disabled={busy} onClick={() => void confirmDelete()} type="button">{busy ? "Suppression…" : "Supprimer la règle"}</button></>)}
          onClose={() => setDeleting(undefined)}
          title="Supprimer cette règle"
        >
          <p className="drawer-help">La règle « {deleting.name} » et toutes ses occurrences (y compris passées ou rapprochées) seront supprimées définitivement. Les transactions déjà importées sont conservées mais perdent leur rapprochement avec cette règle. Pour retirer seulement quelques échéances, supprime-les une par une dans l’onglet « Récurrences ».</p>
          {error && <p className="account-form-error" role="alert">{error}</p>}
        </SideDrawer>
      )}
    </div>
  );
}

function kindClass(kind: string): string {
  return kind === "Abonnement" ? "sub" : kind === "Charge fixe" ? "fixed" : kind === "Revenu" ? "income" : "other";
}
