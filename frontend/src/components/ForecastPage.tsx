import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createRecurrence, deleteRecurrence, getForecast, updateRecurrence } from "../api/client";
import type { ForecastAccount, ForecastCategory, ForecastEvent, ForecastPoint, ForecastSnapshot, RecurrenceActionResult, RecurrenceItem, RecurrencePayload } from "../api/contracts";
import { InteractiveLineChart } from "./InteractiveCharts";

interface ForecastPageProps {
  accountId: string;
  editorRequestKey: number;
  horizonDays: number;
  onAccountsChange: (accounts: ForecastAccount[]) => void;
  onDataChanged: () => void;
  onScenarioChange: (scenario: string) => void;
  scenario: string;
  token: string;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function ForecastPage({ accountId, editorRequestKey, horizonDays, onAccountsChange, onDataChanged, onScenarioChange, scenario, token }: ForecastPageProps) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [editorOpen, setEditorOpen] = useState(false);
  const [managerOpen, setManagerOpen] = useState(false);
  const [editingRecurrence, setEditingRecurrence] = useState<RecurrenceItem>();
  const [selectedPoint, setSelectedPoint] = useState<ForecastPoint>();
  const lastEditorRequestKey = useRef(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setSelectedPoint(undefined);
    getForecast(token, { accountId, horizonDays, scenario }, controller.signal)
      .then((data) => {
        setSnapshot(data);
        onAccountsChange(data.accounts);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "La projection ne peut pas être chargée.");
        }
      });
    return () => controller.abort();
  }, [accountId, horizonDays, onAccountsChange, refreshKey, scenario, token]);

  useEffect(() => {
    if (editorRequestKey > 0 && editorRequestKey !== lastEditorRequestKey.current) {
      lastEditorRequestKey.current = editorRequestKey;
      setEditingRecurrence(undefined);
      setManagerOpen(false);
      setSelectedPoint(undefined);
      setEditorOpen(true);
    }
  }, [editorRequestKey]);

  function completed(result: RecurrenceActionResult) {
    setEditorOpen(false);
    setManagerOpen(false);
    setEditingRecurrence(undefined);
    setSelectedPoint(undefined);
    setNotice(result.message);
    setRefreshKey((key) => key + 1);
    onDataChanged();
  }

  if (error) {
    return (
      <section className="error-state">
        <strong>Le prévisionnel ne peut pas être affiché.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Calcul de la projection par le moteur Python…</div>;
  }

  return (
    <>
      {notice && <div className="transaction-notice forecast-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      <div className="forecast-page">
      <article className="card forecast-projection">
        <div className="forecast-card-heading">
          <div><h2>Projection journalière</h2><p>Solde de départ + transactions réelles + occurrences prévues.</p></div>
          <div className="forecast-scenarios" role="tablist" aria-label="Scénario de projection">
            <ScenarioButton active={scenario === "Réaliste"} onClick={() => onScenarioChange("Réaliste")}>Réaliste</ScenarioButton>
            <ScenarioButton active={scenario === "Optimiste"} onClick={() => onScenarioChange("Optimiste")}>Optimiste</ScenarioButton>
          </div>
        </div>

        <ForecastChart onPointSelect={setSelectedPoint} snapshot={snapshot} />

        <div className="forecast-summary-cards">
          <ForecastSummaryCard
            badge={snapshot.summary.lowBalance >= 5000 ? "Cash stable" : snapshot.summary.alert}
            label="Point bas"
            meta={`Atteint le ${formatDate(snapshot.summary.lowDate)}`}
            tone={snapshot.summary.lowBalance >= 5000 ? "success" : "warning"}
            value={formatMoney(snapshot.summary.lowBalance)}
          />
          <ForecastSummaryCard
            badge={percentageChange(snapshot.summary.startingCash, snapshot.summary.endBalance)}
            label="Solde final"
            meta={`Projection au ${formatDate(snapshot.summary.endDate)}`}
            tone="blue"
            value={formatMoney(snapshot.summary.endBalance)}
          />
        </div>
      </article>

      <aside className="forecast-side">
        <article className="card forecast-upcoming">
          <div className="forecast-card-heading">
            <div><h2>Récurrences à venir</h2><p>Occurrences traçables par statut.</p></div>
            <button className="forecast-manage-button" onClick={() => {
              setSelectedPoint(undefined);
              setManagerOpen(true);
            }} type="button">
              Gérer <span>{snapshot.recurrences.length}</span>
            </button>
          </div>
          <div className="forecast-upcoming-list">
            {snapshot.upcoming.length > 0
              ? snapshot.upcoming.map((event, index) => <UpcomingEvent event={event} key={`${event.date}-${event.name}-${index}`} />)
              : <p className="forecast-empty">Aucune récurrence sur cette période.</p>}
          </div>
        </article>

        <article className="card forecast-reading">
          <div className="forecast-card-heading"><div><h2>Lecture immédiate</h2><p>Ce qui change sur la période.</p></div></div>
          <Metric label="Encaissements prévus" tone="positive" value={signedMoney(snapshot.summary.totalIn)} />
          <Metric label="Décaissements prévus" tone="negative" value={signedMoney(-snapshot.summary.totalOut)} />
          <Metric label="Écart vs scénario prudent" tone="blue" value={signedMoney(snapshot.summary.prudentDifference)} />
        </article>
      </aside>
      </div>
      {editorOpen && (
        <RecurrenceEditor
          accounts={snapshot.accounts}
          categories={snapshot.categories}
          defaultAccountId={accountId}
          defaultScenario={scenario}
          key={editingRecurrence?.id ?? "new"}
          onClose={() => {
            setEditorOpen(false);
            setEditingRecurrence(undefined);
          }}
          onCompleted={completed}
          recurrence={editingRecurrence}
          token={token}
        />
      )}
      {managerOpen && (
        <RecurrenceManager
          accountId={accountId}
          items={snapshot.recurrences}
          onClose={() => setManagerOpen(false)}
          onCompleted={completed}
          onEdit={(item) => {
            setManagerOpen(false);
            setEditingRecurrence(item);
            setEditorOpen(true);
          }}
          token={token}
        />
      )}
      {selectedPoint && (
        <ForecastDayDetails
          onClose={() => setSelectedPoint(undefined)}
          onCompleted={completed}
          onEdit={(item) => {
            setSelectedPoint(undefined);
            setEditingRecurrence(item);
            setEditorOpen(true);
          }}
          point={selectedPoint}
          recurrences={snapshot.recurrences}
          token={token}
        />
      )}
    </>
  );
}

function RecurrenceEditor({
  accounts,
  categories,
  defaultAccountId,
  defaultScenario,
  onClose,
  onCompleted,
  recurrence,
  token,
}: {
  accounts: ForecastAccount[];
  categories: ForecastCategory[];
  defaultAccountId: string;
  defaultScenario: string;
  onClose: () => void;
  onCompleted: (result: RecurrenceActionResult) => void;
  recurrence?: RecurrenceItem;
  token: string;
}) {
  const initialDirection: RecurrencePayload["direction"] = recurrence?.direction ?? "Débit";
  const initialCategories = compatibleCategories(categories, initialDirection);
  const [draft, setDraft] = useState<RecurrencePayload>(() => recurrence ? {
    accountId: recurrence.accountId,
    name: recurrence.name,
    category: recurrence.category,
    direction: recurrence.direction,
    amount: recurrence.amount,
    frequency: recurrence.frequency,
    nextDate: recurrence.nextDate,
    endDate: recurrence.endDate,
    scenario: recurrence.scenario,
  } : {
    accountId: defaultAccountId !== "all" ? Number(defaultAccountId) : accounts[0]?.id ?? 0,
    name: "",
    category: initialCategories[0]?.name ?? "",
    direction: initialDirection,
    amount: 0,
    frequency: "Mensuel",
    nextDate: today(),
    endDate: "",
    scenario: isScenario(defaultScenario) ? defaultScenario : "Réaliste",
  });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();
  const availableCategories = useMemo(
    () => compatibleCategories(categories, draft.direction),
    [categories, draft.direction],
  );

  function field<Key extends keyof RecurrencePayload>(key: Key, value: RecurrencePayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function changeDirection(direction: RecurrencePayload["direction"]) {
    const options = compatibleCategories(categories, direction);
    setDraft((current) => ({
      ...current,
      direction,
      category: options.some((category) => category.name === current.category)
        ? current.category
        : options[0]?.name ?? "",
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(recurrence
        ? await updateRecurrence(token, recurrence.id, draft)
        : await createRecurrence(token, draft));
    } catch (cause: unknown) {
      setFormError(cause instanceof Error ? cause.message : `La récurrence ne peut pas être ${recurrence ? "modifiée" : "créée"}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="recurrence-editor-title" aria-modal="true" className="account-editor recurrence-editor" role="dialog">
        <header>
          <div><span className="eyebrow">Prévisionnel</span><h2 id="recurrence-editor-title">{recurrence ? "Modifier la récurrence" : "Nouvelle récurrence"}</h2></div>
          <button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="account-editor-grid">
            <label className="account-field account-field--wide">
              <span>Nom du tiers ou libellé attendu *</span>
              <input autoFocus maxLength={120} onChange={(event) => field("name", event.target.value)} placeholder="Ex. Loyer Dupont" required value={draft.name} />
              <small>Ce nom sera utilisé par le moteur pour rapprocher l’échéance du relevé bancaire.</small>
            </label>
            <label className="account-field account-field--wide">
              <span>Compte *</span>
              <select onChange={(event) => field("accountId", Number(event.target.value))} required value={draft.accountId}>
                {accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}
              </select>
            </label>
            <label className="account-field">
              <span>Sens *</span>
              <select onChange={(event) => changeDirection(event.target.value as RecurrencePayload["direction"])} value={draft.direction}>
                <option value="Débit">Débit</option>
                <option value="Crédit">Crédit</option>
              </select>
            </label>
            <label className="account-field">
              <span>Montant *</span>
              <input min="0.01" onChange={(event) => field("amount", Number(event.target.value))} required step="0.01" type="number" value={draft.amount || ""} />
            </label>
            <label className="account-field account-field--wide">
              <span>Catégorie *</span>
              <select onChange={(event) => field("category", event.target.value)} required value={draft.category}>
                {availableCategories.map((category) => <option key={category.id} value={category.name}>{category.name}</option>)}
              </select>
            </label>
            <label className="account-field">
              <span>Fréquence *</span>
              <select onChange={(event) => field("frequency", event.target.value as RecurrencePayload["frequency"])} value={draft.frequency}>
                <option value="Ponctuel">Une seule fois</option>
                <option value="Hebdomadaire">Hebdomadaire</option>
                <option value="Mensuel">Mensuelle</option>
                <option value="Trimestriel">Trimestrielle</option>
                <option value="Annuel">Annuelle</option>
              </select>
            </label>
            <label className="account-field">
              <span>Première échéance *</span>
              <input onChange={(event) => field("nextDate", event.target.value)} required type="date" value={draft.nextDate} />
            </label>
            <label className="account-field">
              <span>Date de fin</span>
              <input disabled={draft.frequency === "Ponctuel"} min={draft.nextDate} onChange={(event) => field("endDate", event.target.value)} type="date" value={draft.frequency === "Ponctuel" ? "" : draft.endDate} />
            </label>
            <label className="account-field">
              <span>Scénario *</span>
              <select onChange={(event) => field("scenario", event.target.value as RecurrencePayload["scenario"])} value={draft.scenario}>
                <option value="Prudent">Prudent</option>
                <option value="Réaliste">Réaliste</option>
                <option value="Optimiste">Optimiste</option>
              </select>
            </label>
          </div>
          <p className="account-editor-note">{recurrence ? "Les prochaines projections et propositions de rapprochement seront recalculées." : "La récurrence alimentera immédiatement le prévisionnel et les propositions de rapprochement."}</p>
          {formError && <p className="account-form-error" role="alert">{formError}</p>}
          <footer>
            <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button>
            <button disabled={busy || availableCategories.length === 0 || accounts.length === 0} type="submit">{busy ? "Enregistrement…" : recurrence ? "Enregistrer les modifications" : "Créer la récurrence"}</button>
          </footer>
        </form>
      </aside>
    </div>
  );
}

function ForecastDayDetails({
  onClose,
  onCompleted,
  onEdit,
  point,
  recurrences,
  token,
}: {
  onClose: () => void;
  onCompleted: (result: RecurrenceActionResult) => void;
  onEdit: (item: RecurrenceItem) => void;
  point: ForecastPoint;
  recurrences: RecurrenceItem[];
  token: string;
}) {
  const [deletingId, setDeletingId] = useState<number>();
  const [error, setError] = useState<string>();
  const dailyNet = point.events.reduce((sum, event) => sum + event.amount, 0);

  async function remove(item: RecurrenceItem) {
    if (!window.confirm(`Supprimer définitivement la récurrence « ${item.name} » ?`)) return;
    setDeletingId(item.id);
    setError(undefined);
    try {
      onCompleted(await deleteRecurrence(token, item.id));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La récurrence ne peut pas être supprimée.");
      setDeletingId(undefined);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !deletingId && onClose()}>
      <aside aria-labelledby="forecast-day-title" aria-modal="true" className="account-editor forecast-day-details" role="dialog">
        <header>
          <div>
            <span className="eyebrow">Trésorerie prévisionnelle</span>
            <h2 id="forecast-day-title">{formatDate(point.date)}</h2>
          </div>
          <button aria-label="Fermer" disabled={Boolean(deletingId)} onClick={onClose} type="button">×</button>
        </header>
        <div className="forecast-day-details__body">
          <div className="forecast-day-details__summary">
            <div><span>Solde prévu</span><strong>{formatMoney(point.balance)}</strong></div>
            <div><span>Impact du jour</span><strong className={dailyNet >= 0 ? "positive" : "negative"}>{signedMoney(dailyNet)}</strong></div>
            <div><span>Mouvements</span><strong>{point.events.length}</strong></div>
          </div>
          {error && <p className="account-form-error" role="alert">{error}</p>}
          <div className="forecast-day-details__list">
            {point.events.map((event, index) => {
              const recurrence = event.recurringId === null
                ? undefined
                : recurrences.find((item) => item.id === event.recurringId);
              return (
                <article className="forecast-day-event" key={`${event.source}-${event.name}-${index}`}>
                  <div className="forecast-day-event__marker" data-source={event.source} aria-hidden="true" />
                  <div className="forecast-day-event__main">
                    <div className="forecast-day-event__heading">
                      <div>
                        <span>{event.source}</span>
                        <strong>{event.name}</strong>
                      </div>
                      <b className={event.amount >= 0 ? "positive" : "negative"}>{signedMoney(event.amount)}</b>
                    </div>
                    <p>{event.account} · {event.category}{event.scenario && event.scenario !== "Tous" ? ` · ${event.scenario}` : ""}</p>
                    {recurrence && (
                      <div className="forecast-day-event__actions">
                        <button className="secondary-button" disabled={Boolean(deletingId)} onClick={() => onEdit(recurrence)} type="button">Modifier la récurrence</button>
                        <button className="danger-button" disabled={Boolean(deletingId)} onClick={() => void remove(recurrence)} type="button">
                          {deletingId === recurrence.id ? "Suppression…" : "Supprimer"}
                        </button>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
            {point.events.length === 0 && (
              <div className="forecast-day-details__empty">
                <strong>Aucune opération ce jour</strong>
                <p>Le solde reste inchangé entre les deux points de la courbe.</p>
              </div>
            )}
          </div>
          <footer>
            <button className="secondary-button" disabled={Boolean(deletingId)} onClick={onClose} type="button">Fermer</button>
          </footer>
        </div>
      </aside>
    </div>
  );
}

function RecurrenceManager({
  accountId,
  items,
  onClose,
  onCompleted,
  onEdit,
  token,
}: {
  accountId: string;
  items: RecurrenceItem[];
  onClose: () => void;
  onCompleted: (result: RecurrenceActionResult) => void;
  onEdit: (item: RecurrenceItem) => void;
  token: string;
}) {
  const [deletingId, setDeletingId] = useState<number>();
  const [error, setError] = useState<string>();
  const visibleItems = accountId === "all"
    ? items
    : items.filter((item) => item.accountId === Number(accountId));

  async function remove(item: RecurrenceItem) {
    if (!window.confirm(`Supprimer définitivement la récurrence « ${item.name} » ?`)) return;
    setDeletingId(item.id);
    setError(undefined);
    try {
      onCompleted(await deleteRecurrence(token, item.id));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La récurrence ne peut pas être supprimée.");
      setDeletingId(undefined);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !deletingId && onClose()}>
      <aside aria-labelledby="recurrence-manager-title" aria-modal="true" className="account-editor recurrence-manager" role="dialog">
        <header>
          <div>
            <span className="eyebrow">Prévisionnel</span>
            <h2 id="recurrence-manager-title">Gérer les récurrences</h2>
          </div>
          <button aria-label="Fermer" disabled={Boolean(deletingId)} onClick={onClose} type="button">×</button>
        </header>
        <div className="recurrence-manager__body">
          <div className="recurrence-manager__summary">
            <strong>{visibleItems.length} récurrence(s)</strong>
            <span>{accountId === "all" ? "Tous les comptes" : "Compte sélectionné"}</span>
          </div>
          {error && <p className="account-form-error" role="alert">{error}</p>}
          <div className="recurrence-manager__list">
            {visibleItems.map((item) => (
              <article className="recurrence-manager__item" key={item.id}>
                <div className="recurrence-manager__item-main">
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.bank ? `${item.bank} · ` : ""}{item.accountName}</span>
                  </div>
                  <b className={item.direction === "Crédit" ? "positive" : "negative"}>
                    {signedMoney(item.direction === "Crédit" ? item.amount : -item.amount)}
                  </b>
                </div>
                <div className="recurrence-manager__meta">
                  <span>{item.category}</span>
                  <span>{item.frequency}</span>
                  <span>Prochaine : {formatDate(item.nextDate)}</span>
                  <span className={item.status === "Actif" ? "recurrence-status recurrence-status--active" : "recurrence-status"}>
                    {item.status}
                  </span>
                </div>
                <div className="recurrence-manager__actions">
                  <button className="secondary-button" disabled={Boolean(deletingId)} onClick={() => onEdit(item)} type="button">Modifier</button>
                  <button className="danger-button" disabled={Boolean(deletingId)} onClick={() => void remove(item)} type="button">
                    {deletingId === item.id ? "Suppression…" : "Supprimer"}
                  </button>
                </div>
              </article>
            ))}
            {visibleItems.length === 0 && <p className="forecast-empty">Aucune récurrence pour ce filtre.</p>}
          </div>
          <footer>
            <button className="secondary-button" disabled={Boolean(deletingId)} onClick={onClose} type="button">Fermer</button>
          </footer>
        </div>
      </aside>
    </div>
  );
}

function compatibleCategories(categories: ForecastCategory[], direction: RecurrencePayload["direction"]): ForecastCategory[] {
  const expected = direction === "Crédit" ? "Recette" : "Dépense";
  return categories.filter((category) => category.direction === expected || category.direction === "Neutre");
}

function isScenario(value: string): value is RecurrencePayload["scenario"] {
  return value === "Prudent" || value === "Réaliste" || value === "Optimiste";
}

function today(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

function ScenarioButton({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button aria-selected={active} className={active ? "forecast-scenario forecast-scenario--active" : "forecast-scenario"} onClick={onClick} role="tab" type="button">{children}</button>;
}

function ForecastChart({ onPointSelect, snapshot }: { onPointSelect: (point: ForecastPoint) => void; snapshot: ForecastSnapshot }) {
  return (
    <InteractiveLineChart
      ariaLabel={`Projection ${snapshot.filters.scenario} sur ${snapshot.filters.horizonDays} jours`}
      onPointSelect={(index) => {
        const point = snapshot.series.selected[index];
        if (point) onPointSelect(point);
      }}
      series={[
        {
          id: "selected",
          label: `Solde prévu · ${snapshot.filters.scenario}`,
          color: "#2563eb",
          area: true,
          points: snapshot.series.selected.map((point) => ({
            date: point.date,
            value: point.balance,
            details: (point.events ?? []).map((event) => ({
              label: event.name,
              meta: `${event.source} · ${event.account}`,
              value: event.amount,
              color: event.source === "Récurrence" ? "#7c3aed" : event.amount >= 0 ? "#16a34a" : "#dc2626",
            })),
          })),
        },
        {
          id: "realized",
          label: "Réalisé",
          color: "#06a9c2",
          points: snapshot.series.realized.map((point) => ({ date: point.date, value: point.balance })),
        },
        {
          id: "prudent",
          label: "Scénario prudent",
          color: "#e11d48",
          dashed: true,
          points: snapshot.series.prudent.map((point) => ({ date: point.date, value: point.balance })),
        },
      ]}
      valueFormatter={formatMoney}
    />
  );
}

function ForecastSummaryCard({ badge, label, meta, tone, value }: { badge: string; label: string; meta: string; tone: "blue" | "success" | "warning"; value: string }) {
  return (
    <section className="forecast-summary-card">
      <h3>{label}</h3>
      <strong>{value}</strong>
      <p>{meta}</p>
      <span className={`forecast-badge forecast-badge--${tone}`}>{badge}</span>
    </section>
  );
}

function UpcomingEvent({ event }: { event: ForecastEvent }) {
  const tone = event.amount > 0 ? "success" : event.category.toLocaleLowerCase("fr").includes("épargne") ? "cyan" : "warning";
  return (
    <div className="forecast-event">
      <div><strong>{event.name}</strong><span>{formatDate(event.date)} · {signedMoney(event.amount)}</span></div>
      <span className={`forecast-badge forecast-badge--${tone}`}>Prévue</span>
    </div>
  );
}

function Metric({ label, tone, value }: { label: string; tone: "blue" | "negative" | "positive"; value: string }) {
  return <div className="forecast-metric"><span>{label}</span><strong className={`forecast-metric__value forecast-metric__value--${tone}`}>{value}</strong></div>;
}

function percentageChange(start: number, end: number): string {
  if (!start) return "Projection calculée";
  const change = ((end - start) / Math.abs(start)) * 100;
  return `${change >= 0 ? "+ " : "- "}${Math.abs(change).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

function signedMoney(value: number): string {
  if (value === 0) return formatMoney(value);
  return `${value > 0 ? "+ " : "- "}${formatMoney(Math.abs(value))}`;
}

function formatMoney(value: number): string {
  return currencyFormatter.format(value);
}

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}