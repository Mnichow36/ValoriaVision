import { useEffect, useMemo, useState } from "react";

import {
  createSettingsCategory,
  createSettingsRule,
  deleteSettingsCategory,
  getSettings,
  previewSettingsRules,
  setSettingsRuleActive,
  updateSettingsCategory,
  updateSettingsGeneral,
  updateSettingsRule,
  getSecurityJournal,
  getSecurityStatus,
} from "../api/client";
import type {
  SettingsCategory,
  Profile,
  SecurityEvent,
  SecurityStatus,
  SettingsCategoryPayload,
  SettingsRule,
  SettingsRulePayload,
  SettingsRulesPreview,
  SettingsSnapshot,
} from "../api/contracts";
import { ChangePasswordDrawer, RecoveryKeyDrawer } from "./PasswordDrawers";
import { ProfileAvatar } from "./ProfileAvatar";
import { ProfileFormDrawer } from "./ProfileDrawers";
import type { NavigationId } from "./Sidebar";
import { ThemeSwitch } from "./ThemeSwitch";

type SettingsTab = "general" | "categories" | "rules" | "balances" | "security";

const tabs: Array<{ id: SettingsTab; label: string }> = [
  { id: "general", label: "Général" },
  { id: "categories", label: "Catégories" },
  { id: "rules", label: "Règles auto" },
  { id: "balances", label: "Soldes" },
  { id: "security", label: "Sécurité" },
];

const money = new Intl.NumberFormat("fr-FR", {
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 2,
  style: "currency",
});

interface CategoryForm {
  name: string;
  kind: string;
  direction: string;
  color: string;
  budgetEnabled: boolean;
}

interface RuleForm {
  name: string;
  description: string;
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

const emptyCategory = (): CategoryForm => ({
  name: "",
  kind: "Dépense",
  direction: "Dépense",
  color: "#64748B",
  budgetEnabled: true,
});

const emptyRule = (): RuleForm => ({
  name: "",
  description: "",
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

export function SettingsPage({ onNavigate, token, profile, onProfileChanged }: { onNavigate: (destination: NavigationId | "reconciliation") => void; token: string; profile: Profile | null; onProfileChanged: () => void }) {
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("rules");
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [selectedRuleId, setSelectedRuleId] = useState<number | null>(null);
  const [categoryForm, setCategoryForm] = useState<CategoryForm>(emptyCategory);
  const [ruleForm, setRuleForm] = useState<RuleForm>(emptyRule);
  const [currentMonth, setCurrentMonth] = useState("");
  const [sessionTimeout, setSessionTimeout] = useState(10);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<SettingsRulesPreview | null>(null);
  const [journal, setJournal] = useState<SecurityEvent[]>([]);
  const [securityStatus, setSecurityStatus] = useState<SecurityStatus | null>(null);
  const [securityDrawer, setSecurityDrawer] = useState<"password" | "recovery" | "profile" | null>(null);
  const [securityRefresh, setSecurityRefresh] = useState(0);

  async function refresh(signal?: AbortSignal, preferred?: { categoryId?: number; ruleId?: number }) {
    const next = await getSettings(token, signal);
    setSnapshot(next);
    setCurrentMonth(next.general.currentMonth);
    setSessionTimeout(next.security.sessionTimeoutMinutes);
    const categoryId = preferred?.categoryId ?? selectedCategoryId ?? next.categories[0]?.id ?? null;
    const ruleId = preferred?.ruleId ?? selectedRuleId ?? next.rules[0]?.id ?? null;
    selectCategory(next.categories.find((item) => item.id === categoryId) ?? null);
    selectRule(next.rules.find((item) => item.id === ruleId) ?? null);
  }

  useEffect(() => {
    const controller = new AbortController();
    refresh(controller.signal).catch((reason: unknown) => {
      if (!controller.signal.aborted) setError(errorMessage(reason));
    });
    return () => controller.abort();
    // The first snapshot owns the initial selection; later refreshes are explicit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  useEffect(() => {
    if (activeTab !== "security") return;
    const controller = new AbortController();
    getSecurityJournal(token, controller.signal).then((r) => setJournal(r.events)).catch(() => undefined);
    getSecurityStatus(token, controller.signal).then(setSecurityStatus).catch(() => undefined);
    return () => controller.abort();
  }, [activeTab, token, securityRefresh]);

  const selectedCategory = useMemo(
    () => snapshot?.categories.find((item) => item.id === selectedCategoryId) ?? null,
    [selectedCategoryId, snapshot],
  );
  const selectedRule = useMemo(
    () => snapshot?.rules.find((item) => item.id === selectedRuleId) ?? null,
    [selectedRuleId, snapshot],
  );

  function selectCategory(category: SettingsCategory | null) {
    setSelectedCategoryId(category?.id ?? null);
    setCategoryForm(category ? {
      name: category.name,
      kind: category.kind,
      direction: category.direction,
      color: category.color,
      budgetEnabled: category.budgetEnabled,
    } : emptyCategory());
  }

  function selectRule(rule: SettingsRule | null) {
    setSelectedRuleId(rule?.id ?? null);
    setRuleForm(rule ? {
      name: rule.name,
      description: rule.description,
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
    } : emptyRule());
  }

  async function run(action: () => Promise<{ message: string; id?: number }>, preferred?: (result: { id?: number }) => { categoryId?: number; ruleId?: number }) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await action();
      setNotice(result.message);
      await refresh(undefined, preferred?.(result));
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  if (!snapshot) {
    return error
      ? <section className="error-state"><strong>Les paramètres ne peuvent pas être chargés</strong><p>{error}</p></section>
      : <section className="loading-state"><span /><p>Lecture des réglages Python…</p></section>;
  }

  async function saveGeneral() {
    await run(() => updateSettingsGeneral(token, {
      currency: snapshot!.general.currency,
      current_month: currentMonth,
      session_timeout_minutes: snapshot!.security.sessionTimeoutMinutes,
    }));
  }

  async function saveSecurity() {
    await run(() => updateSettingsGeneral(token, {
      currency: snapshot!.general.currency,
      current_month: snapshot!.general.currentMonth,
      session_timeout_minutes: sessionTimeout,
    }));
  }

  async function saveCategory() {
    const payload: SettingsCategoryPayload = {
      name: categoryForm.name,
      kind: categoryForm.kind,
      direction: categoryForm.direction,
      color: categoryForm.color,
      budget_enabled: categoryForm.budgetEnabled,
    };
    await run(
      () => selectedCategoryId === null
        ? createSettingsCategory(token, payload)
        : updateSettingsCategory(token, selectedCategoryId, payload),
      (result) => ({ categoryId: result.id }),
    );
  }

  async function removeCategory() {
    if (selectedCategoryId === null || !selectedCategory) return;
    const confirmed = window.confirm(
      `Supprimer la catégorie « ${selectedCategory.name} » ? Les usages seront réaffectés par le moteur Python.`,
    );
    if (!confirmed) return;
    await run(() => deleteSettingsCategory(token, selectedCategoryId), () => ({ categoryId: undefined }));
  }

  async function saveRule() {
    const payload: SettingsRulePayload = {
      name: ruleForm.name,
      description: ruleForm.description,
      is_active: ruleForm.active,
      priority: ruleForm.priority,
      match_field: ruleForm.matchField,
      match_operator: ruleForm.matchOperator,
      match_value: ruleForm.matchValue,
      transaction_type: ruleForm.transactionType === "Tous" ? null : ruleForm.transactionType,
      account_id: ruleForm.accountId === "all" ? null : Number(ruleForm.accountId),
      min_amount: optionalNumber(ruleForm.minAmount),
      max_amount: optionalNumber(ruleForm.maxAmount),
      target_category_id: Number(ruleForm.targetCategoryId),
      confidence: ruleForm.confidence,
    };
    await run(
      () => selectedRuleId === null
        ? createSettingsRule(token, payload)
        : updateSettingsRule(token, selectedRuleId, payload),
      (result) => ({ ruleId: result.id }),
    );
  }

  async function toggleRule() {
    if (selectedRuleId === null) return;
    await run(
      () => setSettingsRuleActive(token, selectedRuleId, !ruleForm.active),
      () => ({ ruleId: selectedRuleId }),
    );
  }

  async function testRules() {
    setBusy(true);
    setError("");
    try {
      const result = await previewSettingsRules(token);
      setPreview(result);
      setNotice(result.message);
    } catch (reason: unknown) {
      setError(errorMessage(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="settings-page">
      <nav aria-label="Sections des paramètres" className="settings-tabs">
        {tabs.map((tab) => (
          <button
            className={activeTab === tab.id ? "settings-tab settings-tab--active" : "settings-tab"}
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); setError(""); setNotice(""); }}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {(notice || error) && (
        <div aria-live="polite" className={error ? "settings-feedback settings-feedback--error" : "settings-feedback"}>
          {error || notice}
        </div>
      )}

      {activeTab === "general" && (
        <form className="settings-overview-grid" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveGeneral(); }}>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Préférences générales</h2><p>Réglages communs utilisés par tous les écrans.</p></div></div>
            <div className="settings-form-grid">
              <label>Devise<select disabled value={snapshot.general.currency}><option>EUR</option></select></label>
              <label>Langue<select disabled value={snapshot.general.locale}><option value="fr">Français</option></select></label>
              <label>Mois de travail<input onChange={(event) => setCurrentMonth(event.target.value)} pattern="\d{4}-(0[1-9]|1[0-2])" placeholder="AAAA-MM" value={currentMonth} /></label>
            </div>
            <div className="settings-theme-row"><div><strong>Apparence</strong><small>Clair, sombre, ou selon le réglage de ton système. Mémorisé sur ce poste.</small></div><ThemeSwitch variant="settings" /></div>
            <button className="settings-primary" disabled={busy} type="submit">Enregistrer les préférences</button>
          </article>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Socle local</h2><p>État de la base utilisée par les moteurs Python.</p></div></div>
            <dl className="settings-kv-list">
              <div><dt>Intégrité SQLite</dt><dd><Status value={snapshot.general.integrity === "ok"} /></dd></div>
              <div><dt>Version du schéma</dt><dd>V{snapshot.general.schemaVersion}</dd></div>
              <div><dt>Taille de la base</dt><dd>{snapshot.general.databaseSizeKb.toLocaleString("fr-FR")} Ko</dd></div>
              <div><dt>Dernière sauvegarde</dt><dd title={snapshot.general.lastBackup}>{fileName(snapshot.general.lastBackup) || "Aucune"}</dd></div>
            </dl>
          </article>
          <article className="card settings-summary-card settings-ownership-card">
            <div className="panel-heading"><div><h2>Architecture sans doublon</h2><p>Chaque fonction conserve un seul moteur métier.</p></div></div>
            <ul>{snapshot.ownership.map((item) => <li key={item.feature}><strong>{item.feature}</strong><span>{item.mode}</span><small>{item.owner}</small></li>)}</ul>
          </article>
        </form>
      )}

      {activeTab === "categories" && (
        <div className="settings-split">
          <article className="card settings-list-card">
            <div className="settings-card-heading"><div><h2>Gestion des catégories</h2><p>Source commune aux transactions, budgets et graphiques.</p></div></div>
            <div className="settings-table-wrap">
              <table className="settings-table"><thead><tr><th>Catégorie</th><th>Sens</th><th>Usages</th></tr></thead><tbody>
                {snapshot.categories.map((category) => (
                  <tr className={category.id === selectedCategoryId ? "settings-row--active" : ""} key={category.id} onClick={() => selectCategory(category)}>
                    <td><span className="settings-color" style={{ background: category.color }} /><strong>{category.name}</strong></td>
                    <td>{category.direction}</td>
                    <td>{category.usage.transactions + category.usage.recurrences + category.usage.budgets}</td>
                  </tr>
                ))}
              </tbody></table>
            </div>
            <button className="settings-primary" onClick={() => selectCategory(null)} type="button">Nouvelle catégorie</button>
          </article>
          <form className="card settings-editor" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveCategory(); }}>
            <div className="settings-card-heading"><div><h2>{selectedCategoryId === null ? "Nouvelle catégorie" : "Volet catégorie"}</h2><p>Le sens pilote le signe des saisies manuelles.</p></div></div>
            <label>Nom<input onChange={(event) => setCategoryForm({ ...categoryForm, name: event.target.value })} required value={categoryForm.name} /></label>
            <label>Type<select onChange={(event) => setCategoryForm({ ...categoryForm, kind: event.target.value })} value={categoryForm.kind}><option>Revenu</option><option>Dépense</option><option>Neutre</option></select></label>
            <label>Sens<select onChange={(event) => setCategoryForm({ ...categoryForm, direction: event.target.value })} value={categoryForm.direction}><option>Recette</option><option>Dépense</option><option>Neutre</option></select></label>
            <label>Couleur<span className="settings-color-field"><input onChange={(event) => setCategoryForm({ ...categoryForm, color: event.target.value })} type="color" value={categoryForm.color} /><input onChange={(event) => setCategoryForm({ ...categoryForm, color: event.target.value })} value={categoryForm.color} /></span></label>
            <label className="settings-check"><input checked={categoryForm.budgetEnabled} onChange={(event) => setCategoryForm({ ...categoryForm, budgetEnabled: event.target.checked })} type="checkbox" />Disponible dans les budgets</label>
            <div className="settings-editor-actions">
              {selectedCategoryId !== null && <button className="settings-secondary settings-danger" disabled={busy || selectedCategory?.isSystem} onClick={() => void removeCategory()} type="button">Supprimer</button>}
              <button className="settings-primary" disabled={busy} type="submit">Enregistrer</button>
            </div>
          </form>
        </div>
      )}

      {activeTab === "rules" && (
        <div className="settings-split settings-split--rules">
          <article className="card settings-list-card">
            <div className="settings-card-heading"><div><h2>Règles de catégorisation automatique</h2><p>Règles locales appliquées aux imports et transactions.</p></div></div>
            <div className="settings-table-wrap">
              <table className="settings-table settings-rule-table"><thead><tr><th>Priorité</th><th>Critère</th><th>Catégorie</th><th>Statut</th></tr></thead><tbody>
                {snapshot.rules.map((rule) => (
                  <tr className={rule.id === selectedRuleId ? "settings-row--active" : ""} key={rule.id} onClick={() => selectRule(rule)}>
                    <td>{rule.priority}</td><td><strong>{rule.summary}</strong><small>{rule.name}</small></td>
                    <td><span className="category-chip">{rule.targetCategory}</span></td>
                    <td><span className={rule.active ? "status-chip status-chip--success" : "status-chip status-chip--muted"}>{rule.active ? "Active" : "Pause"}</span></td>
                  </tr>
                ))}
              </tbody></table>
            </div>
            <div className="settings-list-actions"><button className="settings-primary" onClick={() => selectRule(null)} type="button">Nouvelle règle</button><button className="settings-secondary" disabled={busy} onClick={() => void testRules()} type="button">Tester sur les transactions</button></div>
            {preview && <div className="settings-preview"><strong>{preview.matchedCount} correspondance(s)</strong><span>Simulation en lecture seule — aucune transaction modifiée.</span></div>}
          </article>
          <form className="card settings-editor" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveRule(); }}>
            <div className="settings-card-heading"><div><h2>{selectedRuleId === null ? "Nouvelle règle" : "Volet règle"}</h2><p>Configuration de la règle sélectionnée.</p></div></div>
            <label>Nom<input onChange={(event) => setRuleForm({ ...ruleForm, name: event.target.value })} required value={ruleForm.name} /></label>
            <div className="settings-inline-fields">
              <label>Champ<select onChange={(event) => setRuleForm({ ...ruleForm, matchField: event.target.value })} value={ruleForm.matchField}>{snapshot.options.matchFields.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
              <label>Opérateur<select onChange={(event) => setRuleForm({ ...ruleForm, matchOperator: event.target.value })} value={ruleForm.matchOperator}>{snapshot.options.operators.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
            </div>
            {ruleForm.matchOperator === "amount_between" ? <div className="settings-inline-fields"><label>Montant min<input inputMode="decimal" onChange={(event) => setRuleForm({ ...ruleForm, minAmount: event.target.value })} value={ruleForm.minAmount} /></label><label>Montant max<input inputMode="decimal" onChange={(event) => setRuleForm({ ...ruleForm, maxAmount: event.target.value })} value={ruleForm.maxAmount} /></label></div> : <label>Valeur recherchée<input onChange={(event) => setRuleForm({ ...ruleForm, matchValue: event.target.value })} required value={ruleForm.matchValue} /></label>}
            <label>Compte<select onChange={(event) => setRuleForm({ ...ruleForm, accountId: event.target.value })} value={ruleForm.accountId}><option value="all">Tous les comptes</option>{snapshot.options.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}</select></label>
            <label>Catégorie<select onChange={(event) => setRuleForm({ ...ruleForm, targetCategoryId: event.target.value })} required value={ruleForm.targetCategoryId}><option disabled value="">Choisir une catégorie</option>{snapshot.options.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
            <div className="settings-inline-fields"><label>Type de flux<select onChange={(event) => setRuleForm({ ...ruleForm, transactionType: event.target.value })} value={ruleForm.transactionType}>{snapshot.options.transactionTypes.map((item) => <option key={item}>{item}</option>)}</select></label><label>Priorité<input min="1" onChange={(event) => setRuleForm({ ...ruleForm, priority: Number(event.target.value) })} type="number" value={ruleForm.priority} /></label></div>
            <label>Confiance (%)<input max="100" min="1" onChange={(event) => setRuleForm({ ...ruleForm, confidence: Number(event.target.value) })} type="number" value={ruleForm.confidence} /></label>
            <label className="settings-check"><input checked={ruleForm.active} onChange={(event) => setRuleForm({ ...ruleForm, active: event.target.checked })} type="checkbox" />Règle active</label>
            <div className="settings-editor-actions">
              {selectedRuleId !== null && <button className="settings-secondary" disabled={busy} onClick={() => void toggleRule()} type="button">{ruleForm.active ? "Désactiver" : "Réactiver"}</button>}
              <button className="settings-primary" disabled={busy} type="submit">Enregistrer</button>
            </div>
          </form>
        </div>
      )}

      {activeTab === "balances" && (
        <form className="settings-balance-layout" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void run(() => Promise.resolve({ message: "Contrôles de soldes actualisés." })); }}>
          <article className="card settings-list-card">
            <div className="settings-card-heading"><div><h2>Contrôle des soldes</h2><p>Vue de cohérence uniquement : les valeurs restent éditées dans Comptes.</p></div><button className="settings-secondary" onClick={() => onNavigate("accounts")} type="button">Ouvrir Comptes</button></div>
            <div className="settings-table-wrap"><table className="settings-table settings-balance-table"><thead><tr><th>Compte</th><th>Solde initial</th><th>Mouvements</th><th>Solde calculé</th><th>Statut</th></tr></thead><tbody>{snapshot.balances.accounts.map((account) => <tr key={account.id}><td><strong>{account.name}</strong><small>{account.bank}</small></td><td>{money.format(account.initialBalance)}<small>{formatDate(account.initialDate)}</small></td><td className={account.movementTotal < 0 ? "amount--negative" : "amount--positive"}>{money.format(account.movementTotal)}</td><td><strong>{money.format(account.currentBalance)}</strong><small>{formatDate(account.currentDate)}</small></td><td><span className="status-chip status-chip--success">{account.status}</span></td></tr>)}</tbody></table></div>
          </article>
          <aside className="card settings-balance-aside"><h2>Cohérence</h2><dl className="settings-kv-list"><div><dt>Transactions sans compte</dt><dd>{snapshot.balances.summary.orphanTransactions}</dd></div><div><dt>Imports orphelins</dt><dd>{snapshot.balances.summary.orphanImportLinks}</dd></div><div><dt>Écart revenus</dt><dd>{money.format(snapshot.balances.summary.revenuesGap)}</dd></div><div><dt>Écart dépenses</dt><dd>{money.format(snapshot.balances.summary.expensesGap)}</dd></div></dl><button className="settings-primary" onClick={() => onNavigate("reconciliation")} type="button">Ouvrir Rapprochements</button><p>Les règles de rapprochement restent dans leur écran métier afin d’éviter un doublon fonctionnel.</p></aside>
        </form>
      )}

      {activeTab === "security" && (
        <form className="settings-overview-grid" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveSecurity(); }}>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Sécurité locale</h2><p>Protection appliquée par les services Python existants.</p></div></div>
            <dl className="settings-kv-list"><div><dt>Vault chiffré</dt><dd><Status value={snapshot.security.encryptedVault} /></dd></div><div><dt>Sauvegardes chiffrées</dt><dd><Status value={snapshot.security.encryptedBackups} /></dd></div><div><dt>Mot de passe maître</dt><dd><Status value={snapshot.security.masterPassword} /></dd></div><div><dt>Algorithme</dt><dd>{snapshot.security.algorithm || "Non initialisé"}</dd></div><div><dt>Clé locale</dt><dd>{snapshot.security.keyStorage || "Non renseignée"}</dd></div></dl>
          </article>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Verrouillage de session</h2><p>Le nouveau délai s’applique au prochain démarrage du moteur local.</p></div></div>
            <label className="settings-timeout-field">Délai avant verrouillage<input max="120" min="1" onChange={(event) => setSessionTimeout(Number(event.target.value))} type="number" value={sessionTimeout} /><span>minutes</span></label>
            <button className="settings-primary" disabled={busy} type="submit">Enregistrer le délai</button>
          </article>
          {profile && (
            <article className="card settings-summary-card">
              <div className="panel-heading"><div><h2>Mon profil</h2><p>Nom, photo et couleur affichés à l’ouverture de Valoria.</p></div></div>
              <div className="settings-profile-row">
                <ProfileAvatar profile={profile} size={64} />
                <div><strong>{profile.name}</strong><small>{profile.kind === "demo" ? "Profil de démonstration" : "Profil personnel"}</small></div>
              </div>
              <div className="security-card-actions">
                <button className="settings-secondary" onClick={() => setSecurityDrawer("profile")} type="button">Modifier le profil</button>
              </div>
            </article>
          )}
          {profile?.kind !== "demo" && (
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Mot de passe et récupération</h2><p>Changez votre mot de passe et gardez un accès de secours.</p></div></div>
            <dl className="settings-kv-list">
              <div><dt>Mot de passe modifié le</dt><dd>{securityStatus?.passwordChangedAt ? formatJournalDate(securityStatus.passwordChangedAt) : "Jamais depuis la création"}</dd></div>
              <div><dt>Clé de secours</dt><dd>{securityStatus?.recoveryKeyConfigured ? `Créée le ${formatJournalDate(securityStatus.recoveryKeyCreatedAt ?? "")}` : <span className="security-warning">Non créée</span>}</dd></div>
            </dl>
            {securityStatus && !securityStatus.recoveryKeyConfigured && <p className="security-warning-note">Sans clé de secours, un mot de passe oublié ne peut pas être récupéré.</p>}
            <div className="security-card-actions">
              <button className="settings-secondary" onClick={() => setSecurityDrawer("password")} type="button">Changer le mot de passe</button>
              <button className="settings-secondary" onClick={() => setSecurityDrawer("recovery")} type="button">{securityStatus?.recoveryKeyConfigured ? "Remplacer la clé de secours" : "Créer la clé de secours"}</button>
            </div>
          </article>
          )}
          <article className="card settings-summary-card security-journal-card">
            <div className="panel-heading"><div><h2>Journal de sécurité</h2><p>Dernières connexions, échecs et verrouillages.</p></div></div>
            {journal.length === 0 ? <small>Aucun événement enregistré.</small> : (
              <ul className="security-journal">
                {journal.slice(0, 12).map((event, index) => (
                  <li data-kind={event.type.endsWith("failure") ? "bad" : "ok"} key={`${event.at}-${index}`}>
                    <span>{formatJournalDate(event.at)}</span><strong>{event.message}</strong>
                  </li>
                ))}
              </ul>
            )}
          </article>
          <article className="card settings-summary-card settings-backup-card"><div className="panel-heading"><div><h2>Sauvegardes</h2><p>Format chiffré Valoria .vvb.</p></div></div><strong>{fileName(snapshot.security.lastBackup) || "Aucune sauvegarde enregistrée"}</strong><small title={snapshot.security.lastBackup}>{snapshot.security.lastBackup || "La création/restauration reste pilotée par le moteur local sécurisé."}</small></article>
        </form>
      )}
      {securityDrawer === "profile" && profile && (
        <ProfileFormDrawer mode="edit" onClose={() => setSecurityDrawer(null)} onSaved={() => { setSecurityDrawer(null); setNotice("Profil mis à jour."); onProfileChanged(); }} profile={profile} token={token} />
      )}
      {securityDrawer === "password" && (
        <ChangePasswordDrawer onClose={() => setSecurityDrawer(null)} onDone={(text) => { setSecurityDrawer(null); setNotice(text); setSecurityRefresh((n) => n + 1); }} token={token} />
      )}
      {securityDrawer === "recovery" && (
        <RecoveryKeyDrawer onClose={() => setSecurityDrawer(null)} onDone={(text) => { setSecurityDrawer(null); setNotice(text); setSecurityRefresh((n) => n + 1); }} replacing={Boolean(securityStatus?.recoveryKeyConfigured)} token={token} />
      )}
    </section>
  );
}

function formatJournalDate(value: string): string {
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function Status({ value }: { value: boolean }) {
  return <span className={value ? "status-chip status-chip--success" : "status-chip status-chip--warning"}>{value ? "Opérationnel" : "À vérifier"}</span>;
}

function optionalNumber(value: string): number | null {
  const clean = value.trim();
  if (!clean) return null;
  const result = Number(clean.replace(",", "."));
  return Number.isFinite(result) ? result : null;
}

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

function formatDate(value: string): string {
  if (!value) return "Date inconnue";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("fr-FR").format(date);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Le moteur Python ne répond pas.";
}
