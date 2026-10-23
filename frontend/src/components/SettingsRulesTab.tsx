import { useEffect, useMemo, useState } from "react";

import {
  applyPendingRules,
  createSettingsRule,
  deleteSettingsRule,
  getRuleSuggestions,
  previewPendingRules,
  setSettingsRuleActive,
  updateSettingsRule,
} from "../api/client";
import type { PendingRulesPreview, SettingsRule, SettingsRulePayload, SettingsSnapshot } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code" });
const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" });

type Filter = "all" | "active" | "paused";

interface RuleForm {
  name: string;
  active: boolean;
  priority: number;
  matchField: string;
  matchOperator: string;
  matchValue: string;
  transactionType: string;
  accountId: string;
  minAmount: string;
  maxAmount: string;
  targetCategoryId: string;
  confidence: number;
}

const emptyForm = (): RuleForm => ({
  name: "",
  active: true,
  priority: 100,
  matchField: "label",
  matchOperator: "contains",
  matchValue: "",
  transactionType: "Tous",
  accountId: "all",
  minAmount: "",
  maxAmount: "",
  targetCategoryId: "",
  confidence: 100,
});

const formOf = (rule: SettingsRule): RuleForm => ({
  name: rule.name,
  active: rule.active,
  priority: rule.priority,
  matchField: rule.matchField,
  matchOperator: rule.matchOperator,
  matchValue: rule.matchValue,
  transactionType: rule.transactionType || "Tous",
  accountId: rule.accountId === null ? "all" : String(rule.accountId),
  minAmount: rule.minAmount === null ? "" : String(rule.minAmount),
  maxAmount: rule.maxAmount === null ? "" : String(rule.maxAmount),
  targetCategoryId: String(rule.targetCategoryId),
  confidence: rule.confidence,
});

function optionalNumber(value: string): number | null {
  const parsed = Number(value.replace(",", "."));
  return value.trim() === "" || Number.isNaN(parsed) ? null : parsed;
}

function scopeOf(rule: SettingsRule): string {
  const flow = rule.transactionType && rule.transactionType !== "Tous" ? `${rule.transactionType.toLowerCase()}s` : "tous flux";
  return `${flow} · ${rule.accountId === null ? "tous comptes" : rule.accountName}`;
}

interface Props {
  onChanged: (message: string) => Promise<void>;
  onOpenSuggestions: () => void;
  snapshot: SettingsSnapshot;
  token: string;
}

/** Paramètres › Règles de catégorisation : tableau, clic droit, volets Modifier / Appliquer. */
export function SettingsRulesTab({ onChanged, onOpenSuggestions, snapshot, token }: Props) {
  const rules = snapshot.rules;
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [menu, setMenu] = useState<ContextMenuState>();
  const [editing, setEditing] = useState<SettingsRule | "new">();
  const [removing, setRemoving] = useState<SettingsRule>();
  const [applying, setApplying] = useState<{ rule: SettingsRule | null }>();
  const [form, setForm] = useState<RuleForm>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestionCount, setSuggestionCount] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getRuleSuggestions(token, 0.9, controller.signal)
      .then((data) => setSuggestionCount(data.suggestions.filter((item) => item.recommended).length))
      .catch(() => undefined);
    return () => controller.abort();
  }, [token, rules.length]);

  const activeCount = rules.filter((rule) => rule.active).length;
  const pausedCount = rules.length - activeCount;
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rules.filter((rule) => {
      if (filter === "active" && !rule.active) return false;
      if (filter === "paused" && rule.active) return false;
      return !needle || `${rule.summary} ${rule.name} ${rule.targetCategory}`.toLowerCase().includes(needle);
    });
  }, [rules, filter, search]);

  function open(target: SettingsRule | "new") {
    setEditing(target);
    setForm(target === "new" ? emptyForm() : formOf(target));
    setError("");
  }

  function openMenu(event: React.MouseEvent, rule: SettingsRule) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Modifier la règle…", onSelect: () => open(rule) },
        { label: "Appliquer cette règle aux opérations en attente", onSelect: () => setApplying({ rule }), disabled: !rule.active, hint: rule.active ? undefined : "Réactivez la règle pour l’appliquer." },
        { label: rule.active ? "Mettre en pause" : "Réactiver", onSelect: () => void toggle(rule) },
        { label: "Supprimer la règle…", danger: true, onSelect: () => { setRemoving(rule); setError(""); } },
      ],
      note: rule.active ? undefined : "Règle en pause : elle n’est plus appliquée aux imports.",
    });
  }

  async function guarded(action: () => Promise<{ message: string }>, close?: () => void) {
    setBusy(true);
    setError("");
    try {
      const result = await action();
      close?.();
      await onChanged(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "L’opération a échoué.");
    } finally {
      setBusy(false);
    }
  }

  const toggle = (rule: SettingsRule) => guarded(() => setSettingsRuleActive(token, rule.id, !rule.active));

  function save() {
    if (!editing) return;
    const categoryName = snapshot.options.categories.find((item) => String(item.id) === form.targetCategoryId)?.name ?? "";
    const payload: SettingsRulePayload = {
      name: form.name.trim() || `${form.matchValue.trim() || "Montant"} → ${categoryName}`,
      description: editing === "new" ? "" : editing.description,
      is_active: form.active,
      priority: form.priority,
      match_field: form.matchField,
      match_operator: form.matchOperator,
      match_value: form.matchValue,
      transaction_type: form.transactionType === "Tous" ? null : form.transactionType,
      account_id: form.accountId === "all" ? null : Number(form.accountId),
      min_amount: optionalNumber(form.minAmount),
      max_amount: optionalNumber(form.maxAmount),
      target_category_id: Number(form.targetCategoryId),
      confidence: form.confidence,
    };
    void guarded(
      () => (editing === "new" ? createSettingsRule(token, payload) : updateSettingsRule(token, editing.id, payload)),
      () => setEditing(undefined),
    );
  }

  const filters: Array<{ id: Filter; label: string; count: number }> = [
    { id: "all", label: "Toutes", count: rules.length },
    { id: "active", label: "Actives", count: activeCount },
    { id: "paused", label: "En pause", count: pausedCount },
  ];

  return (
    <article className="card stg-panel">
      <div className="stg-toolbar">
        <div className="stg-toolbar__left">
          <input aria-label="Rechercher une règle" onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher une règle…" value={search} />
          <div className="stg-segment" role="group" aria-label="Filtrer par statut">
            {filters.map((item) => (
              <button aria-pressed={filter === item.id} key={item.id} onClick={() => setFilter(item.id)} type="button">{item.label} · {item.count}</button>
            ))}
          </div>
        </div>
        <div className="stg-toolbar__right">
          <button className="stg-secondary" disabled={snapshot.pendingCount === 0 || activeCount === 0} onClick={() => setApplying({ rule: null })} type="button">Appliquer aux opérations en attente · {snapshot.pendingCount}</button>
          <button className="stg-primary" onClick={() => open("new")} type="button">Nouvelle règle de catégorisation</button>
        </div>
      </div>

      <div className="stg-kpis stg-kpis--3">
        <div><b>{rules.length}</b> règles de catégorisation</div>
        <div><b className="stg-accent">{snapshot.pendingCount}</b> opérations « À catégoriser » en attente</div>
        <div><b>{suggestionCount}</b> suggestions à valider <button className="stg-link" onClick={onOpenSuggestions} type="button">· Transactions ›</button></div>
      </div>

      <div className="stg-table-wrap">
        <table className="stg-table stg-table--rules">
          <thead>
            <tr><th>Priorité</th><th>Si… alors…</th><th>Catégorie</th><th className="num">Utilisée</th><th>Statut</th></tr>
          </thead>
          <tbody>
            {visible.map((rule) => (
              <tr key={rule.id} onContextMenu={(event) => openMenu(event, rule)} onDoubleClick={() => open(rule)} title="Double-clic : modifier · clic droit : actions">
                <td>{rule.priority}</td>
                <td><strong>{rule.summary}</strong> <small>· {scopeOf(rule)}</small></td>
                <td><span className="category-chip">{rule.targetCategory}</span></td>
                <td className={rule.usageCount === 0 ? "num stg-zero" : "num"}>{rule.usageCount === 0 ? "jamais" : `${rule.usageCount} fois`}</td>
                <td><span className={rule.active ? "status-chip status-chip--success" : "status-chip status-chip--muted"}>{rule.active ? "Active" : "Pause"}</span></td>
              </tr>
            ))}
            {visible.length === 0 && <tr><td className="stg-empty" colSpan={5}>{rules.length === 0 ? "Aucune règle pour l’instant. Créez-en une, ou validez des suggestions dans Transactions." : "Aucune règle ne correspond à la recherche."}</td></tr>}
          </tbody>
        </table>
      </div>

      <p className="stg-footnote">Les règles sont appliquées par priorité (la plus basse en premier) à chaque import. Clic droit sur une règle : Modifier… · Appliquer cette règle aux opérations en attente · Mettre en pause · Supprimer. Double-clic : modifier.</p>

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}

      {editing && (
        <SideDrawer
          eyebrow="RÈGLES DE CATÉGORISATION"
          footer={<><button className="secondary-button" onClick={() => setEditing(undefined)} type="button">Annuler</button><button className="primary-button" disabled={busy || !form.targetCategoryId} form="stg-rule-form" type="submit">Enregistrer</button></>}
          onClose={() => setEditing(undefined)}
          title={editing === "new" ? "Nouvelle règle de catégorisation" : "Modifier la règle"}
        >
          <form className="stg-form" id="stg-rule-form" onSubmit={(event) => { event.preventDefault(); save(); }}>
            {error && <p className="stg-error" role="alert">{error}</p>}
            <div className="stg-form__row">
              <label>Si le champ<select onChange={(event) => setForm({ ...form, matchField: event.target.value })} value={form.matchField}>{snapshot.options.matchFields.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label>Condition<select onChange={(event) => setForm({ ...form, matchOperator: event.target.value })} value={form.matchOperator}>{snapshot.options.operators.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
            </div>
            {form.matchOperator === "amount_between"
              ? <div className="stg-form__row"><label>Montant min<input inputMode="decimal" onChange={(event) => setForm({ ...form, minAmount: event.target.value })} value={form.minAmount} /></label><label>Montant max<input inputMode="decimal" onChange={(event) => setForm({ ...form, maxAmount: event.target.value })} value={form.maxAmount} /></label></div>
              : <label>Valeur recherchée<input autoFocus onChange={(event) => setForm({ ...form, matchValue: event.target.value })} placeholder="ex. LIDL" required value={form.matchValue} /></label>}
            <label>Alors la catégorie est<select onChange={(event) => setForm({ ...form, targetCategoryId: event.target.value })} required value={form.targetCategoryId}><option disabled value="">Choisir une catégorie</option>{snapshot.options.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            <div className="stg-form__row">
              <label>Comptes concernés<select onChange={(event) => setForm({ ...form, accountId: event.target.value })} value={form.accountId}><option value="all">Tous les comptes</option>{snapshot.options.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}</select></label>
              <label>Type de flux<select onChange={(event) => setForm({ ...form, transactionType: event.target.value })} value={form.transactionType}>{snapshot.options.transactionTypes.map((item) => <option key={item}>{item}</option>)}</select></label>
            </div>
            <div className="stg-form__row">
              <label>Priorité<input min="1" onChange={(event) => setForm({ ...form, priority: Number(event.target.value) })} type="number" value={form.priority} /></label>
              <label>Confiance (%)<input max="100" min="1" onChange={(event) => setForm({ ...form, confidence: Number(event.target.value) })} type="number" value={form.confidence} /></label>
            </div>
            <label>Nom (facultatif)<input onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Généré automatiquement si vide" value={form.name} /></label>
            <label className="stg-check"><input checked={form.active} onChange={(event) => setForm({ ...form, active: event.target.checked })} type="checkbox" />Règle active</label>
            <p className="stg-hint">Priorité : la plus basse passe en premier. Confiance inférieure à 80 % : l’opération est classée « À vérifier ».</p>
          </form>
        </SideDrawer>
      )}

      {removing && (
        <SideDrawer
          eyebrow="RÈGLES DE CATÉGORISATION"
          footer={<><button className="secondary-button" onClick={() => setRemoving(undefined)} type="button">Annuler</button><button className="primary-button stg-danger-btn" disabled={busy} onClick={() => void guarded(() => deleteSettingsRule(token, removing.id), () => setRemoving(undefined))} type="button">Supprimer la règle</button></>}
          onClose={() => setRemoving(undefined)}
          title="Supprimer cette règle ?"
        >
          {error && <p className="stg-error" role="alert">{error}</p>}
          <p className="stg-hint"><b>{removing.summary}</b> → {removing.targetCategory}</p>
          <p className="stg-hint">Les opérations déjà classées par cette règle gardent leur catégorie. La règle ne sera plus appliquée aux prochains imports.</p>
        </SideDrawer>
      )}

      {applying && (
        <ApplyDrawer
          onClose={() => setApplying(undefined)}
          onDone={async (message) => { setApplying(undefined); await onChanged(message); }}
          rule={applying.rule}
          token={token}
        />
      )}
    </article>
  );
}

function ApplyDrawer({ onClose, onDone, rule, token }: { onClose: () => void; onDone: (message: string) => Promise<void>; rule: SettingsRule | null; token: string }) {
  const [preview, setPreview] = useState<PendingRulesPreview>();
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let alive = true;
    previewPendingRules(token, rule?.id)
      .then((data) => {
        if (!alive) return;
        setPreview(data);
        setChecked(new Set(data.items.map((item) => item.id)));
      })
      .catch((cause: unknown) => alive && setError(cause instanceof Error ? cause.message : "La simulation a échoué."));
    return () => { alive = false; };
  }, [token, rule?.id]);

  function toggle(id: number) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function confirm() {
    if (checked.size === 0) return;
    setBusy(true);
    setError("");
    try {
      const result = await applyPendingRules(token, [...checked], rule?.id);
      await onDone(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Le classement a échoué.");
      setBusy(false);
    }
  }

  const items = preview?.items ?? [];
  const allChecked = items.length > 0 && checked.size === items.length;

  return (
    <SideDrawer
      eyebrow="RÈGLES DE CATÉGORISATION"
      footer={<><button className="secondary-button" onClick={onClose} type="button">Annuler</button><button className="primary-button" disabled={busy || checked.size === 0} onClick={() => void confirm()} type="button">Classer {checked.size} opération{checked.size > 1 ? "s" : ""}</button></>}
      onClose={onClose}
      title={rule ? "Appliquer cette règle aux opérations en attente" : "Appliquer aux opérations en attente"}
    >
      <p className="rsg-drawer-lead">Simulation : rien n’est modifié tant que vous n’avez pas validé. Les opérations déjà catégorisées ne sont jamais touchées.</p>
      {error && <p className="stg-error" role="alert">{error}</p>}
      {!preview && !error && <p className="stg-hint">Calcul en cours…</p>}
      {preview && (
        <>
          <div className="stg-kpis stg-kpis--3 stg-kpis--drawer">
            <div><b>{preview.pendingCount}</b> en attente</div>
            <div className="stg-kpis__ok"><b>{preview.matchedCount}</b> seront classées</div>
            <div><b>{preview.unmatchedCount}</b> sans règle</div>
          </div>
          {preview.byRule.length > 0 && (
            <>
              <div className="rsg-drawer-title">Par règle</div>
              <ul className="stg-byrule">
                {preview.byRule.map((entry) => (
                  <li key={entry.ruleId}><span>{entry.summary}</span><span className="category-chip">{entry.category}</span><b>{entry.count}</b></li>
                ))}
              </ul>
            </>
          )}
          <div className="rsg-drawer-title">
            <span>Aperçu des opérations ({items.length})</span>
            {items.length > 0 && <button className="stg-link" onClick={() => setChecked(allChecked ? new Set() : new Set(items.map((item) => item.id)))} type="button">{allChecked ? "Tout décocher" : "Tout cocher"}</button>}
          </div>
          {items.length === 0
            ? <p className="stg-hint">Aucune opération en attente ne correspond {rule ? "à cette règle" : "aux règles actives"}.</p>
            : (
              <table className="rsg-preview">
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td><input aria-label={`Classer ${item.label}`} checked={checked.has(item.id)} onChange={() => toggle(item.id)} type="checkbox" /></td>
                      <td>{shortDate.format(new Date(item.date))}</td>
                      <td title={item.label}>{item.label}</td>
                      <td className="stg-cat">→ {item.category}</td>
                      <td className={item.amount < 0 ? "amount--negative" : "amount--positive"}>{money.format(item.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </>
      )}
    </SideDrawer>
  );
}
