import { type FormEvent, useMemo, useState } from "react";

import { createRecurrence, updateRecurrence } from "../api/client";
import type { ForecastAccount, ForecastCategory, RecurrenceActionResult, RecurrenceItem, RecurrencePayload } from "../api/contracts";

export function RecurrenceEditor({
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
              <span>Date de départ du calendrier *</span>
              <input onChange={(event) => field("nextDate", event.target.value)} required type="date" value={draft.nextDate} />
              <small>Cette date sert d’ancrage à la fréquence ; la prochaine échéance est recalculée automatiquement.</small>
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
