import { WriteOnly } from "../permissions";
import { BRAND_SLOGAN, BrandMark, DeltaGlyph, STUDIO_NAME } from "./Brand";
import { useEffect, useState } from "react";

import {
  getSettings,
  updateSettingsGeneral,
  getSecurityJournal,
  getSecurityStatus,
} from "../api/client";
import type {
  Profile,
  SecurityEvent,
  SecurityStatus,
  SettingsSnapshot,
} from "../api/contracts";
import { ChangePasswordDrawer, RecoveryKeyDrawer } from "./PasswordDrawers";
import { DeletePinDrawer, PinDrawer } from "./PinDrawers";
import { ProfileAvatar } from "./ProfileAvatar";
import { BackupAdmin } from "./BackupAdmin";
import { AccessAdmin } from "./AccessAdmin";
import { ProfileFormDrawer } from "./ProfileDrawers";
import type { NavigationId } from "./Sidebar";
import { SettingsCategoriesTab } from "./SettingsCategoriesTab";
import { SettingsRulesTab } from "./SettingsRulesTab";
import { ThemeSwitch } from "./ThemeSwitch";

type SecurityView = "access" | "profiles" | "journal" | "protection";
const securityViews: { id: SecurityView; label: string; admin?: boolean }[] = [
  { id: "access", label: "Mon accès" },
  { id: "profiles", label: "Profils et accès", admin: true },
  { id: "journal", label: "Journal", admin: true },
  { id: "protection", label: "Protection des données" },
];

type SettingsTab = "general" | "categories" | "rules" | "balances" | "security";

const tabs: Array<{ id: SettingsTab; label: string }> = [
  { id: "general", label: "Général" },
  { id: "categories", label: "Catégories" },
  { id: "rules", label: "Règles de catégorisation" },
  { id: "balances", label: "Soldes" },
  { id: "security", label: "Sécurité" },
];

const money = new Intl.NumberFormat("fr-FR", {
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 2,
  style: "currency",
});

export function SettingsPage({ onNavigate, token, profile, onProfileChanged, onSessionEnded, onTabChange, onShowCategoryOperations, onOpenSuggestions }: { onNavigate: (destination: NavigationId | "reconciliation") => void; token: string; profile: Profile | null; onProfileChanged: () => void; onSessionEnded: () => void; onTabChange?: (tab: string) => void; onShowCategoryOperations?: (categoryName: string) => void; onOpenSuggestions?: () => void }) {
  const [snapshot, setSnapshot] = useState<SettingsSnapshot | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("rules");
  const [securityView, setSecurityView] = useState<SecurityView>("access");
  const isAdmin = profile?.role === "admin" && profile.kind !== "demo";
  const [currentMonth, setCurrentMonth] = useState("");
  const [sessionTimeout, setSessionTimeout] = useState(10);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [journal, setJournal] = useState<SecurityEvent[]>([]);
  const [securityStatus, setSecurityStatus] = useState<SecurityStatus | null>(null);
  const [securityDrawer, setSecurityDrawer] = useState<"password" | "recovery" | "profile" | "pin" | "pin-delete" | null>(null);
  const [securityRefresh, setSecurityRefresh] = useState(0);

  async function refresh(signal?: AbortSignal) {
    const next = await getSettings(token, signal);
    setSnapshot(next);
    setCurrentMonth(next.general.currentMonth);
    setSessionTimeout(next.security.sessionTimeoutMinutes);
  }

  useEffect(() => { onTabChange?.(activeTab); }, [activeTab, onTabChange]);

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

  async function run(action: () => Promise<{ message: string; id?: number }>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await action();
      setNotice(result.message);
      await refresh();
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

  async function afterChange(message: string) {
    setNotice(message);
    setError("");
    await refresh();
  }

  return (
    <section className={activeTab === "categories" || activeTab === "rules" ? "settings-page settings-page--fill" : "settings-page"}>
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
        <form className="settings-overview-grid settings-overview-grid--general" id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveGeneral(); }}>
          <div className="settings-general-left">
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Préférences générales</h2><p>Réglages communs utilisés par tous les écrans.</p></div></div>
            <div className="settings-form-grid">
              <label>Devise<select disabled value={snapshot.general.currency}><option>EUR</option></select></label>
              <label>Langue<select disabled value={snapshot.general.locale}><option value="fr">Français</option></select></label>
              <label>Mois de travail<input onChange={(event) => setCurrentMonth(event.target.value)} pattern="\d{4}-(0[1-9]|1[0-2])" placeholder="AAAA-MM" value={currentMonth} /></label>
            </div>
            <div className="settings-theme-row"><div><strong>Apparence</strong><small>Clair, sombre, ou selon le réglage de ton système. Mémorisé sur ce poste.</small></div><ThemeSwitch variant="settings" /></div>
            <WriteOnly><button className="settings-primary" disabled={busy} type="submit">Enregistrer les préférences</button></WriteOnly>
          </article>
          <article className="card settings-summary-card settings-about-card">
            <div className="panel-heading"><div><h2>À propos</h2><p>{BRAND_SLOGAN}</p></div></div>
            <div className="settings-about-brand"><BrandMark size={52} /><div><strong>Valoria Vision</strong><small>Le cockpit financier de votre patrimoine</small></div></div>
            <div className="settings-about-studio"><DeltaGlyph filled size={28} /><div><small>Développé par</small><strong>{STUDIO_NAME}</strong></div></div>
          </article>
          </div>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Socle local</h2><p>État de la base utilisée par les moteurs Python.</p></div></div>
            <dl className="settings-kv-list">
              <div><dt>Intégrité SQLite</dt><dd><Status value={snapshot.general.integrity === "ok"} /></dd></div>
              <div><dt>Version du schéma</dt><dd>V{snapshot.general.schemaVersion}</dd></div>
              <div><dt>Taille de la base</dt><dd>{snapshot.general.databaseSizeKb.toLocaleString("fr-FR")} Ko</dd></div>
              <div><dt>Dernière sauvegarde</dt><dd title={snapshot.general.lastBackup}>{fileName(snapshot.general.lastBackup) || "Aucune"}</dd></div>
            </dl>
          </article>
        </form>
      )}

      {activeTab === "categories" && (
        <SettingsCategoriesTab categories={snapshot.categories} onChanged={afterChange} onShowOperations={(name) => onShowCategoryOperations?.(name)} token={token} />
      )}

      {activeTab === "rules" && (
        <SettingsRulesTab onChanged={afterChange} onOpenSuggestions={() => onOpenSuggestions?.()} snapshot={snapshot} token={token} />
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
        <>
        <nav aria-label="Sections de la sécurité" className="settings-subtabs">
          {securityViews.filter((view) => !view.admin || isAdmin).map((view) => (
            <button aria-pressed={securityView === view.id} key={view.id} onClick={() => setSecurityView(view.id)} type="button">{view.label}</button>
          ))}
        </nav>
        <form className={securityView === "access" ? "settings-overview-grid settings-overview-grid--3" : securityView === "protection" && !isAdmin ? "settings-overview-grid" : "settings-overview-grid settings-overview-grid--1"} id="settings-active-form" onSubmit={(event) => { event.preventDefault(); void saveSecurity(); }}>
          {securityView === "access" && (
            <>
          {profile && (
            <article className="card settings-summary-card">
              <div className="panel-heading"><div><h2>Mon profil</h2><p>Nom, photo et couleur affichés à l’ouverture de Valoria.</p></div></div>
              <div className="settings-profile-row">
                <ProfileAvatar profile={profile} size={64} />
                <div><strong>{profile.name}</strong><small>{profile.kind === "demo" ? "Profil de démonstration" : profile.roleLabel ?? "Profil personnel"}</small></div>
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
          {profile?.kind !== "demo" && (
          <article className="card settings-summary-card pin-card">
            <div className="panel-heading"><div><h2>Code PIN</h2><p>6 chiffres pour rouvrir votre profil rapidement après un verrouillage automatique. Le mot de passe reste nécessaire à l’ouverture de l’application.</p></div></div>
            <dl className="settings-kv-list">
              <div><dt>État</dt><dd>{securityStatus?.pinConfigured ? <span className="status-chip status-chip--success">Activé</span> : <span className="status-chip status-chip--warning">Non activé</span>}</dd></div>
              {securityStatus?.pinConfigured && <div><dt>Créé le</dt><dd>{securityStatus.pinCreatedAt ? formatJournalDate(securityStatus.pinCreatedAt) : "—"}</dd></div>}
              {securityStatus?.pinConfigured && <div><dt>Dernier usage</dt><dd>{securityStatus.pinLastUsedAt ? formatJournalDate(securityStatus.pinLastUsedAt) : "Jamais"}</dd></div>}
            </dl>
            <div className="security-card-actions">
              <button className={securityStatus?.pinConfigured ? "settings-secondary" : "settings-primary"} onClick={() => setSecurityDrawer("pin")} type="button">{securityStatus?.pinConfigured ? "Changer le PIN" : "Créer mon PIN"}</button>
              {securityStatus?.pinConfigured && <button className="settings-secondary" onClick={() => setSecurityDrawer("pin-delete")} type="button">Supprimer le PIN</button>}
            </div>
          </article>
          )}
          <article className="card settings-summary-card settings-session-card">
            <div className="panel-heading"><div><h2>Verrouillage de session</h2><p>Le nouveau délai s’applique au prochain démarrage du moteur local.</p></div></div>
            <label className="settings-timeout-field">Délai avant verrouillage<input max="120" min="1" onChange={(event) => setSessionTimeout(Number(event.target.value))} type="number" value={sessionTimeout} /><span>minutes</span></label>
            <button className="settings-primary" disabled={busy} type="submit">Enregistrer le délai</button>
          </article>
            </>
          )}
          {securityView === "profiles" && isAdmin && profile && (
            <AccessAdmin currentProfileId={profile.id} onChanged={onProfileChanged} onNotice={setNotice} token={token} />
          )}
          {securityView === "journal" && isAdmin && (
          <article className="card settings-summary-card security-journal-card">
            <div className="panel-heading"><div><h2>Journal de sécurité</h2><p>Dernières connexions, échecs et verrouillages.</p></div></div>
            {journal.length === 0 ? <small>Aucun événement enregistré.</small> : (
              <ul className="security-journal">
                {journal.slice(0, 30).map((event, index) => (
                  <li data-kind={event.type.endsWith("failure") ? "bad" : "ok"} key={`${event.at}-${index}`}>
                    <span>{formatJournalDate(event.at)}</span><strong>{event.message}</strong>
                  </li>
                ))}
              </ul>
            )}
          </article>
          )}
          {securityView === "protection" && isAdmin && (
            <BackupAdmin onNotice={setNotice} onRestored={onSessionEnded} token={token}>
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Sécurité locale</h2><p>Protection appliquée par les services Python existants.</p></div></div>
            <dl className="settings-kv-list"><div><dt>Vault chiffré</dt><dd><Status value={snapshot.security.encryptedVault} /></dd></div><div><dt>Sauvegardes</dt><dd><span className="status-chip status-chip--success">Phrase secrète</span></dd></div><div><dt>Mot de passe maître</dt><dd><Status value={snapshot.security.masterPassword} /></dd></div><div><dt>Algorithme</dt><dd>{snapshot.security.algorithm || "Non initialisé"}</dd></div><div><dt>Clé locale</dt><dd>{snapshot.security.keyStorage || "Non renseignée"}</dd></div></dl>
          </article>
            </BackupAdmin>
          )}
          {securityView === "protection" && !isAdmin && (
          <article className="card settings-summary-card">
            <div className="panel-heading"><div><h2>Sécurité locale</h2><p>Protection appliquée par les services Python existants.</p></div></div>
            <dl className="settings-kv-list"><div><dt>Vault chiffré</dt><dd><Status value={snapshot.security.encryptedVault} /></dd></div><div><dt>Sauvegardes</dt><dd><span className="status-chip status-chip--success">Phrase secrète</span></dd></div><div><dt>Mot de passe maître</dt><dd><Status value={snapshot.security.masterPassword} /></dd></div><div><dt>Algorithme</dt><dd>{snapshot.security.algorithm || "Non initialisé"}</dd></div><div><dt>Clé locale</dt><dd>{snapshot.security.keyStorage || "Non renseignée"}</dd></div></dl>
          </article>
          )}
        </form>
        </>
      )}
      {securityDrawer === "profile" && profile && (
        <ProfileFormDrawer mode="edit" onClose={() => setSecurityDrawer(null)} onSaved={() => { setSecurityDrawer(null); setNotice("Profil mis à jour."); onProfileChanged(); }} profile={profile} token={token} />
      )}
      {securityDrawer === "password" && (
        <ChangePasswordDrawer onClose={() => setSecurityDrawer(null)} onDone={(text) => { setSecurityDrawer(null); setNotice(text); setSecurityRefresh((n) => n + 1); }} token={token} />
      )}
      {securityDrawer === "pin" && (
        <PinDrawer onClose={() => setSecurityDrawer(null)} onDone={(text) => { setSecurityDrawer(null); setNotice(text); setSecurityRefresh((n) => n + 1); onProfileChanged(); }} replacing={Boolean(securityStatus?.pinConfigured)} token={token} />
      )}
      {securityDrawer === "pin-delete" && (
        <DeletePinDrawer onClose={() => setSecurityDrawer(null)} onDone={(text) => { setSecurityDrawer(null); setNotice(text); setSecurityRefresh((n) => n + 1); onProfileChanged(); }} token={token} />
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
