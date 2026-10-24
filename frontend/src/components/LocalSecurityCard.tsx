import type { SettingsSnapshot } from "../api/contracts";

function dateOnly(value: string | null): string {
  if (!value) return "Non créée";
  const date = new Date(value.includes("T") ? value : `${value.replace(" ", "T")}Z`);
  return Number.isNaN(date.getTime()) ? value : `Créée le ${date.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })}`;
}

interface Props {
  security: SettingsSnapshot["security"];
  protectionEnabled: boolean;
  recoveryCreatedAt: string | null;
  profilesWithAccess?: number;
  totalProfiles?: number;
  /** Absents pour un profil non administrateur : la carte est alors en lecture seule. */
  onEnable?: () => void;
  onLock?: () => void;
}

/** Paramètres › Sécurité › Protection des données : ce qui protège les données sur cet ordinateur. */
export function LocalSecurityCard({ security, protectionEnabled, recoveryCreatedAt, profilesWithAccess, totalProfiles, onEnable, onLock }: Props) {
  return (
    <article className="card settings-summary-card local-security-card">
      <div className="panel-heading local-security-card__head">
        <div><h2>Sécurité locale</h2><p>Ce qui protège tes données sur cet ordinateur.</p></div>
        {protectionEnabled
          ? onLock && <button className="settings-secondary" onClick={onLock} type="button">Verrouiller maintenant</button>
          : onEnable && <button className="settings-primary" onClick={onEnable} type="button">Verrouiller par mot de passe…</button>}
      </div>
      <dl className="settings-kv-list">
        <div><dt>Coffre chiffré</dt><dd><span className={security.encryptedVault ? "status-chip status-chip--success" : "status-chip status-chip--warning"}>{security.encryptedVault ? "Opérationnel" : "À vérifier"}</span></dd></div>
        <div><dt>Ouverture du coffre</dt><dd>{protectionEnabled ? "Par ton mot de passe" : "Clé stockée sur cet ordinateur"}</dd></div>
        <div><dt>Base en clair sur le disque</dt><dd>{protectionEnabled ? "Seulement pendant l’utilisation" : "Présente en permanence"}</dd></div>
        <div><dt>Clé de secours</dt><dd>{recoveryCreatedAt ? <span className="status-chip status-chip--success">{dateOnly(recoveryCreatedAt)}</span> : <span className="status-chip status-chip--warning">Non créée</span>}</dd></div>
        <div><dt>Algorithme</dt><dd>{security.algorithm || "Non initialisé"}</dd></div>
        {protectionEnabled && profilesWithAccess !== undefined && totalProfiles !== undefined && (
          <div><dt>Accès déverrouillés</dt><dd>{profilesWithAccess} sur {totalProfiles} profil{totalProfiles > 1 ? "s" : ""}</dd></div>
        )}
      </dl>
      {protectionEnabled ? (
        <p className="protection-notice"><strong>Sans ton mot de passe ni ta clé de secours, personne ne peut relire les données</strong> : ni toi, ni l’appli. Garde la clé de secours hors de l’ordinateur.</p>
      ) : (
        <p className="protection-notice protection-notice--info">Ta base est aujourd’hui lisible en clair sur le disque. Verrouille-la par ton mot de passe pour qu’elle ne le soit plus qu’en cours d’utilisation.</p>
      )}
    </article>
  );
}
