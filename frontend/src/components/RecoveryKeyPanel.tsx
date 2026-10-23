import { useState } from "react";

/** Affiche la clé de secours une seule fois ; la fermeture exige une confirmation explicite. */
export function RecoveryKeyPanel({ recoveryKey, onConfirmedChange }: { recoveryKey: string; onConfirmedChange: (confirmed: boolean) => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(recoveryKey);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="recovery-panel">
      <p>Cette clé ne sera <strong>plus jamais affichée</strong>. Conservez-la hors de cet ordinateur (papier, coffre, gestionnaire de mots de passe) : elle permet de retrouver l’accès si vous oubliez votre mot de passe.</p>
      <div className="recovery-sheet">
        <small>Valoria Vision · Clé de secours</small>
        <code aria-label="Clé de secours">{recoveryKey}</code>
        <small>Ne la partagez avec personne.</small>
      </div>
      <div className="recovery-actions">
        <button className="settings-secondary" onClick={() => void copy()} type="button">{copied ? "Copiée ✓" : "Copier"}</button>
        <button className="settings-secondary" onClick={() => window.print()} type="button">Imprimer</button>
      </div>
      <label className="recovery-confirm">
        <input onChange={(event) => onConfirmedChange(event.target.checked)} type="checkbox" />
        Je l’ai conservée hors de cet ordinateur
      </label>
    </div>
  );
}
