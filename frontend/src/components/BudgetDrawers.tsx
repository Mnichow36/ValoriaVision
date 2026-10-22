import { useEffect, useMemo, useState } from "react";

import { removeBudgetCategory, reviseBudget, saveBudgetCategory, saveBudgetRules } from "../api/client";
import type { BudgetRevision, BudgetsSnapshot } from "../api/contracts";
import { MONTH_SHORT, formatMoney, formatMoneyExact, monthLabel, monthShortLabel, parseAmount } from "./budgetFormat";
import { SideDrawer } from "./SideDrawer";

interface CommonProps {
  month: string;
  onClose: () => void;
  onSaved: (message: string) => void;
  snapshot: BudgetsSnapshot;
  token: string;
}

type Scope = "month" | "from" | "year";

function describeRevision(revision: BudgetRevision): string {
  const range = revision.fromMonth === revision.toMonth ? monthShortLabel(revision.fromMonth) : `${monthShortLabel(revision.fromMonth)} → ${monthShortLabel(revision.toMonth)}`;
  return `${formatMoney(revision.oldAmount)} → ${formatMoney(revision.newAmount)} · ${range}`;
}

function RevisionHistory({ initial, revisions }: { initial: number; revisions: BudgetRevision[] }) {
  return (
    <div className="bgt-history">
      <div className="bgt-history__title">Historique des révisions</div>
      <ol>
        <li><b>Initial</b> · {formatMoney(initial)} / mois</li>
        {revisions.map((revision) => (
          <li key={revision.id}>
            <b>Révision</b> · {describeRevision(revision)}
            {revision.reason && <em> — {revision.reason}</em>}
          </li>
        ))}
      </ol>
      <small>Le budget initial est toujours conservé : tu peux comparer « initial » et « révisé » dans l’onglet Budget comparatif.</small>
    </div>
  );
}

/** Volet « Réviser le budget » : change le montant sur une portée choisie, avec historique. */
export function ReviseDrawer({ category: initialCategory, month, onClose, onSaved, snapshot, token }: CommonProps & { category: string }) {
  const categories = snapshot.annual.categories;
  const [category, setCategory] = useState(initialCategory);
  const data = categories.find((item) => item.category === category);
  const monthIndex = Number(month.slice(5, 7)) - 1;
  const current = data?.planned[monthIndex] ?? 0;
  const [amount, setAmount] = useState(String(current).replace(".", ","));
  const [scope, setScope] = useState<Scope>("from");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setAmount(String(data?.planned[monthIndex] ?? 0).replace(".", ","));
  }, [category, data, monthIndex]);

  const newAmount = parseAmount(amount);
  const valid = Number.isFinite(newAmount) && newAmount >= 0 && Boolean(category);

  const impact = useMemo(() => {
    if (!data || !valid) return undefined;
    const first = scope === "year" ? 0 : monthIndex;
    const last = scope === "month" ? monthIndex : 11;
    const firstBudgeted = Math.max(0, data.planned.findIndex((value) => value > 0));
    let annual = data.annual;
    for (let index = first; index <= last; index += 1) {
      if (index < firstBudgeted && scope === "year") continue;
      annual += newAmount - data.planned[index];
    }
    const overMonths = (amounts: number[]) => data.actual.filter((value, index) => index < snapshot.annual.elapsedMonths && amounts[index] > 0 && value > amounts[index]).length;
    const nextPlanned = data.planned.map((value, index) => (index >= first && index <= last && !(index < firstBudgeted && scope === "year") ? newAmount : value));
    return {
      annual,
      totalAnnual: snapshot.annual.totals.annual - data.annual + annual,
      overBefore: overMonths(data.planned),
      overAfter: overMonths(nextPlanned),
    };
  }, [data, monthIndex, newAmount, scope, snapshot.annual.elapsedMonths, snapshot.annual.totals.annual, valid]);

  const row = snapshot.rows.find((item) => item.category === category);
  const monthName = monthLabel(month).split(" ")[0].toLowerCase();

  async function save() {
    setSaving(true);
    setError(undefined);
    try {
      const result = await reviseBudget(token, { category, month, scope, newAmount, reason });
      onSaved(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La révision n’a pas pu être enregistrée.");
      setSaving(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Budgets · Révision"
      footer={(
        <>
          <button className="secondary-button" onClick={onClose} type="button">Annuler</button>
          <button disabled={!valid || saving} onClick={() => void save()} type="button">{saving ? "Enregistrement…" : "Enregistrer la révision"}</button>
        </>
      )}
      onClose={onClose}
      title={category || "Réviser le budget"}
    >
      {data?.suggestRevision && (
        <p className="bgt-advice"><b>Pourquoi réviser ?</b> Le réalisé dépasse le budget depuis {data.monthsOver} mois. Le budget actuel ne reflète plus la réalité.</p>
      )}
      <label className="account-field">
        <span>Catégorie</span>
        <select onChange={(event) => setCategory(event.target.value)} value={category}>
          {categories.map((item) => <option key={item.category} value={item.category}>{item.category}</option>)}
        </select>
      </label>
      <div className="bgt-compare">
        <div><small>Budget actuel</small><strong>{formatMoney(current)}<em> / mois</em></strong></div>
        <div className="is-new"><small>Nouveau budget</small><strong>{Number.isFinite(newAmount) ? formatMoney(newAmount) : "—"}<em> / mois</em></strong></div>
      </div>
      <label className="account-field">
        <span>Nouveau montant mensuel</span>
        <div className="rules-input"><input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} value={amount} /><b>EUR</b></div>
      </label>
      <fieldset className="bgt-scope">
        <legend>Appliquer la révision</legend>
        {([["month", `Ce mois seulement (${monthName})`], ["from", `À partir de ${monthName}, jusqu’à la fin de l’année`], ["year", `Toute l’année ${month.slice(0, 4)} (réécrit aussi le passé)`]] as const).map(([id, label]) => (
          <label className={scope === id ? "is-active" : ""} key={id}><input checked={scope === id} name="scope" onChange={() => setScope(id)} type="radio" />{label}</label>
        ))}
      </fieldset>
      <label className="account-field">
        <span>Motif (facultatif)</span>
        <input onChange={(event) => setReason(event.target.value)} placeholder="Ex. prime annuelle prélevée mensuellement" value={reason} />
      </label>
      {impact && data && (
        <div className="bgt-impact">
          <div className="bgt-history__title">Impact sur {month.slice(0, 4)} (estimation)</div>
          <div><span>Budget annuel {category}</span><span><s>{formatMoney(data.annual)}</s> → <b>{formatMoney(impact.annual)}</b></span></div>
          <div><span>Budget annuel total</span><span><s>{formatMoney(snapshot.annual.totals.annual)}</s> → <b>{formatMoney(impact.totalAnnual)}</b></span></div>
          <div><span>Mois en dépassement</span><span><b>{impact.overBefore} → {impact.overAfter}</b></span></div>
        </div>
      )}
      {error && <p className="account-form-error" role="alert">{error}</p>}
      <RevisionHistory initial={data?.initial[monthIndex] ?? current} revisions={data?.revisions ?? []} />
      {row && row.transactions.length > 0 && (
        <div className="bgt-history">
          <div className="bgt-history__title">Plus grosses dépenses de {monthLabel(month).toLowerCase()}</div>
          <ul className="bgt-tx">
            {row.transactions.map((transaction) => <li key={transaction.id}><span title={transaction.label}>{transaction.label}</span><b>{formatMoneyExact(transaction.amount)}</b></li>)}
          </ul>
        </div>
      )}
    </SideDrawer>
  );
}

/** Volet « Paramétrer une catégorie » : activation, mode, montant de base, seuil, notes. */
export function CategoryDrawer({ category, month, onClose, onSaved, snapshot, token }: CommonProps & { category: string | null }) {
  const { settings } = snapshot;
  const existing = settings.categories.find((item) => item.category === category);
  const [name, setName] = useState(category ?? settings.available[0] ?? "");
  const [active, setActive] = useState(existing?.active ?? true);
  const [mode, setMode] = useState(existing?.mode ?? "Fixe");
  const [amount, setAmount] = useState(() => {
    const base = existing?.amount ?? 0;
    return String(existing?.mode === "Annuel réparti" ? Math.round(base * 12 * 100) / 100 : base).replace(".", ",");
  });
  const [threshold, setThreshold] = useState(String(Math.round(existing?.alertThreshold ?? settings.defaultAlertThreshold)));
  const [notes, setNotes] = useState(existing?.notes ?? "");
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);

  const typed = parseAmount(amount);
  const monthly = mode === "Annuel réparti" ? Math.round((typed / 12) * 100) / 100 : typed;
  const thresholdValue = parseAmount(threshold);
  const valid = Boolean(name) && Number.isFinite(typed) && typed >= 0 && Number.isFinite(thresholdValue) && thresholdValue >= 1 && thresholdValue <= 200;
  const alertAt = Number.isFinite(monthly) ? monthly * (thresholdValue / 100) : 0;

  function switchMode(next: string) {
    const current = parseAmount(amount);
    if (Number.isFinite(current)) {
      if (mode !== "Annuel réparti" && next === "Annuel réparti") setAmount(String(Math.round(current * 12 * 100) / 100).replace(".", ","));
      if (mode === "Annuel réparti" && next !== "Annuel réparti") setAmount(String(Math.round((current / 12) * 100) / 100).replace(".", ","));
    }
    setMode(next);
  }

  async function save() {
    setSaving(true);
    setError(undefined);
    try {
      const result = await saveBudgetCategory(token, { category: name, month, plannedAmount: monthly, alertThreshold: thresholdValue, mode, notes, active });
      onSaved(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La catégorie n’a pas pu être enregistrée.");
      setSaving(false);
    }
  }

  async function remove() {
    if (!category) return;
    setSaving(true);
    try {
      const result = await removeBudgetCategory(token, category, month);
      onSaved(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La catégorie n’a pas pu être retirée.");
      setSaving(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Budgets · Paramétrage"
      footer={(
        <>
          {category && <button className="bgt-danger" disabled={saving} onClick={() => void remove()} type="button">Retirer du budget</button>}
          <button className="secondary-button" onClick={onClose} type="button">Annuler</button>
          <button disabled={!valid || saving} onClick={() => void save()} type="button">{saving ? "Enregistrement…" : "Enregistrer"}</button>
        </>
      )}
      onClose={onClose}
      title={category ?? "Nouvelle catégorie budgétée"}
    >
      <p className="drawer-help">Les réglages s’appliquent à partir de {monthLabel(month).toLowerCase()}.</p>
      {!category && (
        <label className="account-field">
          <span>Catégorie</span>
          {settings.available.length > 0 ? (
            <select onChange={(event) => setName(event.target.value)} value={name}>
              {settings.available.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          ) : <p className="bgt-note">Toutes les catégories de dépense sont déjà budgétées. Crée-en une dans Paramètres › Catégories.</p>}
        </label>
      )}
      <div className="bgt-switch-row">
        <div><b>Catégorie suivie</b><small>Désactivée, elle sort des totaux et des alertes.</small></div>
        <button aria-checked={active} aria-label="Catégorie suivie" className={active ? "bgt-switch is-on" : "bgt-switch"} onClick={() => setActive((value) => !value)} role="switch" type="button"><i /></button>
      </div>
      <div className="account-field">
        <span>Mode du budget</span>
        <div className="sim-segmented" role="group" aria-label="Mode">
          {settings.modes.map((item) => <button aria-pressed={mode === item} className={mode === item ? "is-active" : ""} key={item} onClick={() => switchMode(item)} type="button">{item}</button>)}
        </div>
      </div>
      <div className="sim-grid">
        <label className="account-field">
          <span>{mode === "Annuel réparti" ? "Budget annuel" : "Budget mensuel de base"}</span>
          <div className="rules-input"><input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} value={amount} /><b>EUR</b></div>
        </label>
        <label className="account-field">
          <span>Seuil d’alerte</span>
          <div className="rules-input"><input inputMode="numeric" onChange={(event) => setThreshold(event.target.value)} value={threshold} /><b>%</b></div>
        </label>
      </div>
      <p className="bgt-note">
        {mode === "Annuel réparti" && Number.isFinite(monthly) && <>Soit {formatMoney(monthly)} par mois. </>}
        Alerte à partir de {formatMoney(alertAt)} dépensés dans le mois.
        {mode === "Saisonnier" && " Pour un mois particulier, utilise « Réviser le budget » avec « ce mois seulement »."}
      </p>
      <label className="account-field">
        <span>Notes</span>
        <input onChange={(event) => setNotes(event.target.value)} placeholder="Ex. courses + restaurants" value={notes} />
      </label>
      {error && <p className="account-form-error" role="alert">{error}</p>}
      {existing && <RevisionHistory initial={existing.initialAmount} revisions={existing.revisions} />}
      {existing && <p className="bgt-note">Changer le montant ici enregistre une révision « à partir de {MONTH_SHORT[Number(month.slice(5, 7)) - 1]} » dans l’historique.</p>}
    </SideDrawer>
  );
}

/** Volet « Règles générales » : seuil d'alerte par défaut des nouvelles catégories. */
export function RulesDrawer({ onClose, onSaved, snapshot, token }: Omit<CommonProps, "month">) {
  const [threshold, setThreshold] = useState(String(Math.round(snapshot.settings.defaultAlertThreshold)));
  const [error, setError] = useState<string>();
  const [saving, setSaving] = useState(false);
  const value = parseAmount(threshold);
  const valid = Number.isFinite(value) && value >= 1 && value <= 200;

  async function save() {
    setSaving(true);
    try {
      const result = await saveBudgetRules(token, value);
      onSaved(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Les règles n’ont pas pu être enregistrées.");
      setSaving(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Budgets · Règles générales"
      footer={(
        <>
          <button className="secondary-button" onClick={onClose} type="button">Annuler</button>
          <button disabled={!valid || saving} onClick={() => void save()} type="button">{saving ? "Enregistrement…" : "Enregistrer"}</button>
        </>
      )}
      onClose={onClose}
      title="Règles générales"
    >
      <p className="drawer-help">Le seuil par défaut s’applique aux nouvelles catégories budgétées. Les catégories existantes gardent leur propre seuil.</p>
      <label className="account-field">
        <span>Seuil d’alerte par défaut</span>
        <div className="rules-input"><input inputMode="numeric" onChange={(event) => setThreshold(event.target.value)} value={threshold} /><b>%</b></div>
      </label>
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}
