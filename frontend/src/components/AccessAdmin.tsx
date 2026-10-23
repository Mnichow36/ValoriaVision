import { useEffect, useState } from "react";
import type { MouseEvent } from "react";
import { createPortal } from "react-dom";

import { getAccessMatrix, getAuthStatus } from "../api/client";
import type { AccessMatrix, Profile } from "../api/contracts";
import { ContextMenu } from "./ContextMenu";
import type { ContextMenuState } from "./ContextMenu";
import { ProfileAvatar } from "./ProfileAvatar";
import { DeleteProfileDrawer, ProfileFormDrawer } from "./ProfileDrawers";

type Drawer = { kind: "create" } | { kind: "edit"; profile: Profile } | { kind: "delete"; profile: Profile } | null;

const ROLE_CLASS: Record<string, string> = { admin: "profile-badge--info", contributor: "profile-badge--ok", reader: "profile-badge--reader" };

function scopeText(profile: Profile): string {
  if (profile.kind === "demo") return "Données fictives · sans mot de passe";
  if (profile.role === "admin") return `Voit tout · ${profile.totalAccounts ?? 0} compte(s) et ${profile.totalAssets ?? 0} bien(s) · gère les accès`;
  const base = `${profile.scopeAccounts ?? 0} sur ${profile.totalAccounts ?? 0} compte(s) · ${profile.scopeAssets ?? 0} sur ${profile.totalAssets ?? 0} bien(s)`;
  return profile.role === "reader" ? `${base} · consultation uniquement` : `${base} · peut modifier`;
}

/** Paramètres › Profils et accès : réservé à l'administrateur. */
export function AccessAdmin({ token, currentProfileId, onNotice, onChanged }: { token: string; currentProfileId: string; onNotice: (text: string) => void; onChanged: () => void }) {
  const [matrix, setMatrix] = useState<AccessMatrix | null>(null);
  const [demo, setDemo] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [menu, setMenu] = useState<ContextMenuState | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getAccessMatrix(token, controller.signal)
      .then((result) => { setMatrix(result); setError(""); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Lecture impossible."); });
    getAuthStatus(controller.signal).then((auth) => setDemo((auth.profiles ?? []).find((p) => p.kind === "demo") ?? null)).catch(() => undefined);
    return () => controller.abort();
  }, [token, refresh]);

  function done(text: string) {
    setDrawer(null);
    onNotice(text);
    setRefresh((n) => n + 1);
    onChanged();
  }

  function openMenu(event: MouseEvent, profile: Profile) {
    event.preventDefault();
    const isSelf = profile.id === currentProfileId;
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        ...(profile.kind === "demo" ? [] : [{ label: "Modifier le profil et l’accès…", onSelect: () => setDrawer({ kind: "edit", profile }) }]),
        { label: "Supprimer le profil…", danger: true, disabled: isSelf, hint: isSelf ? "Vous ne pouvez pas supprimer le profil ouvert." : undefined, onSelect: () => setDrawer({ kind: "delete", profile }) },
      ],
    });
  }

  const users = matrix?.users ?? [];
  const resources = matrix?.resources ?? [];
  const rows: Profile[] = [...users, ...(demo ? [demo] : [])];

  return (
    <article className="card settings-summary-card access-admin">
      <div className="panel-heading">
        <div><h2>Profils et accès</h2><p>Une base familiale commune. Chaque profil voit uniquement les comptes et biens qui lui sont ouverts.</p></div>
        <button className="settings-primary" onClick={() => setDrawer({ kind: "create" })} type="button">+ Nouveau profil</button>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <ul className="access-list">
        {rows.map((profile) => (
          <li key={profile.id} onContextMenu={(event) => openMenu(event, profile)}>
            <ProfileAvatar profile={profile} size={38} />
            <div><strong>{profile.name}{profile.id === currentProfileId ? " (vous)" : ""}</strong><small>{scopeText(profile)}</small></div>
            <span className={`profile-badge ${profile.kind === "demo" ? "profile-badge--info" : ROLE_CLASS[profile.role ?? "reader"]}`}>{profile.kind === "demo" ? "Démonstration" : profile.roleLabel}</span>
          </li>
        ))}
      </ul>
      {resources.length > 0 && users.length > 0 && (
        <div className="access-matrix-wrap">
          <h3>Qui voit quoi</h3>
          <table className="access-matrix">
            <thead><tr><th scope="col">Compte ou bien</th>{users.map((u) => <th key={u.id} scope="col">{u.name}</th>)}</tr></thead>
            <tbody>
              {resources.map((r) => (
                <tr key={`${r.type}:${r.id}`}>
                  <th scope="row">{r.name}<small>{r.type === "account" ? "Compte" : "Bien"}</small></th>
                  {users.map((u) => {
                    const sees = r.visibleTo.includes(u.id);
                    return <td aria-label={sees ? "Voit" : "Ne voit pas"} className={sees ? "is-on" : "is-off"} key={u.id}>{sees ? "●" : "○"}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <small>Clic droit sur un profil pour modifier son rôle et son accès. L’administrateur voit toujours tout.</small>
        </div>
      )}
      <p className="drawer-note">Ces restrictions contrôlent l’accès depuis l’application. Elles ne protègent pas contre quelqu’un qui ouvrirait directement le fichier de données sur cet ordinateur.</p>
      {createPortal(<>
      {drawer?.kind === "create" && (
        <ProfileFormDrawer hasDemo={demo !== null} mode="create" onClose={() => setDrawer(null)} onCreated={(profile) => done(`Profil « ${profile.name} » créé.`)} resources={resources} token={token} />
      )}
      {drawer?.kind === "edit" && (
        <ProfileFormDrawer mode="edit" onClose={() => setDrawer(null)} onSaved={(profile) => done(`Profil « ${profile.name} » mis à jour.`)} profile={drawer.profile} resources={resources} token={token} />
      )}
      {drawer?.kind === "delete" && (
        <DeleteProfileDrawer onClose={() => setDrawer(null)} onDeleted={() => done("Profil supprimé.")} profile={drawer.profile} token={token} />
      )}
      </>, document.body)}
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(null)} />}
    </article>
  );
}
