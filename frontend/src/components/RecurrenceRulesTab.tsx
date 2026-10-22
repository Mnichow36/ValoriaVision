import { useEffect, useMemo, useState } from "react";

import { deleteRecurrence, getForecast } from "../api/client";
import type { ForecastSnapshot, RecurrenceActionResult, RecurrenceItem } from "../api/contracts";
import { RecurrenceEditor } from "./RecurrenceEditor";
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
  const [status, setStatus] = useState("all");
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
    if (status !== "all" && (status === "active") !== (item.status === "Actif")) return false;
    return !query || [item.name, item.accountName, item.bank, item.category, item.frequency, item.scenario].some((value) => value.toLocaleLowerCase("fr").includes(query));
  }), [accountId, query, snapshot, status]);

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

  return (
    <div className="transactions-page recurrence-workspace">
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      {error && <p className="account-form-error" role="alert">{error}</p>}
      <article className="card recurrence-catalog">
        <div className="recurrence-catalog__heading">
          <div>
            <h2>Règles de récurrence</h2>
            <p>Une règle génère les occurrences listées dans l’onglet « Récurrences ». Modifier une règle met à jour les échéances à venir non modifiées à la main.</p>
          </div>
        </div>
        <div className="recurrence-catalog__filters">
          <input aria-label="Rechercher une règle" onChange={(event) => setSearch(event.target.value)} placeholder="Recherche libellé, compte, catégorie…" type="search" value={search} />
          <select aria-label="Compte des règles" onChange={(event) => setAccountId(event.target.value)} value={accountId}>
            <option value="all">Tous les comptes</option>
            {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}
          </select>
          <select aria-label="Statut des règles" onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="all">Tous les statuts</option>
            <option value="active">Actives</option>
            <option value="inactive">Inactives</option>
          </select>
        </div>
        <div className="recurrence-rules__grid">
          {rules.map((item) => (
            <article className="recurrence-rule-card" key={item.id}>
              <div className="recurrence-rule-card__top">
                <div><strong>{item.name}</strong><span>{item.bank ? `${item.bank} · ` : ""}{item.accountName}</span></div>
                <b className={item.direction === "Crédit" ? "positive" : "negative"}>{signed(item.direction === "Crédit" ? item.amount : -item.amount)}</b>
              </div>
              <div className="recurrence-rule-card__meta">
                <span>{item.category}</span>
                <span>{item.frequency}</span>
                <span>{item.scenario}</span>
                <span className={item.status === "Actif" ? "recurrence-status recurrence-status--active" : "recurrence-status"}>{item.status}</span>
              </div>
              <div className="recurrence-rule-card__dates">
                <div><span>Prochaine échéance</span><strong>{item.nextOccurrenceDate ? formatDate(item.nextOccurrenceDate) : "Aucune"}</strong></div>
                <div><span>Fin de la règle</span><strong>{item.endDate ? formatDate(item.endDate) : "Sans fin"}</strong></div>
              </div>
              <div className="recurrence-rule-card__actions">
                <button className="secondary-button" onClick={() => { setEditing(item); setEditorOpen(true); }} type="button">Modifier</button>
                <button className="danger-button" onClick={() => setDeleting(item)} type="button">Supprimer</button>
              </div>
            </article>
          ))}
          {rules.length === 0 && <div className="forecast-day-details__empty"><strong>Aucune règle trouvée</strong><p>Modifiez les filtres ou créez une nouvelle récurrence.</p></div>}
        </div>
      </article>

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
