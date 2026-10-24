import { useState } from "react";
import type { FormEvent } from "react";

import { enableProtection } from "../api/client";
import type { ProtectionEnableResult } from "../api/contracts";
import { RecoveryKeyPanel } from "./RecoveryKeyPanel";
import { SideDrawer } from "./SideDrawer";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

/** Verrouille les données par le mot de passe de l'administrateur connecté. */
export function EnableProtectionDrawer({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: (notice: string) => void }) {
  const [password, setPassword] = useState("");
  const [understood, setUnderstood] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ProtectionEnableResult | null>(null);
  const [keptKey, setKeptKey] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await enableProtection(token, password));
    } catch (reason: unknown) {
      setError(message(reason));
    }
    setBusy(false);
  }

  const done = () => onDone("Données verrouillées par mot de passe. Elles se referment à la fermeture de l’application.");

  return (
    <SideDrawer
      eyebrow="Protection des données"
      onClose={() => (result && !keptKey ? undefined : result ? done() : onClose())}
      title={result ? "Protection activée" : "Verrouiller tes données par mot de passe"}
      footer={result
        ? <button className="settings-primary" disabled={!keptKey} onClick={done} type="button">Terminer</button>
        : <>
            <button className="settings-secondary" onClick={onClose} type="button">Plus tard</button>
            <button className="settings-primary" disabled={busy || !password || !understood} form="enable-protection-form" type="submit">{busy ? "Activation…" : "Activer la protection"}</button>
          </>}
    >
      {result ? (
        <>
          <p>Une copie de sécurité complète a été créée avant la conversion : <strong>{result.safetyCopy}</strong>.</p>
          <p>Voici ta <strong>nouvelle clé de secours</strong> : elle remplace l’ancienne et ouvre aussi le coffre si tu oublies ton mot de passe.</p>
          <RecoveryKeyPanel onConfirmedChange={setKeptKey} recoveryKey={result.recoveryKey} />
        </>
      ) : (
        <form className="drawer-form" id="enable-protection-form" onSubmit={submit}>
          <p>Aujourd’hui, ta base est lisible en clair sur le disque. Après l’activation, elle n’existe en clair que pendant que l’appli est ouverte.</p>
          <div className="protection-steps">
            <strong>Ce qui va se passer</strong>
            <ol>
              <li>Une copie de sécurité complète est créée.</li>
              <li>Ton mot de passe devient la clé du coffre.</li>
              <li>L’ancienne clé stockée sur le poste est supprimée.</li>
              <li>La base en clair est effacée à la fermeture.</li>
            </ol>
          </div>
          <label>Confirme ton mot de passe<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
          <label className="recovery-confirm">
            <input checked={understood} onChange={(e) => setUnderstood(e.target.checked)} type="checkbox" />
            Je comprends que sans mot de passe ni clé de secours, mes données seront illisibles.
          </label>
          {error && <p className="auth-error" role="alert">{error}</p>}
        </form>
      )}
    </SideDrawer>
  );
}
