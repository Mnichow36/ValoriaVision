import { useState } from "react";
import type { FormEvent } from "react";

import { changePassword, createRecoveryKey, recoverAccess } from "../api/client";
import type { RecoveryRequestResult } from "../api/contracts";
import { RecoveryKeyPanel } from "./RecoveryKeyPanel";
import { SideDrawer } from "./SideDrawer";
import { evaluatePassword } from "./passwordStrength";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

export function PasswordStrengthMeter({ password }: { password: string }) {
  const strength = evaluatePassword(password);
  if (!password) return null;
  return (
    <div className="password-strength" data-score={strength.score}>
      <div className="password-strength__bar" aria-hidden="true"><i /><i /><i /><i /></div>
      <small>{strength.acceptable ? `Force : ${strength.label}` : strength.hint}</small>
    </div>
  );
}

export function ChangePasswordDrawer({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: (notice: string) => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (next !== confirmation) return setError("Les deux mots de passe ne correspondent pas.");
    const strength = evaluatePassword(next);
    if (!strength.acceptable) return setError(strength.hint || "Mot de passe trop faible.");
    setBusy(true);
    setError("");
    try {
      await changePassword(token, current, next);
      onDone("Mot de passe modifié.");
    } catch (reason: unknown) {
      setError(message(reason));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Sécurité" onClose={onClose} title="Changer le mot de passe"
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy || !current || !next} form="change-password-form" type="submit">{busy ? "Enregistrement…" : "Modifier"}</button></>}>
      <form className="drawer-form" id="change-password-form" onSubmit={submit}>
        <label>Mot de passe actuel<input autoComplete="current-password" autoFocus onChange={(e) => setCurrent(e.target.value)} type="password" value={current} /></label>
        <label>Nouveau mot de passe<input autoComplete="new-password" onChange={(e) => setNext(e.target.value)} type="password" value={next} /></label>
        <PasswordStrengthMeter password={next} />
        <label>Confirmer le nouveau mot de passe<input autoComplete="new-password" onChange={(e) => setConfirmation(e.target.value)} type="password" value={confirmation} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

export function RecoveryKeyDrawer({ token, replacing, onClose, onDone }: { token: string; replacing: boolean; onClose: () => void; onDone: (notice: string) => void }) {
  const [password, setPassword] = useState("");
  const [recoveryKey, setRecoveryKey] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await createRecoveryKey(token, password);
      setRecoveryKey(result.recoveryKey);
    } catch (reason: unknown) {
      setError(message(reason));
    }
    setBusy(false);
  }

  return (
    <SideDrawer eyebrow="Sécurité" onClose={() => (recoveryKey && !confirmed ? undefined : recoveryKey ? onDone(replacing ? "Clé de secours remplacée." : "Clé de secours créée.") : onClose())}
      title={replacing ? "Remplacer la clé de secours" : "Créer la clé de secours"}
      footer={recoveryKey
        ? <button className="settings-primary" disabled={!confirmed} onClick={() => onDone(replacing ? "Clé de secours remplacée." : "Clé de secours créée.")} type="button">Terminer</button>
        : <><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy || !password} form="recovery-key-form" type="submit">{busy ? "Génération…" : "Générer la clé"}</button></>}>
      {recoveryKey ? <RecoveryKeyPanel onConfirmedChange={setConfirmed} recoveryKey={recoveryKey} /> : (
        <form className="drawer-form" id="recovery-key-form" onSubmit={submit}>
          <p>{replacing ? "Une nouvelle clé remplacera l’ancienne, qui deviendra inutilisable." : "Cette clé vous permettra de retrouver l’accès si vous oubliez votre mot de passe."} Confirmez avec votre mot de passe.</p>
          <label>Mot de passe maître<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </form>
      )}
    </SideDrawer>
  );
}

export function RecoverAccessDrawer({ onClose, onRecovered }: { onClose: () => void; onRecovered: (token: string) => void }) {
  const [key, setKey] = useState("");
  const [next, setNext] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [result, setResult] = useState<RecoveryRequestResult | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (next !== confirmation) return setError("Les deux mots de passe ne correspondent pas.");
    const strength = evaluatePassword(next);
    if (!strength.acceptable) return setError(strength.hint || "Mot de passe trop faible.");
    setBusy(true);
    setError("");
    try {
      setResult(await recoverAccess(key, next));
    } catch (reason: unknown) {
      setError(message(reason));
    }
    setBusy(false);
  }

  return (
    <SideDrawer eyebrow="Accès" onClose={() => (result ? undefined : onClose())} title="Mot de passe oublié"
      footer={result
        ? <button className="settings-primary" disabled={!confirmed} onClick={() => onRecovered(result.token)} type="button">Ouvrir mon espace</button>
        : <><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy || !key || !next} form="recover-form" type="submit">{busy ? "Vérification…" : "Réinitialiser"}</button></>}>
      {result ? (
        <>
          <p><strong>Mot de passe réinitialisé.</strong> Votre ancienne clé de secours n’est plus valable : voici la nouvelle.</p>
          <RecoveryKeyPanel onConfirmedChange={setConfirmed} recoveryKey={result.recoveryKey} />
        </>
      ) : (
        <form className="drawer-form" id="recover-form" onSubmit={submit}>
          <p>Saisissez la clé de secours créée dans Paramètres › Sécurité, puis choisissez un nouveau mot de passe.</p>
          <label>Clé de secours<input autoComplete="off" autoFocus onChange={(e) => setKey(e.target.value)} placeholder="XXXX-XXXX-XXXX-XXXX-XXXX-XXXX" spellCheck={false} value={key} /></label>
          <label>Nouveau mot de passe<input autoComplete="new-password" onChange={(e) => setNext(e.target.value)} type="password" value={next} /></label>
          <PasswordStrengthMeter password={next} />
          <label>Confirmer le nouveau mot de passe<input autoComplete="new-password" onChange={(e) => setConfirmation(e.target.value)} type="password" value={confirmation} /></label>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </form>
      )}
    </SideDrawer>
  );
}
