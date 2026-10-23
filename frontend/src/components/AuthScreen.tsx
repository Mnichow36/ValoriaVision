import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import type { Profile } from "../api/contracts";
import { RecoverAccessDrawer } from "./PasswordDrawers";
import { ProfileAvatar } from "./ProfileAvatar";
import { ProfileFormDrawer } from "./ProfileDrawers";
import { SideDrawer } from "./SideDrawer";

interface AuthScreenProps {
  profiles: Profile[];
  /** Profil à présenter d'emblée (ex. celui qui vient d'être verrouillé) ; null = choix du profil. */
  preferredProfileId?: string | null;
  busy: boolean;
  error?: string;
  retryAfter?: number;
  onUnlock: (profileId: string, password: string) => Promise<void>;
  onRecovered: (token: string) => void;
  onProfilesChanged: () => Promise<void>;
}

type Drawer = { kind: "create" } | { kind: "recover"; profile: Profile } | null;

function lastLogin(profile: Profile): string {
  if (!profile.lastLoginAt) return "Jamais connecté";
  const date = new Date(`${profile.lastLoginAt.replace(" ", "T")}Z`);
  if (Number.isNaN(date.getTime())) return "";
  return `Dernière connexion : ${date.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}`;
}

export function AuthScreen({ profiles, preferredProfileId, busy, error, retryAfter, onUnlock, onRecovered, onProfilesChanged }: AuthScreenProps) {
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    if (preferredProfileId && profiles.some((p) => p.id === preferredProfileId)) return preferredProfileId;
    return preferredProfileId === null ? null : profiles.length === 1 ? profiles[0].id : null;
  });
  const [password, setPassword] = useState("");
  const [wait, setWait] = useState(retryAfter ?? 0);
  const [drawer, setDrawer] = useState<Drawer>(null);

  const selected = useMemo(() => profiles.find((p) => p.id === selectedId) ?? null, [profiles, selectedId]);

  useEffect(() => { setWait(retryAfter ?? 0); }, [retryAfter, error]);
  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);
  useEffect(() => {
    if (selectedId && !profiles.some((p) => p.id === selectedId)) setSelectedId(null);
  }, [profiles, selectedId]);
  useEffect(() => { if (profiles.length === 0) setDrawer({ kind: "create" }); }, [profiles.length]);

  function choose(profile: Profile) {
    setPassword("");
    if (profile.kind === "demo" && !profile.configured) void onUnlock(profile.id, "");
    else setSelectedId(profile.id);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (selected) await onUnlock(selected.id, password);
  }

  return (
    <main className="auth-shell">
      {selected ? (
        <section className="auth-card">
          <div className="auth-profile-head">
            <ProfileAvatar profile={selected} size={56} />
            <div><span className="eyebrow">Profil</span><h1>{selected.name}</h1></div>
          </div>
          <form onSubmit={submit}>
            <label htmlFor="master-password">Mot de passe du profil</label>
            <input autoComplete="current-password" autoFocus id="master-password" onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
            {error && <p className="auth-error" role="alert">{error}</p>}
            {wait > 0 && !error && <p className="auth-error" role="status">Nouvel essai possible dans {wait} s.</p>}
            <button disabled={busy || wait > 0} type="submit">{busy ? "Vérification…" : wait > 0 ? `Patientez ${wait} s` : "Déverrouiller"}</button>
          </form>
          <div className="auth-links">
            <button className="auth-link" onClick={() => { setSelectedId(null); setPassword(""); }} type="button">← Changer de profil</button>
            <button className="auth-link" onClick={() => setDrawer({ kind: "recover", profile: selected })} type="button">Mot de passe oublié ?</button>
          </div>
          <small>Ce mot de passe protège l’accès à ce profil. Il ne quitte jamais cet ordinateur.</small>
        </section>
      ) : (
        <section className="profile-picker">
          <div className="auth-brand"><span>V</span><strong>Valoria Vision</strong></div>
          <div className="profile-picker__intro">
            <p className="eyebrow">Données financières locales</p>
            <h1>{profiles.length ? "Qui utilise Valoria aujourd’hui ?" : "Créons le profil administrateur"}</h1>
            <p>Une seule base familiale. Votre profil détermine ce que vous voyez et ce que vous pouvez modifier.</p>
          </div>
          {error && <p className="auth-error" role="alert">{error}</p>}
          <div className="profile-grid">
            {profiles.map((profile) => (
              <button className="profile-card" disabled={busy} key={profile.id} onClick={() => choose(profile)} type="button">
                <ProfileAvatar profile={profile} size={84} />
                <strong>{profile.name}</strong>
                <span className="profile-card__meta">{profile.kind === "demo" ? "Données fictives · sans mot de passe" : lastLogin(profile)}</span>
                {profile.kind === "demo"
                  ? <span className="profile-badge profile-badge--info">Mode démonstration</span>
                  : <span className={`profile-badge ${profile.role === "admin" ? "profile-badge--info" : profile.role === "reader" ? "profile-badge--reader" : "profile-badge--ok"}`}>{roleBadge(profile)}</span>}
              </button>
            ))}
            {profiles.length === 0 && (
              <button className="profile-card profile-card--add" onClick={() => setDrawer({ kind: "create" })} type="button">
                <span className="profile-add-circle" aria-hidden="true">+</span>
                <strong>Créer l’administrateur</strong>
              </button>
            )}
          </div>
          <small>Aucune connexion bancaire · tout reste sur cet ordinateur</small>
        </section>
      )}

      {drawer?.kind === "create" && (
        <ProfileFormDrawer
          firstRun
          mode="create"
          onClose={() => setDrawer(null)}
          onCreated={(profile, pwd) => {
            setDrawer(null);
            void onProfilesChanged().then(() => { if (pwd) return onUnlock(profile.id, pwd); });
          }}
        />
      )}
      {drawer?.kind === "recover" && (
        drawer.profile.recoveryKeyConfigured
          ? <RecoverAccessDrawer onClose={() => setDrawer(null)} onRecovered={onRecovered} profileId={drawer.profile.id} />
          : <NoRecoveryKey onClose={() => setDrawer(null)} />
      )}
    </main>
  );
}

function roleBadge(profile: Profile): string {
  const label = profile.roleLabel ?? "Profil";
  if (profile.role && profile.role !== "admin" && profile.totalAccounts !== undefined) {
    const visible = (profile.scopeAccounts ?? 0) + (profile.scopeAssets ?? 0);
    const total = (profile.totalAccounts ?? 0) + (profile.totalAssets ?? 0);
    return `${label} · ${visible} sur ${total}`;
  }
  return label;
}

function NoRecoveryKey({ onClose }: { onClose: () => void }) {
  return (
    <SideDrawer eyebrow="Accès" onClose={onClose} title="Mot de passe oublié"
      footer={<button className="settings-primary" onClick={onClose} type="button">Compris</button>}>
      <p>Aucune clé de secours n’a été créée pour ce profil, la réinitialisation est donc impossible.</p>
      <p>Pour l’avenir : créez-la dès maintenant dans <strong>Paramètres › Sécurité</strong> une fois connecté, et conservez-la hors de cet ordinateur.</p>
    </SideDrawer>
  );
}
