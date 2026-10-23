import { useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, MouseEvent, ReactNode } from "react";
import { createPortal } from "react-dom";

import { createBackup, deleteBackup, downloadBackup, inspectBackup, listBackups, resetEverything, restoreBackup } from "../api/client";
import type { BackupSource } from "../api/client";
import type { BackupCounts, BackupInfo, BackupInspection, BackupList } from "../api/contracts";
import { ContextMenu } from "./ContextMenu";
import type { ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";

const MIN_PASSPHRASE = 10;
const dateFormat = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

function formatSize(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} Mo` : `${Math.max(1, Math.round(bytes / 1024))} Ko`;
}

function daysSince(value: string | null): number | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : Math.floor((Date.now() - date.getTime()) / 86_400_000);
}

function contentText(counts: BackupCounts): string {
  const parts = [
    counts.accounts !== undefined ? `${counts.accounts} compte(s)` : null,
    counts.transactions !== undefined ? `${counts.transactions} opération(s)` : null,
    counts.users !== undefined ? `${counts.users} profil(s)` : null,
  ].filter(Boolean);
  return parts.join(" · ");
}

function kindLabel(backup: BackupInfo): string {
  if (backup.damaged) return "Illisible";
  if (backup.legacy || backup.kind === "legacy") return "Ancien format";
  return backup.kind === "pre-restore" ? "Avant restauration" : backup.kind === "pre-reset" ? "Avant remise à zéro" : "Manuelle";
}

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

function saveFile(name: string, base64: string) {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function reason(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

function passphraseStrength(value: string): { score: number; text: string } {
  if (!value) return { score: 0, text: "" };
  if (value.length < MIN_PASSPHRASE) return { score: 1, text: `Au moins ${MIN_PASSPHRASE} caractères (${value.length}/${MIN_PASSPHRASE}).` };
  const words = value.trim().split(/\s+/).length;
  if (value.length >= 24 || words >= 4) return { score: 4, text: "Très solide. Une phrase de plusieurs mots est facile à retenir." };
  if (value.length >= 16) return { score: 3, text: "Solide." };
  return { score: 2, text: "Correct. Une phrase de 4 mots ou plus serait plus solide." };
}

type Drawer = { kind: "create" } | { kind: "restore"; source?: BackupInfo } | { kind: "reset" } | null;

/** Paramètres › Sécurité › Protection des données : sauvegarde et restauration chiffrées (administrateur). */
export function BackupAdmin({ token, onNotice, onRestored, children }: { token: string; onNotice: (text: string) => void; onRestored: () => void; children?: ReactNode }) {
  const [list, setList] = useState<BackupList | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [menu, setMenu] = useState<ContextMenuState | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    listBackups(token, controller.signal)
      .then((result) => { setList(result); setError(""); })
      .catch((failure: unknown) => { if (!controller.signal.aborted) setError(reason(failure)); });
    return () => controller.abort();
  }, [token, refresh]);

  const age = daysSince(list?.lastBackupAt ?? null);
  const reminderDays = list?.reminderDays ?? 30;
  const stale = list !== null && (age === null || age >= reminderDays);

  function openMenu(event: MouseEvent, backup: BackupInfo) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Restaurer…", disabled: backup.damaged, onSelect: () => setDrawer({ kind: "restore", source: backup }) },
        {
          label: "Télécharger",
          onSelect: () => void downloadBackup(token, backup.name).then((file) => saveFile(file.name, file.data)).catch((failure: unknown) => setError(reason(failure))),
        },
        {
          label: "Supprimer cette copie",
          danger: true,
          onSelect: () => void deleteBackup(token, backup.name).then(() => { onNotice("Copie supprimée de cet ordinateur."); setRefresh((n) => n + 1); }).catch((failure: unknown) => setError(reason(failure))),
        },
      ],
    });
  }

  return (
    <div className="backup-admin">
      <div className="backup-cards">
        <article className="card settings-summary-card">
          <div className="panel-heading"><div><h2>Sauvegarder</h2><p>Un fichier <strong>.vvb</strong> chiffré par une phrase secrète que vous choisissez. Restaurable sur n’importe quel ordinateur.</p></div></div>
          <dl className="settings-kv-list"><div><dt>Dernière sauvegarde</dt><dd>{list?.lastBackupAt ? formatDate(list.lastBackupAt) : "Jamais"}</dd></div></dl>
          {stale && <p className="backup-reminder">{age === null ? "Aucune sauvegarde n’a encore été faite." : `Il y a ${age} jours.`} Pensez à sauvegarder avant d’importer de nouveaux relevés.</p>}
          <div className="security-card-actions"><button className="settings-primary" onClick={() => setDrawer({ kind: "create" })} type="button">Créer une sauvegarde</button></div>
        </article>
        <article className="card settings-summary-card">
          <div className="panel-heading"><div><h2>Restaurer</h2><p>Remplace les données actuelles par celles d’une sauvegarde. Une copie de sécurité est créée juste avant.</p></div></div>
          <dl className="settings-kv-list"><div><dt>Réservé à</dt><dd>l’administrateur</dd></div></dl>
          <div className="security-card-actions"><button className="settings-secondary" onClick={() => setDrawer({ kind: "restore" })} type="button">Restaurer depuis un fichier…</button></div>
        </article>
        <article className="card settings-summary-card backup-danger-card">
          <div className="panel-heading"><div><h2>Remise à zéro</h2><p>Efface toutes les données et les profils : l’application repart comme à la première installation. Une copie chiffrée est créée avant.</p></div></div>
          <dl className="settings-kv-list"><div><dt>Réservé à</dt><dd>l’administrateur</dd></div></dl>
          <div className="security-card-actions"><button className="settings-secondary settings-danger" onClick={() => setDrawer({ kind: "reset" })} type="button">Tout remettre à zéro…</button></div>
        </article>
        {children}
      </div>
      <article className="card settings-summary-card backup-list-card">
        <div className="panel-heading"><div><h2>Copies conservées sur cet ordinateur</h2><p>Clic droit sur une ligne : Restaurer · Télécharger · Supprimer.</p></div></div>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="backup-table-wrap">
          <table className="settings-table backup-table">
            <thead><tr><th>Date</th><th>Type</th><th>Contenu</th><th>Taille</th></tr></thead>
            <tbody>
              {(list?.backups ?? []).map((backup) => (
                <tr key={backup.name} onContextMenu={(event) => openMenu(event, backup)}>
                  <td>{formatDate(backup.createdAt ?? backup.modifiedAt)}</td>
                  <td>{kindLabel(backup)}</td>
                  <td>{backup.damaged || backup.legacy || backup.kind === "legacy" ? "Contenu visible après déchiffrement" : contentText(backup)}</td>
                  <td>{formatSize(backup.size)}</td>
                </tr>
              ))}
              {list && list.backups.length === 0 && <tr><td colSpan={4}>Aucune copie locale pour le moment.</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="backup-note">Les copies locales sont sur le même disque que vos données : elles ne protègent pas d’une panne du disque. Téléchargez le fichier et rangez-le ailleurs (clé USB, disque externe, cloud personnel). La phrase secrète n’est pas récupérable.</p>
      </article>
      {createPortal(<>
        {drawer?.kind === "create" && (
          <CreateBackupDrawer onClose={() => setDrawer(null)} onDone={() => { setDrawer(null); onNotice("Sauvegarde créée, téléchargée et conservée sur cet ordinateur."); setRefresh((n) => n + 1); }} token={token} />
        )}
        {drawer?.kind === "restore" && (
          <RestoreBackupDrawer onClose={() => setDrawer(null)} onRestored={onRestored} source={drawer.source} token={token} />
        )}
        {drawer?.kind === "reset" && (
          <ResetDrawer onClose={() => setDrawer(null)} onDone={onRestored} token={token} />
        )}
      </>, document.body)}
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(null)} />}
    </div>
  );
}

function PassphraseMeter({ value }: { value: string }) {
  const strength = passphraseStrength(value);
  if (!value) return null;
  return (
    <div className="password-strength" data-score={strength.score}>
      <div className="password-strength__bar" aria-hidden="true"><i /><i /><i /><i /></div>
      <small>{strength.text}</small>
    </div>
  );
}

function CreateBackupDrawer({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: () => void }) {
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [noted, setNoted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const valid = passphrase.length >= MIN_PASSPHRASE && passphrase === confirm && noted;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError("");
    try {
      const file = await createBackup(token, passphrase, confirm);
      saveFile(file.name, file.data);
      onDone();
    } catch (failure: unknown) {
      setError(reason(failure));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Protection des données" onClose={onClose} title="Créer une sauvegarde"
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy || !valid} form="backup-create-form" type="submit">{busy ? "Chiffrement…" : "Créer et télécharger"}</button></>}>
      <form className="drawer-form" id="backup-create-form" onSubmit={submit}>
        <p className="backup-lead">Toute la base familiale : comptes, opérations, patrimoine, budgets, profils et accès.</p>
        <label>Phrase secrète de la sauvegarde<input autoComplete="new-password" autoFocus onChange={(e) => setPassphrase(e.target.value)} type="password" value={passphrase} /></label>
        <PassphraseMeter value={passphrase} />
        <label>Confirmer la phrase secrète<input autoComplete="new-password" onChange={(e) => setConfirm(e.target.value)} type="password" value={confirm} /></label>
        {confirm && passphrase !== confirm && <small className="security-warning">Les deux phrases ne sont pas identiques.</small>}
        <p className="drawer-note"><strong>Cette phrase ne peut pas être récupérée.</strong> Sans elle, la sauvegarde est définitivement illisible. Notez-la ailleurs que sur cet ordinateur.</p>
        <label className="backup-check"><input checked={noted} onChange={(e) => setNoted(e.target.checked)} type="checkbox" />J’ai noté ma phrase secrète dans un endroit sûr.</label>
        <ul className="backup-facts">
          <li>Chiffrement AES-256-GCM, clé dérivée par scrypt.</li>
          <li>Le fichier est téléchargé et une copie reste dans le dossier local de sauvegardes.</li>
          <li>Après création, le fichier est relu et vérifié.</li>
        </ul>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

const RESET_PHRASE = "REMETTRE À ZÉRO";

function ResetDrawer({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [typed, setTyped] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [safety, setSafety] = useState<string | null>(null);
  const valid = password !== "" && typed.trim().toUpperCase() === RESET_PHRASE && passphrase.length >= MIN_PASSPHRASE && passphrase === confirm;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError("");
    try {
      const result = await resetEverything(token, password, typed, passphrase);
      setSafety(result.safetyCopy);
    } catch (failure: unknown) {
      setError(reason(failure));
      setBusy(false);
    }
  }

  if (safety) {
    return (
      <SideDrawer eyebrow="Protection des données" onClose={() => { onDone(); window.location.reload(); }} title="Remise à zéro effectuée"
        footer={<button className="settings-primary" onClick={() => { onDone(); window.location.reload(); }} type="button">Recommencer l’installation</button>}>
        <p className="backup-lead">Toutes les données ont été effacées. Vous allez créer un nouvel administrateur.</p>
        <p className="drawer-note">Copie de sécurité conservée sur cet ordinateur : <strong>{safety}</strong>. Elle se restaure avec la phrase secrète que vous venez de choisir.</p>
      </SideDrawer>
    );
  }

  return (
    <SideDrawer eyebrow="Protection des données" onClose={onClose} title="Tout remettre à zéro"
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary backup-danger-btn" disabled={busy || !valid} form="backup-reset-form" type="submit">{busy ? "Effacement…" : "Effacer toutes les données"}</button></>}>
      <form className="drawer-form" id="backup-reset-form" onSubmit={submit}>
        <p className="drawer-note"><strong>Action irréversible.</strong> Comptes, opérations, récurrences, budgets, patrimoine, scénarios, catégories, règles, profils et mots de passe seront supprimés. L’application demandera ensuite de créer un nouvel administrateur.</p>
        <p className="backup-lead">Avant d’effacer, une copie chiffrée est créée automatiquement : choisissez sa phrase secrète.</p>
        <label>Phrase secrète de la copie de sécurité<input autoComplete="new-password" onChange={(e) => setPassphrase(e.target.value)} type="password" value={passphrase} /></label>
        <PassphraseMeter value={passphrase} />
        <label>Confirmer la phrase secrète<input autoComplete="new-password" onChange={(e) => setConfirm(e.target.value)} type="password" value={confirm} /></label>
        {confirm && passphrase !== confirm && <small className="security-warning">Les deux phrases ne sont pas identiques.</small>}
        <label>Mot de passe de l’administrateur<input autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
        <label>Pour confirmer, tapez « {RESET_PHRASE} »<input autoComplete="off" onChange={(e) => setTyped(e.target.value)} value={typed} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

function RestoreBackupDrawer({ token, source, onClose, onRestored }: { token: string; source?: BackupInfo; onClose: () => void; onRestored: () => void }) {
  const [picked, setPicked] = useState<{ label: string; ref: BackupSource } | null>(source ? { label: source.name, ref: { name: source.name } } : null);
  const [passphrase, setPassphrase] = useState("");
  const [inspection, setInspection] = useState<BackupInspection | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const legacy = source?.legacy === true || source?.kind === "legacy";

  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setInspection(null);
    try {
      setPicked({ label: file.name, ref: { data: toBase64(await file.arrayBuffer()) } });
    } catch {
      setError("Impossible de lire ce fichier.");
    }
  }

  async function verify(event: FormEvent) {
    event.preventDefault();
    if (!picked) return;
    setBusy(true);
    setError("");
    try {
      setInspection(await inspectBackup(token, picked.ref, passphrase));
    } catch (failure: unknown) {
      setInspection(null);
      setError(reason(failure));
    }
    setBusy(false);
  }

  async function restore(event: FormEvent) {
    event.preventDefault();
    if (!picked || !inspection) return;
    setBusy(true);
    setError("");
    try {
      const result = await restoreBackup(token, picked.ref, passphrase, password);
      setDone(result.safetyCopy);
    } catch (failure: unknown) {
      setError(reason(failure));
    }
    setBusy(false);
  }

  if (done) {
    return (
      <SideDrawer eyebrow="Protection des données" onClose={onRestored} title="Sauvegarde restaurée"
        footer={<button className="settings-primary" onClick={onRestored} type="button">Se reconnecter</button>}>
        <p className="backup-lead">Les données de la sauvegarde sont en place. Tous les profils ont été déconnectés ; mots de passe et accès sont ceux de la sauvegarde.</p>
        <p className="drawer-note">Votre état d’avant restauration est conservé dans « {done} » (même phrase secrète). Vous pouvez le restaurer pour revenir en arrière.</p>
      </SideDrawer>
    );
  }

  const step = !picked ? 1 : !inspection ? 2 : 3;
  const comparison: [string, number | undefined, number | undefined][] = inspection
    ? [["Comptes", inspection.current.accounts, inspection.backup.accounts], ["Opérations", inspection.current.transactions, inspection.backup.transactions], ["Profils", inspection.current.users, inspection.backup.users]]
    : [];
  const loses = inspection ? (inspection.current.transactions ?? 0) - (inspection.backup.transactions ?? 0) : 0;

  return (
    <SideDrawer eyebrow="Protection des données" onClose={onClose} title="Restaurer une sauvegarde"
      footer={<>
        <button className="settings-secondary" onClick={onClose} type="button">Annuler</button>
        {step === 2 && <button className="settings-primary" disabled={busy || passphrase.length < MIN_PASSPHRASE} form="backup-verify-form" type="submit">{busy ? "Vérification…" : "Vérifier le fichier"}</button>}
        {step === 3 && <button className="settings-danger" disabled={busy || !password} form="backup-restore-form" type="submit">{busy ? "Restauration…" : "Restaurer et fermer la session"}</button>}
      </>}>
      <ol className="backup-steps" aria-label="Étapes">
        <li data-state={step > 1 ? "done" : "current"}>1 Fichier</li>
        <li data-state={step > 2 ? "done" : step === 2 ? "current" : "todo"}>2 Phrase secrète</li>
        <li data-state={step === 3 ? "current" : "todo"}>3 Confirmer</li>
      </ol>
      <input accept=".vvb" hidden onChange={(event) => void chooseFile(event)} ref={fileInput} type="file" />
      {step === 1 && (
        <div className="drawer-form">
          <p className="backup-lead">Choisissez un fichier de sauvegarde <strong>.vvb</strong>.</p>
          <button className="settings-secondary" onClick={() => fileInput.current?.click()} type="button">Choisir un fichier…</button>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </div>
      )}
      {step >= 2 && picked && (
        <div className="backup-picked"><strong>{picked.label}</strong>{inspection && <span className="backup-ok">Déchiffrée · intégrité vérifiée</span>}{step === 2 && !source && <button className="settings-secondary" onClick={() => { setPicked(null); setPassphrase(""); setError(""); }} type="button">Changer de fichier</button>}</div>
      )}
      {step === 2 && (
        <form className="drawer-form" id="backup-verify-form" onSubmit={verify}>
          <label>{legacy ? "Nouvelle phrase secrète (protège la copie d’avant restauration)" : "Phrase secrète de cette sauvegarde"}<input autoComplete="off" autoFocus onChange={(e) => setPassphrase(e.target.value)} type="password" value={passphrase} /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </form>
      )}
      {step === 3 && inspection && (
        <form className="drawer-form" id="backup-restore-form" onSubmit={restore}>
          <div className="backup-compare">
            <span /><b>Actuel</b><b>Sauvegarde</b>
            {comparison.map(([label, now, then]) => <div key={label}><span>{label}</span><b>{now ?? "—"}</b><b>{then ?? "—"}</b></div>)}
          </div>
          <p className="backup-lead">Créée le {formatDate(inspection.backup.createdAt)}.{loses > 0 && <> <span className="security-warning">{loses} opération(s) récente(s) seront perdues</span>, sauf retour à la copie d’avant restauration.</>}</p>
          <p className="drawer-note"><strong>Ceci remplace toutes les données actuelles.</strong> Une copie de sécurité de l’état actuel est créée juste avant. Tous les profils seront déconnectés ; mots de passe et accès reviendront à ceux de la sauvegarde.</p>
          <label>Votre mot de passe d’administrateur<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </form>
      )}
    </SideDrawer>
  );
}
