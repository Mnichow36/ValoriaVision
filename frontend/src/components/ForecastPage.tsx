import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { deleteRecurrence, getForecast, getScenarioSettings, updateSafetyThreshold } from "../api/client";
import type { ForecastAccount, ForecastEvent, ForecastPoint, ForecastSnapshot, OccurrenceRescheduleResult, RecurrenceActionResult, RecurrenceItem, ReschedulableOccurrence, ReschedulableOccurrencesResult, ScenarioActionResult, ScenarioSettingsSnapshot } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { ForecastStepChart } from "./ForecastStepChart";
import { SideDrawer } from "./SideDrawer";
import { ScenarioManager } from "./ScenarioManager";
import { RecurrenceEditor } from "./RecurrenceEditor";

interface ForecastPageProps {
  accountId: string;
  editorRequestKey: number;
  horizonDays: number;
  onAccountsChange: (accounts: ForecastAccount[]) => void;
  onDataChanged: () => void;
  onOpenRecurrences: () => void;
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

export function ForecastPage({ accountId, editorRequestKey, horizonDays, onAccountsChange, onDataChanged, onOpenRecurrences, onScenarioChange, scenario, token }: ForecastPageProps) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [editorOpen, setEditorOpen] = useState(false);
  const [thresholdOpen, setThresholdOpen] = useState(false);
  const [menu, setMenu] = useState<ContextMenuState>();
  const [scenarioManagerOpen, setScenarioManagerOpen] = useState(false);
  const [scenarioCatalog, setScenarioCatalog] = useState<ScenarioSettingsSnapshot>();
  const [visibleSeries, setVisibleSeries] = useState<Record<string, boolean>>({
    __realized: true,
    "Réaliste": true,
    "Prudent": true,
    "Optimiste": false,
  });
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
    const controller = new AbortController();
    getScenarioSettings(token, controller.signal)
      .then(setScenarioCatalog)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setNotice(cause instanceof Error ? cause.message : "Les scénarios ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [refreshKey, token]);

  useEffect(() => {
    if (editorRequestKey > 0 && editorRequestKey !== lastEditorRequestKey.current) {
      lastEditorRequestKey.current = editorRequestKey;
      setEditingRecurrence(undefined);
      setSelectedPoint(undefined);
      setEditorOpen(true);
    }
  }, [editorRequestKey]);

  function openEventMenu(event: React.MouseEvent, item: ForecastEvent) {
    event.preventDefault();
    const rule = item.recurringId === null ? undefined : snapshot?.recurrences.find((recurrence) => recurrence.id === item.recurringId);
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Voir dans Récurrences", onSelect: onOpenRecurrences },
        { label: "Modifier la règle…", disabled: !rule, onSelect: () => { if (rule) { setEditingRecurrence(rule); setEditorOpen(true); } } },
      ],
    });
  }

  function completed(result: { message: string }) {
    setEditorOpen(false);
    setScenarioManagerOpen(false);
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
      <div className="forecast-v2">
        {notice && <div className="transaction-notice forecast-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
        <section aria-label="Synthèse du prévisionnel" className="forecast-kpis">
          <div className="forecast-kpi">
            <span>Solde aujourd’hui</span>
            <strong>{formatMoney(snapshot.summary.startingCash)}</strong>
            <small>{snapshot.filters.accountLabel}, au {formatDate(snapshot.filters.referenceDate)}</small>
          </div>
          <div className="forecast-kpi">
            <span>Point bas</span>
            <strong>{formatMoney(snapshot.summary.lowBalance)}</strong>
            <small>Atteint le {formatDate(snapshot.summary.lowDate)}</small>
          </div>
          <div className="forecast-kpi">
            <span>Solde au {formatDate(snapshot.summary.endDate)}</span>
            <strong>{formatMoney(snapshot.summary.endBalance)}</strong>
            <small className="forecast-kpi__positive">{signedMoney(snapshot.summary.endBalance - snapshot.summary.startingCash)} · {percentageChange(snapshot.summary.startingCash, snapshot.summary.endBalance)}</small>
          </div>
          <div className="forecast-kpi">
            <span>Écart scénario prudent</span>
            <strong>{signedMoney(snapshot.summary.prudentDifference)}</strong>
            <small>sur le solde final</small>
          </div>
          <button
            className={snapshot.summary.safetyThreshold > 0 && snapshot.summary.daysBelowThreshold > 0 ? "forecast-kpi forecast-kpi--alert" : "forecast-kpi forecast-kpi--ok"}
            onClick={() => setThresholdOpen(true)}
            title="Régler le seuil de sécurité"
            type="button"
          >
            <span>Seuil de sécurité</span>
            <strong>{snapshot.summary.safetyThreshold > 0 ? (snapshot.summary.daysBelowThreshold > 0 ? `${snapshot.summary.daysBelowThreshold} jour${snapshot.summary.daysBelowThreshold > 1 ? "s" : ""} sous le seuil` : "0 jour sous le seuil") : "Non défini"}</strong>
            <small>{snapshot.summary.safetyThreshold > 0 ? `Seuil réglé à ${formatMoney(snapshot.summary.safetyThreshold)}` : "Cliquer pour le régler"}</small>
          </button>
        </section>

        <div className="forecast-v2__main">
          <article className="card forecast-projection forecast-projection--v2">
            <div className="forecast-card-heading">
              <div>
                <h2>Solde projeté, jour par jour</h2>
                <p>Du {formatDate(snapshot.filters.startDate)} au {formatDate(snapshot.filters.endDate)} · aucune prévision antérieure à aujourd’hui.</p>
              </div>
              <div className="forecast-heading-actions">
                {snapshot.summary.overdueOccurrences > 0 && (
                  <button className="occurrence-overdue-chip" onClick={onOpenRecurrences} title="Ouvrir les récurrences à décaler ou reporter" type="button">
                    {snapshot.summary.overdueOccurrences} prévision{snapshot.summary.overdueOccurrences > 1 ? "s" : ""} antérieure{snapshot.summary.overdueOccurrences > 1 ? "s" : ""} à traiter
                  </button>
                )}
                <ScenarioSelector
                  catalog={scenarioCatalog}
                  onManage={() => {
                    setEditorOpen(false);
                    setSelectedPoint(undefined);
                    setScenarioManagerOpen(true);
                  }}
                  onScenarioChange={onScenarioChange}
                  onVisibilityChange={(name) => {
                    setVisibleSeries((current) => ({
                      ...current,
                      [name]: !(current[name] ?? name === scenario),
                    }));
                  }}
                  scenario={scenario}
                  visibleSeries={visibleSeries}
                />
              </div>
            </div>
            <div className="forecast-legend">
              <span><i style={{ background: "#2563eb" }} />{snapshot.filters.scenario}</span>
              {scenario !== "Prudent" && visibleSeries.Prudent && <span><i className="forecast-legend__dash" />Prudent</span>}
              {snapshot.summary.safetyThreshold > 0 && <span><i className="forecast-legend__threshold" />Seuil</span>}
            </div>
            <div className="forecast-step-host">
              <ForecastStepChart
                comparison={scenario !== "Prudent" && visibleSeries.Prudent ? { label: "Prudent", points: snapshot.series.prudent } : undefined}
                onPointSelect={setSelectedPoint}
                points={snapshot.series.selected}
                referenceDate={snapshot.filters.referenceDate}
                scenarioLabel={snapshot.filters.scenario}
                threshold={snapshot.summary.safetyThreshold}
              />
            </div>
          </article>

          <article className="card forecast-upcoming forecast-upcoming--v2">
            <div className="forecast-card-heading">
              <h2>Prochaines échéances</h2>
              <span className="forecast-count">{Math.min(10, snapshot.upcoming.length)} sur {snapshot.upcoming.length}</span>
            </div>
            <div className="forecast-upcoming-list forecast-upcoming-list--v2">
              {snapshot.upcoming.length > 0
                ? snapshot.upcoming.slice(0, 10).map((event, index) => (
                  <div className="forecast-row" key={`${event.date}-${event.name}-${index}`} onContextMenu={(mouseEvent) => openEventMenu(mouseEvent, event)}>
                    <span className="forecast-row__date">{shortDay(event.date)}</span>
                    <strong className="forecast-row__label" title={event.name}>{event.name}{event.source === "Récurrence décalée" ? " · décalée" : ""}</strong>
                    <span className={event.amount >= 0 ? "forecast-row__amount positive" : "forecast-row__amount negative"}>{signedMoney(event.amount)}</span>
                  </div>
                ))
                : <p className="forecast-empty">Aucune récurrence sur cette période.</p>}
            </div>
            <div className="forecast-upcoming__footer">
              <span>Clic droit sur une ligne : voir ou modifier la règle.</span>
              <button className="forecast-link" onClick={onOpenRecurrences} type="button">Tout voir dans Récurrences →</button>
            </div>
          </article>
        </div>
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
      {scenarioManagerOpen && scenarioCatalog && (
        <ScenarioManager
          catalog={scenarioCatalog}
          onChanged={(result: ScenarioActionResult) => {
            setNotice(result.message);
            setRefreshKey((key) => key + 1);
            onDataChanged();
          }}
          onClose={() => setScenarioManagerOpen(false)}
          token={token}
        />
      )}
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
      {thresholdOpen && (
        <SafetyThresholdDrawer
          current={snapshot.summary.safetyThreshold}
          onClose={() => setThresholdOpen(false)}
          onSaved={(message) => {
            setThresholdOpen(false);
            setNotice(message);
            setRefreshKey((key) => key + 1);
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
  const recurringEvents = point.events.filter((event) => event.source.startsWith("Récurrence"));
  const otherEvents = point.events.filter((event) => !event.source.startsWith("Récurrence"));
  const groups = [
    {
      id: "recurrences",
      title: "Échéances récurrentes",
      description: "Opérations planifiées qui expliquent la variation de trésorerie.",
      events: recurringEvents,
    },
    {
      id: "operations",
      title: "Autres mouvements",
      description: "Opérations réalisées ou hypothèses ponctuelles de la journée.",
      events: otherEvents,
    },
  ].filter((group) => group.events.length > 0);

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
            <span className="eyebrow">Détail des opérations</span>
            <h2 id="forecast-day-title">{formatDate(point.date)}</h2>
          </div>
          <button aria-label="Fermer" disabled={Boolean(deletingId)} onClick={onClose} type="button">×</button>
        </header>
        <div className="forecast-day-details__body">
          <div className="forecast-day-details__summary">
            <div><span>Solde prévu</span><strong>{formatMoney(point.balance)}</strong></div>
            <div><span>Impact du jour</span><strong className={dailyNet >= 0 ? "positive" : "negative"}>{signedMoney(dailyNet)}</strong></div>
            <div><span>Échéances récurrentes</span><strong>{recurringEvents.length}</strong></div>
            <div><span>Autres mouvements</span><strong>{otherEvents.length}</strong></div>
          </div>
          {error && <p className="account-form-error" role="alert">{error}</p>}
          <div className="forecast-day-details__list">
            {groups.map((group) => (
              <section className="forecast-day-group" key={group.id}>
                <div className="forecast-day-group__heading">
                  <div><strong>{group.title}</strong><span>{group.description}</span></div>
                  <b>{group.events.length}</b>
                </div>
                <div className="forecast-day-group__rows">
                  {group.events.map((event, index) => {
                    const recurrence = event.recurringId === null
                      ? undefined
                      : recurrences.find((item) => item.id === event.recurringId);
                    return (
                      <article className="forecast-day-event" key={`${event.source}-${event.name}-${index}`}>
                        <div className="forecast-day-event__marker" data-source={event.source} aria-hidden="true" />
                        <div className="forecast-day-event__main">
                          <div className="forecast-day-event__heading">
                            <div>
                              <span>{event.source || "Opération"}</span>
                              <strong>{event.name}</strong>
                            </div>
                            <b className={event.amount >= 0 ? "positive" : "negative"}>{signedMoney(event.amount)}</b>
                          </div>
                          <div className="forecast-day-event__meta">
                            <span>{event.account}</span>
                            <span>{event.category}</span>
                            {event.scenario && event.scenario !== "Tous" && <span>{event.scenario}</span>}
                            {event.originalDate && event.originalDate !== event.date && <span>Initialement le {formatDate(event.originalDate)}</span>}
                          </div>
                          {recurrence && (
                            <div className="forecast-day-event__actions">
                              <button className="secondary-button" disabled={Boolean(deletingId)} onClick={() => onEdit(recurrence)} type="button">Modifier la règle</button>
                              <button className="danger-button" disabled={Boolean(deletingId)} onClick={() => void remove(recurrence)} type="button">
                                {deletingId === recurrence.id ? "Suppression…" : "Supprimer"}
                              </button>
                            </div>
                          )}
                        </div>
                      </article>
                    );
                  })}
                </div>
              </section>
            ))}
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

const STANDARD_SCENARIOS = [
  { name: "Réaliste", color: "#2563eb", description: "Hypothèses centrales" },
  { name: "Prudent", color: "#e11d48", description: "Vision de vigilance" },
  { name: "Optimiste", color: "#7c3aed", description: "Hypothèses favorables" },
];

const CUSTOM_SCENARIO_COLORS = ["#f59e0b", "#0891b2", "#db2777", "#65a30d", "#9333ea"];

function ScenarioSelector({
  catalog,
  onManage,
  onScenarioChange,
  onVisibilityChange,
  scenario,
  visibleSeries,
}: {
  catalog?: ScenarioSettingsSnapshot;
  onManage: () => void;
  onScenarioChange: (scenario: string) => void;
  onVisibilityChange: (scenario: string) => void;
  scenario: string;
  visibleSeries: Record<string, boolean>;
}) {
  const standard = STANDARD_SCENARIOS.map((option) => {
    const preset = catalog?.presets.find((item) => item.name === option.name);
    return {
      ...option,
      description: preset
        ? `Recettes ${preset.incomePercent} % · dépenses ${preset.expensePercent} %`
        : option.description,
    };
  });
  const custom = (catalog?.scenarios ?? [])
    .filter((item) => !item.isReference && item.isActive)
    .map((item, index) => ({
      name: item.name,
      color: CUSTOM_SCENARIO_COLORS[index % CUSTOM_SCENARIO_COLORS.length],
      description: `${item.eventCount} hypothèse${item.eventCount > 1 ? "s" : ""}`,
    }));
  const options = [...standard, ...custom];
  const active = options.find((option) => option.name === scenario) ?? options[0];

  return (
    <details className="scenario-picker">
      <summary>
        <i style={{ background: active.color }} />
        <span><small>Scénario principal</small><strong>{active.name}</strong></span>
        <b aria-hidden="true">⌄</b>
      </summary>
      <div className="scenario-picker__menu">
        <div className="scenario-picker__title">
          <span>Courbes comparées</span>
          <small>Choisir le scénario principal</small>
        </div>
        <div className="scenario-picker__row scenario-picker__row--realized">
          <button
            aria-label={visibleSeries.__realized ? "Masquer le réalisé" : "Afficher le réalisé"}
            className={visibleSeries.__realized ? "scenario-visibility scenario-visibility--on" : "scenario-visibility"}
            onClick={() => onVisibilityChange("__realized")}
            type="button"
          >
            <EyeIcon visible={Boolean(visibleSeries.__realized)} />
          </button>
          <i style={{ background: "#06a9c2" }} />
          <span><strong>Réalisé</strong><small>Solde issu des opérations bancaires</small></span>
        </div>
        {options.map((option) => {
          const selected = option.name === scenario;
          const visible = selected || Boolean(visibleSeries[option.name]);
          return (
            <div className={selected ? "scenario-picker__row scenario-picker__row--selected" : "scenario-picker__row"} key={option.name}>
              <button
                aria-label={visible ? `Masquer ${option.name}` : `Afficher ${option.name}`}
                className={visible ? "scenario-visibility scenario-visibility--on" : "scenario-visibility"}
                disabled={selected}
                onClick={() => onVisibilityChange(option.name)}
                type="button"
              >
                <EyeIcon visible={visible} />
              </button>
              <i style={{ background: option.color }} />
              <button className="scenario-picker__select" onClick={() => onScenarioChange(option.name)} type="button">
                <span><strong>{option.name}</strong><small>{option.description}</small></span>
                {selected && <b>Principal</b>}
              </button>
            </div>
          );
        })}
        <button className="scenario-picker__manage" onClick={onManage} type="button">
          <span aria-hidden="true">＋</span>
          Gérer et paramétrer les scénarios
        </button>
      </div>
    </details>
  );
}

function EyeIcon({ visible }: { visible: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.8" />
      {!visible && <path d="M4 4 20 20" />}
    </svg>
  );
}

function SafetyThresholdDrawer({ current, onClose, onSaved, token }: { current: number; onClose: () => void; onSaved: (message: string) => void; token: string }) {
  const [value, setValue] = useState(String(current || "").replace(".", ","));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function save() {
    const amount = Number((value || "0").replace(/\s/g, "").replace(",", "."));
    if (!Number.isFinite(amount) || amount < 0) { setError("Saisis un montant positif (0 pour désactiver le seuil)."); return; }
    setBusy(true);
    setError(undefined);
    try {
      onSaved((await updateSafetyThreshold(token, amount)).message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Le seuil n’a pas pu être enregistré.");
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Prévisionnel"
      footer={(<><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} onClick={() => void save()} type="button">{busy ? "Enregistrement…" : "Enregistrer"}</button></>)}
      onClose={onClose}
      title="Seuil de sécurité"
    >
      <p className="drawer-help">Solde minimum que tu souhaites garder, tous comptes confondus. Le graphique trace ce seuil et compte les jours où le solde projeté passe en dessous. 0 désactive le seuil.</p>
      <label className="account-field"><span>Seuil</span><div className="rules-input"><input inputMode="decimal" onChange={(event) => setValue(event.target.value)} value={value} /><b>€</b></div></label>
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}

function shortDay(value: string): string {
  const parts = value.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : value;
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