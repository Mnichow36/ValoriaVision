import { type FormEvent, useState } from "react";

import {
  createScenario,
  createScenarioEvent,
  deleteScenario,
  deleteScenarioEvent,
  duplicateScenario,
  updateScenario,
  updateScenarioEvent,
  updateScenarioPreset,
} from "../api/client";
import type {
  ScenarioActionResult,
  ScenarioDefinition,
  ScenarioEventItem,
  ScenarioEventPayload,
  ScenarioPayload,
  ScenarioPreset,
  ScenarioPresetPayload,
  ScenarioSettingsSnapshot,
} from "../api/contracts";

interface ScenarioManagerProps {
  catalog: ScenarioSettingsSnapshot;
  onChanged: (result: ScenarioActionResult) => void;
  onClose: () => void;
  token: string;
}

const money = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

const date = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
});

export function ScenarioManager({ catalog, onChanged, onClose, token }: ScenarioManagerProps) {
  const [scenarioEditor, setScenarioEditor] = useState<ScenarioDefinition | "new">();
  const [eventEditor, setEventEditor] = useState<{ scenario: ScenarioDefinition; event?: ScenarioEventItem }>();
  const [busyKey, setBusyKey] = useState<string>();
  const [error, setError] = useState<string>();
  const customScenarios = catalog.scenarios.filter((item) => !item.isReference);

  async function action(key: string, operation: () => Promise<ScenarioActionResult>) {
    setBusyKey(key);
    setError(undefined);
    try {
      onChanged(await operation());
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "L’action ne peut pas être réalisée.");
    } finally {
      setBusyKey(undefined);
    }
  }

  return (
    <div className="account-editor-backdrop scenario-manager-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busyKey && onClose()}>
      <aside aria-labelledby="scenario-manager-title" aria-modal="true" className="account-editor scenario-manager" role="dialog">
        <header>
          <div>
            <span className="eyebrow">Prévisionnel</span>
            <h2 id="scenario-manager-title">Gestion des scénarios</h2>
            <p>Créez des variantes et paramétrez les hypothèses qui modifient réellement la trésorerie.</p>
          </div>
          <button aria-label="Fermer" disabled={Boolean(busyKey)} onClick={onClose} type="button">×</button>
        </header>

        <div className="scenario-manager__toolbar">
          <div>
            <strong>Scénarios standards contrôlables</strong>
            <span>Réglez séparément l’impact des recettes et des dépenses prévisionnelles.</span>
          </div>
          <button className="primary-button" onClick={() => setScenarioEditor("new")} type="button">+ Nouveau scénario</button>
        </div>

        {error && <div className="account-editor-error" role="alert">{error}</div>}

        <div className="scenario-manager__list">
          <section className="scenario-preset-section" aria-labelledby="scenario-preset-title">
            <div className="scenario-preset-section__heading">
              <div>
                <strong id="scenario-preset-title">Hypothèses automatiques</strong>
                <span>Les coefficients s’appliquent aux récurrences futures. Les opérations bancaires réelles ne sont jamais modifiées.</span>
              </div>
              <span className="scenario-preset-section__badge">Courbes recalculées immédiatement</span>
            </div>
            <div className="scenario-preset-grid">
              {(catalog.presets ?? []).map((preset) => (
                <ScenarioPresetCard
                  busy={busyKey === `preset-${preset.name}`}
                  key={`${preset.name}-${preset.incomePercent}-${preset.expensePercent}`}
                  onSave={(payload) => action(
                    `preset-${preset.name}`,
                    () => updateScenarioPreset(token, preset.name, payload),
                  )}
                  preset={preset}
                />
              ))}
            </div>
          </section>

          <div className="scenario-manager__custom-heading">
            <strong>Scénarios personnalisés</strong>
            <span>Ajoutez des projets et hypothèses datées en complément du scénario réaliste.</span>
          </div>

          {customScenarios.length === 0 && (
            <div className="scenario-manager__empty">
              <strong>Aucun scénario personnalisé</strong>
              <span>Créez une variante, puis ajoutez des recettes, dépenses ou projets datés.</span>
            </div>
          )}
          {customScenarios.map((item) => (
            <article className={item.isActive ? "scenario-card" : "scenario-card scenario-card--inactive"} key={item.id}>
              <div className="scenario-card__heading">
                <div className="scenario-card__identity">
                  <i aria-hidden="true" />
                  <div>
                    <strong>{item.name}</strong>
                    <span>{item.scenarioType} · horizon {item.horizonMonths} mois</span>
                  </div>
                </div>
                <span className={item.isActive ? "scenario-status scenario-status--active" : "scenario-status"}>{item.isActive ? "Actif" : "Masqué"}</span>
              </div>
              {item.description && <p className="scenario-card__description">{item.description}</p>}
              <div className="scenario-card__meta">
                <span>Départ <b>{formatDate(item.startDate)}</b></span>
                <span><b>{item.eventCount}</b> hypothèse{item.eventCount > 1 ? "s" : ""}</span>
              </div>

              <div className="scenario-card__events">
                {item.events.length === 0
                  ? <p>Aucune hypothèse : la courbe reste identique au scénario réaliste.</p>
                  : item.events.map((event) => (
                    <div className={event.isActive ? "scenario-event-row" : "scenario-event-row scenario-event-row--inactive"} key={event.id}>
                      <span className={event.sense.includes("Entrée") ? "scenario-event-row__icon scenario-event-row__icon--in" : "scenario-event-row__icon scenario-event-row__icon--out"} aria-hidden="true">
                        {event.sense.includes("Entrée") ? "↗" : "↘"}
                      </span>
                      <div>
                        <strong>{event.label}</strong>
                        <span>{event.eventTypeLabel} · {formatDate(event.eventDate)}{event.frequency !== "once" ? ` · ${event.frequencyLabel}` : ""}</span>
                      </div>
                      <b className={event.sense.includes("Entrée") ? "positive" : "negative"}>
                        {event.sense.includes("Entrée") ? "+ " : "- "}{money.format(Math.abs(event.amount))}
                      </b>
                      <button className="scenario-icon-button" onClick={() => setEventEditor({ scenario: item, event })} type="button">Modifier</button>
                      <button
                        className="scenario-icon-button scenario-icon-button--danger"
                        disabled={busyKey === `event-${event.id}`}
                        onClick={() => {
                          if (window.confirm(`Supprimer l’hypothèse « ${event.label} » ?`)) {
                            void action(`event-${event.id}`, () => deleteScenarioEvent(token, event.id));
                          }
                        }}
                        type="button"
                      >
                        Supprimer
                      </button>
                    </div>
                  ))}
              </div>

              <footer className="scenario-card__actions">
                <button onClick={() => setEventEditor({ scenario: item })} type="button">+ Ajouter une hypothèse</button>
                <button className="secondary-button" onClick={() => setScenarioEditor(item)} type="button">Paramétrer</button>
                <button
                  className="secondary-button"
                  disabled={busyKey === `duplicate-${item.id}`}
                  onClick={() => void action(`duplicate-${item.id}`, () => duplicateScenario(token, item.id))}
                  type="button"
                >
                  Dupliquer
                </button>
                <button
                  className="danger-button"
                  disabled={busyKey === `delete-${item.id}`}
                  onClick={() => {
                    if (window.confirm(`Supprimer le scénario « ${item.name} » et ses hypothèses ?`)) {
                      void action(`delete-${item.id}`, () => deleteScenario(token, item.id));
                    }
                  }}
                  type="button"
                >
                  Supprimer
                </button>
              </footer>
            </article>
          ))}
        </div>

        {scenarioEditor && (
          <ScenarioEditor
            catalog={catalog}
            onCancel={() => setScenarioEditor(undefined)}
            onSaved={(result) => {
              setScenarioEditor(undefined);
              onChanged(result);
            }}
            scenario={scenarioEditor === "new" ? undefined : scenarioEditor}
            token={token}
          />
        )}
        {eventEditor && (
          <ScenarioEventEditor
            catalog={catalog}
            event={eventEditor.event}
            onCancel={() => setEventEditor(undefined)}
            onSaved={(result) => {
              setEventEditor(undefined);
              onChanged(result);
            }}
            scenario={eventEditor.scenario}
            token={token}
          />
        )}
      </aside>
    </div>
  );
}

function ScenarioPresetCard({
  busy,
  onSave,
  preset,
}: {
  busy: boolean;
  onSave: (payload: ScenarioPresetPayload) => Promise<void>;
  preset: ScenarioPreset;
}) {
  const [draft, setDraft] = useState<ScenarioPresetPayload>({
    incomePercent: preset.incomePercent,
    expensePercent: preset.expensePercent,
  });
  const changed = draft.incomePercent !== preset.incomePercent
    || draft.expensePercent !== preset.expensePercent;
  const tone = preset.name === "Prudent"
    ? "prudent"
    : preset.name === "Optimiste"
      ? "optimistic"
      : "realistic";

  function setPercent(key: keyof ScenarioPresetPayload, value: string) {
    const parsed = Number(value);
    setDraft((current) => ({
      ...current,
      [key]: Number.isFinite(parsed) ? Math.min(300, Math.max(0, parsed)) : 0,
    }));
  }

  return (
    <article className={`scenario-preset-card scenario-preset-card--${tone}`}>
      <header className="scenario-preset-card__heading">
        <span className="scenario-preset-card__dot" style={{ background: preset.color }} aria-hidden="true" />
        <div>
          <strong>{preset.name}</strong>
          <span>{preset.description}</span>
        </div>
      </header>
      <div className="scenario-preset-card__controls">
        <label>
          <span>Recettes prévues</span>
          <div>
            <input
              aria-label={`Pourcentage des recettes du scénario ${preset.name}`}
              max="300"
              min="0"
              onChange={(event) => setPercent("incomePercent", event.target.value)}
              step="1"
              type="number"
              value={draft.incomePercent}
            />
            <b>%</b>
          </div>
          <small>{scenarioEffect(draft.incomePercent)}</small>
        </label>
        <label>
          <span>Dépenses prévues</span>
          <div>
            <input
              aria-label={`Pourcentage des dépenses du scénario ${preset.name}`}
              max="300"
              min="0"
              onChange={(event) => setPercent("expensePercent", event.target.value)}
              step="1"
              type="number"
              value={draft.expensePercent}
            />
            <b>%</b>
          </div>
          <small>{scenarioEffect(draft.expensePercent)}</small>
        </label>
      </div>
      <button
        className="scenario-preset-card__save"
        disabled={busy || !changed}
        onClick={() => void onSave(draft)}
        type="button"
      >
        {busy ? "Application…" : changed ? "Appliquer à la courbe" : "Paramètres appliqués"}
      </button>
    </article>
  );
}

function scenarioEffect(percent: number): string {
  const delta = Math.round((percent - 100) * 100) / 100;
  if (delta === 0) return "Montant inchangé";
  return delta > 0 ? `+${delta} % sur chaque récurrence` : `${delta} % sur chaque récurrence`;
}

function ScenarioEditor({
  catalog,
  onCancel,
  onSaved,
  scenario,
  token,
}: {
  catalog: ScenarioSettingsSnapshot;
  onCancel: () => void;
  onSaved: (result: ScenarioActionResult) => void;
  scenario?: ScenarioDefinition;
  token: string;
}) {
  const [draft, setDraft] = useState<ScenarioPayload>(() => ({
    name: scenario?.name ?? "",
    description: scenario?.description ?? "",
    scenarioType: scenario?.scenarioType ?? catalog.scenarioTypes[0] ?? "Projet libre",
    startDate: scenario?.startDate ?? today(),
    endDate: scenario?.endDate ?? "",
    horizonMonths: scenario?.horizonMonths ?? 12,
    currencyCode: scenario?.currencyCode ?? "EUR",
    isActive: scenario?.isActive ?? true,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  function field<Key extends keyof ScenarioPayload>(key: Key, value: ScenarioPayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      onSaved(scenario
        ? await updateScenario(token, scenario.id, draft)
        : await createScenario(token, draft));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Le scénario ne peut pas être enregistré.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scenario-form-layer">
      <form className="scenario-form" onSubmit={(event) => void submit(event)}>
        <div className="scenario-form__heading">
          <div><span className="eyebrow">Scénario</span><h3>{scenario ? "Paramétrer le scénario" : "Nouveau scénario"}</h3></div>
          <button aria-label="Fermer" disabled={busy} onClick={onCancel} type="button">×</button>
        </div>
        <label className="account-field account-field--wide">
          <span>Nom *</span>
          <input autoFocus maxLength={100} onChange={(event) => field("name", event.target.value)} required value={draft.name} />
        </label>
        <label className="account-field account-field--wide">
          <span>Description</span>
          <textarea onChange={(event) => field("description", event.target.value)} rows={3} value={draft.description} />
        </label>
        <div className="scenario-form__grid">
          <label className="account-field">
            <span>Type</span>
            <select onChange={(event) => field("scenarioType", event.target.value)} value={draft.scenarioType}>
              {catalog.scenarioTypes.map((option) => <option key={option}>{option}</option>)}
            </select>
          </label>
          <label className="account-field">
            <span>Horizon</span>
            <select onChange={(event) => field("horizonMonths", Number(event.target.value))} value={draft.horizonMonths}>
              {[3, 6, 12, 24, 36, 60].map((months) => <option key={months} value={months}>{months} mois</option>)}
            </select>
          </label>
          <label className="account-field">
            <span>Date de début *</span>
            <input onChange={(event) => field("startDate", event.target.value)} required type="date" value={draft.startDate} />
          </label>
          <label className="account-field">
            <span>Date de fin</span>
            <input min={draft.startDate} onChange={(event) => field("endDate", event.target.value)} type="date" value={draft.endDate} />
          </label>
        </div>
        <label className="scenario-switch">
          <input checked={draft.isActive} onChange={(event) => field("isActive", event.target.checked)} type="checkbox" />
          <span>Scénario actif et visible dans le sélecteur</span>
        </label>
        {error && <div className="account-editor-error" role="alert">{error}</div>}
        <footer>
          <button className="secondary-button" disabled={busy} onClick={onCancel} type="button">Annuler</button>
          <button disabled={busy} type="submit">{busy ? "Enregistrement…" : "Enregistrer"}</button>
        </footer>
      </form>
    </div>
  );
}

function ScenarioEventEditor({
  catalog,
  event,
  onCancel,
  onSaved,
  scenario,
  token,
}: {
  catalog: ScenarioSettingsSnapshot;
  event?: ScenarioEventItem;
  onCancel: () => void;
  onSaved: (result: ScenarioActionResult) => void;
  scenario: ScenarioDefinition;
  token: string;
}) {
  const [draft, setDraft] = useState<ScenarioEventPayload>(() => ({
    eventType: event?.eventType ?? "cash_out",
    label: event?.label ?? "",
    description: event?.description ?? "",
    eventDate: event?.eventDate ?? scenario.startDate ?? today(),
    endDate: event?.endDate ?? "",
    amount: Math.abs(event?.amount ?? 0),
    currencyCode: event?.currencyCode ?? "EUR",
    frequency: event?.frequency ?? "once",
    durationMonths: event?.durationMonths ?? 0,
    accountId: event?.accountId ?? null,
    isActive: event?.isActive ?? true,
  }));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const selectedType = catalog.eventTypes.find((option) => option.id === draft.eventType);

  function field<Key extends keyof ScenarioEventPayload>(key: Key, value: ScenarioEventPayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submit(formEvent: FormEvent<HTMLFormElement>) {
    formEvent.preventDefault();
    setBusy(true);
    setError(undefined);
    try {
      onSaved(event
        ? await updateScenarioEvent(token, event.id, draft)
        : await createScenarioEvent(token, scenario.id, draft));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "L’hypothèse ne peut pas être enregistrée.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="scenario-form-layer">
      <form className="scenario-form scenario-event-form" onSubmit={(formEvent) => void submit(formEvent)}>
        <div className="scenario-form__heading">
          <div><span className="eyebrow">{scenario.name}</span><h3>{event ? "Modifier l’hypothèse" : "Nouvelle hypothèse"}</h3></div>
          <button aria-label="Fermer" disabled={busy} onClick={onCancel} type="button">×</button>
        </div>
        <div className="scenario-form__grid">
          <label className="account-field account-field--wide">
            <span>Type d’impact *</span>
            <select onChange={(change) => field("eventType", change.target.value)} value={draft.eventType}>
              {catalog.eventTypes.map((option) => <option key={option.id} value={option.id}>{option.label} — {option.sense}</option>)}
            </select>
            <small>{selectedType?.nature} · {selectedType?.sense}</small>
          </label>
          <label className="account-field account-field--wide">
            <span>Libellé *</span>
            <input autoFocus maxLength={120} onChange={(change) => field("label", change.target.value)} required value={draft.label} />
          </label>
          <label className="account-field">
            <span>Montant *</span>
            <input min="0" onChange={(change) => field("amount", Number(change.target.value))} required step="0.01" type="number" value={draft.amount || ""} />
          </label>
          <label className="account-field">
            <span>Compte</span>
            <select onChange={(change) => field("accountId", change.target.value ? Number(change.target.value) : null)} value={draft.accountId ?? ""}>
              <option value="">Tous les comptes</option>
              {catalog.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}
            </select>
          </label>
          <label className="account-field">
            <span>Date d’effet *</span>
            <input onChange={(change) => field("eventDate", change.target.value)} required type="date" value={draft.eventDate} />
          </label>
          <label className="account-field">
            <span>Fréquence</span>
            <select onChange={(change) => field("frequency", change.target.value)} value={draft.frequency}>
              {catalog.frequencies.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
          </label>
          {draft.frequency !== "once" && (
            <>
              <label className="account-field">
                <span>Date de fin</span>
                <input min={draft.eventDate} onChange={(change) => field("endDate", change.target.value)} type="date" value={draft.endDate} />
              </label>
              <label className="account-field">
                <span>Durée (mois)</span>
                <input min="0" onChange={(change) => field("durationMonths", Number(change.target.value))} type="number" value={draft.durationMonths || ""} />
              </label>
            </>
          )}
          <label className="account-field account-field--wide">
            <span>Note</span>
            <textarea onChange={(change) => field("description", change.target.value)} rows={2} value={draft.description} />
          </label>
        </div>
        <label className="scenario-switch">
          <input checked={draft.isActive} onChange={(change) => field("isActive", change.target.checked)} type="checkbox" />
          <span>Hypothèse active dans la projection</span>
        </label>
        {error && <div className="account-editor-error" role="alert">{error}</div>}
        <footer>
          <button className="secondary-button" disabled={busy} onClick={onCancel} type="button">Annuler</button>
          <button disabled={busy} type="submit">{busy ? "Enregistrement…" : "Appliquer à la courbe"}</button>
        </footer>
      </form>
    </div>
  );
}

function formatDate(value: string): string {
  if (!value) return "Sans limite";
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : date.format(parsed);
}

function today(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}
