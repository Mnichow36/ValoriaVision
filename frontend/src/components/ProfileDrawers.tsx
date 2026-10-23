import { useRef, useState } from "react";
import type { FormEvent } from "react";

import { createProfile, deleteProfile, setupAdministrator, updateProfile, updateProfileAccess } from "../api/client";
import type { AccessResource, Profile } from "../api/contracts";
import { PasswordStrengthMeter } from "./PasswordDrawers";
import { ProfileAvatar } from "./ProfileAvatar";
import { RecoveryKeyPanel } from "./RecoveryKeyPanel";
import { SideDrawer } from "./SideDrawer";
import { resizeToAvatar } from "./imageResize";
import { evaluatePassword } from "./passwordStrength";

export const PROFILE_COLORS = ["#2563eb", "#0f766e", "#7c3aed", "#b45309", "#be123c"];

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

type Role = "admin" | "contributor" | "reader";

const ROLE_OPTIONS: { id: Role; label: string; text: string }[] = [
  { id: "admin", label: "Administrateur", text: "Voit et modifie tout, gère les profils et les accès." },
  { id: "contributor", label: "Contributeur", text: "Consulte et modifie, uniquement dans son périmètre." },
  { id: "reader", label: "Lecteur", text: "Consultation uniquement, dans son périmètre." },
];

function ScopePicker({ resources, selected, onChange }: { resources: AccessResource[]; selected: Set<string>; onChange: (next: Set<string>) => void }) {
  const groups = [
    { type: "account" as const, title: "Comptes bancaires" },
    { type: "asset" as const, title: "Patrimoine" },
  ];
  const key = (r: AccessResource) => `${r.type}:${r.id}`;
  function toggle(keys: string[], on: boolean) {
    const next = new Set(selected);
    keys.forEach((k) => (on ? next.add(k) : next.delete(k)));
    onChange(next);
  }
  return (
    <div className="scope-picker">
      {groups.map((group) => {
        const items = resources.filter((r) => r.type === group.type);
        if (items.length === 0) return null;
        const keys = items.map(key);
        const all = keys.every((k) => selected.has(k));
        return (
          <div key={group.type}>
            <label className="scope-picker__group">
              <input checked={all} onChange={(e) => toggle(keys, e.target.checked)} type="checkbox" />
              <strong>{group.title}</strong>
            </label>
            {items.map((item) => (
              <label className="scope-picker__item" key={key(item)}>
                <input checked={selected.has(key(item))} onChange={(e) => toggle([key(item)], e.target.checked)} type="checkbox" />
                <span>{item.name}</span>
              </label>
            ))}
          </div>
        );
      })}
    </div>
  );
}

interface ProfileFormProps {
  /** Mode administrateur : rôle et périmètre modifiables (liste des comptes et biens). */
  resources?: AccessResource[];
  mode: "create" | "edit";
  profile?: Profile;
  hasDemo?: boolean;
  /** Première installation : crée l'administrateur de la base familiale (aucun jeton requis). */
  firstRun?: boolean;
  /** Jeton du profil ouvert (modification ou création par un administrateur). */
  token?: string;
  onClose: () => void;
  /** Modification enregistrée. */
  onSaved?: (profile: Profile) => void;
  /** Création terminée : l'interface ouvre le profil (mot de passe connu) ou rafraîchit la liste (Démo). */
  onCreated?: (profile: Profile, password: string) => void;
}

export function ProfileFormDrawer({ mode, profile, resources, hasDemo = false, firstRun = false, token, onClose, onSaved, onCreated }: ProfileFormProps) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(profile?.name ?? "");
  const [color, setColor] = useState(profile?.color ?? PROFILE_COLORS[1]);
  const [kind, setKind] = useState<"personal" | "demo">("personal");
  const adminMode = resources !== undefined && !firstRun;
  const [role, setRole] = useState<Role>(profile?.role ?? "contributor");
  const [scope, setScope] = useState<Set<string>>(() => new Set(
    (resources ?? []).filter((r) => profile && r.visibleTo.includes(profile.id)).map((r) => `${r.type}:${r.id}`),
  ));
  const [avatar, setAvatar] = useState<string | null>(profile?.avatar ?? null);
  const [avatarChanged, setAvatarChanged] = useState(false);
  const [avatarMode, setAvatarMode] = useState<"initials" | "photo">(profile?.avatar ? "photo" : "initials");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<{ profile: Profile; recoveryKey: string } | null>(null);
  const [keyConfirmed, setKeyConfirmed] = useState(false);

  const isDemo = mode === "create" && kind === "demo";
  const preview = { name: name || "?", color, avatar: avatarMode === "photo" ? avatar : null };

  async function pickFile(file: File | undefined) {
    if (!file) return;
    try {
      setAvatar(await resizeToAvatar(file));
      setAvatarChanged(true);
      setError("");
    } catch (reason: unknown) {
      setError(message(reason));
    }
  }

  function chooseMode(next: "initials" | "photo") {
    setAvatarMode(next);
    if (next === "initials" && avatar) {
      setAvatar(null);
      setAvatarChanged(true);
    }
  }

  function scopePayload() {
    const ids = (type: string) => [...scope].filter((k) => k.startsWith(`${type}:`)).map((k) => Number(k.split(":")[1]));
    return { accounts: ids("account"), assets: ids("asset") };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!name.trim()) return setError("Le nom du profil est obligatoire.");
    if (mode === "create" && !isDemo) {
      if (password !== confirmation) return setError("Les deux mots de passe ne correspondent pas.");
      const strength = evaluatePassword(password);
      if (!strength.acceptable) return setError(strength.hint || "Mot de passe trop faible.");
    }
    setBusy(true);
    try {
      if (mode === "edit" && profile && token) {
        const result = await updateProfile(token, profile.id, {
          name,
          color,
          ...(adminMode && role !== profile.role ? { role } : {}),
          ...(avatarChanged ? (avatar ? { avatar } : { clear_avatar: true }) : {}),
        });
        if (adminMode && role !== "admin") await updateProfileAccess(token, profile.id, scopePayload());
        onSaved?.(result.profile);
        return;
      }
      if (firstRun) {
        const result = await setupAdministrator(name.trim(), password);
        const firstProfile: Profile = {
          id: result.profileId ?? "u1", name: name.trim(), color, kind: "personal", avatar: null, lastLoginAt: null,
          configured: true, recoveryKeyConfigured: true, removable: false, role: "admin", roleLabel: "Administrateur",
        };
        setCreated({ profile: firstProfile, recoveryKey: result.recoveryKey });
        return;
      }
      if (!token) throw new Error("Ouvrez d’abord votre session.");
      const result = await createProfile(token, {
        name,
        color,
        kind,
        ...(isDemo ? {} : { password, role, ...scopePayload() }),
        ...(avatar && avatarMode === "photo" ? { avatar } : {}),
      });
      if (result.recoveryKey) setCreated({ profile: result.profile, recoveryKey: result.recoveryKey });
      else onCreated?.(result.profile, "");
    } catch (reason: unknown) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return (
      <SideDrawer eyebrow="Profils" onClose={() => undefined} title="Profil créé"
        footer={<button className="settings-primary" disabled={!keyConfirmed} onClick={() => onCreated?.(created.profile, password)} type="button">{adminMode ? "Terminé" : "Ouvrir mon espace"}</button>}>
        <p><strong>{created.profile.name}</strong> est prêt. Voici sa clé de secours, indispensable si le mot de passe est oublié{adminMode ? " : remettez-la à cette personne, elle ne sera plus affichée." : "."}</p>
        <RecoveryKeyPanel onConfirmedChange={setKeyConfirmed} recoveryKey={created.recoveryKey} />
      </SideDrawer>
    );
  }

  return (
    <SideDrawer eyebrow="Profils" onClose={onClose} title={mode === "create" ? (firstRun ? "Créer l’administrateur" : "Nouveau profil") : adminMode ? "Profil et accès" : "Modifier le profil"}
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy} form="profile-form" type="submit">{busy ? "Enregistrement…" : mode === "create" ? "Créer le profil" : "Enregistrer"}</button></>}>
      <form className="drawer-form" id="profile-form" onSubmit={submit}>
        <label>Nom du profil<input autoFocus maxLength={40} onChange={(e) => setName(e.target.value)} value={name} /></label>

        <div className="drawer-form__label">Avatar</div>
        <div className="avatar-mode" role="group" aria-label="Type d’avatar">
          <button aria-pressed={avatarMode === "initials"} onClick={() => chooseMode("initials")} type="button">Initiales</button>
          <button aria-pressed={avatarMode === "photo"} onClick={() => chooseMode("photo")} type="button">Photo ou image</button>
        </div>
        <div className="avatar-editor">
          <ProfileAvatar profile={preview} size={84} />
          {avatarMode === "photo" ? (
            <div className="avatar-editor__side">
              <div className="avatar-editor__buttons">
                <button className="settings-secondary" onClick={() => fileInput.current?.click()} type="button">Choisir une image…</button>
                {avatar && <button className="avatar-editor__remove" onClick={() => { setAvatar(null); setAvatarChanged(true); }} type="button">Retirer</button>}
              </div>
              <small>JPG, PNG ou WebP · recadrée en rond et réduite à 256 px · reste sur cet ordinateur.</small>
              <input accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => { void pickFile(e.target.files?.[0]); e.target.value = ""; }} ref={fileInput} type="file" />
            </div>
          ) : <small>L’avatar reprend l’initiale du nom et la couleur choisie.</small>}
        </div>

        <div className="drawer-form__label">Couleur (sans photo)</div>
        <div className="color-swatches" role="radiogroup" aria-label="Couleur">
          {PROFILE_COLORS.map((item) => (
            <button aria-checked={color === item} aria-label={item} className={color === item ? "is-selected" : ""} key={item} onClick={() => setColor(item)} role="radio" style={{ background: item }} type="button" />
          ))}
        </div>

        {adminMode && mode === "edit" && (
          <>
            <div className="drawer-form__label">Rôle</div>
            <div className="role-options" role="radiogroup" aria-label="Rôle">
              {ROLE_OPTIONS.map((option) => (
                <button aria-checked={role === option.id} key={option.id} onClick={() => setRole(option.id)} role="radio" type="button">
                  <strong>{option.label}</strong><span>{option.text}</span>
                </button>
              ))}
            </div>
            <div className="drawer-form__label">Périmètre : ce que ce profil peut voir</div>
            {role === "admin"
              ? <p className="drawer-note">Un administrateur voit toujours tous les comptes et tous les biens.</p>
              : <ScopePicker onChange={setScope} resources={resources ?? []} selected={scope} />}
          </>
        )}

        {mode === "create" && (
          <>
            {firstRun
              ? <p className="drawer-note">Ce premier profil est l’<strong>administrateur</strong> : il voit tout et crée ensuite les profils de la famille avec leurs accès.</p>
              : <div className="drawer-form__label">Type de profil</div>}
            {!firstRun && (
            <div className="kind-options">
              <button aria-pressed={kind === "personal"} onClick={() => setKind("personal")} type="button"><strong>Personnel</strong><span>Accès à la base familiale, mot de passe obligatoire.</span></button>
              <button aria-pressed={kind === "demo"} disabled={hasDemo} onClick={() => setKind("demo")} title={hasDemo ? "Un profil Démo existe déjà." : undefined} type="button"><strong>Démo</strong><span>{hasDemo ? "Déjà créé." : "Données fictives, sans mot de passe."}</span></button>
            </div>
            )}
                    {adminMode && !isDemo && (
              <>
                <div className="drawer-form__label">Rôle</div>
                <div className="role-options" role="radiogroup" aria-label="Rôle">
                  {ROLE_OPTIONS.map((option) => (
                    <button aria-checked={role === option.id} key={option.id} onClick={() => setRole(option.id)} role="radio" type="button">
                      <strong>{option.label}</strong><span>{option.text}</span>
                    </button>
                  ))}
                </div>
                <div className="drawer-form__label">Périmètre : ce que ce profil peut voir</div>
                {role === "admin"
                  ? <p className="drawer-note">Un administrateur voit toujours tous les comptes et tous les biens.</p>
                  : <ScopePicker onChange={setScope} resources={resources ?? []} selected={scope} />}
              </>
            )}
            {!isDemo && (
              <>
                <label>Mot de passe du profil<input autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
                <PasswordStrengthMeter password={password} />
                <label>Confirmer le mot de passe<input autoComplete="new-password" onChange={(e) => setConfirmation(e.target.value)} type="password" value={confirmation} /></label>
                <p className="drawer-note">Une <strong>clé de secours</strong> vous sera montrée juste après la création. Sans mot de passe ni clé, ce profil est irrécupérable.</p>
              </>
            )}
          </>
        )}
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

export function DeleteProfileDrawer({ profile, token, onClose, onDeleted }: { profile: Profile; token: string; onClose: () => void; onDeleted: () => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const needsPassword = true;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await deleteProfile(token, profile.id, password);
      onDeleted();
    } catch (reason: unknown) {
      setError(message(reason));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Profils" onClose={onClose} title="Supprimer le profil"
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-danger" disabled={busy || (needsPassword && !password)} form="delete-profile-form" type="submit">{busy ? "Suppression…" : "Supprimer définitivement"}</button></>}>
      <form className="drawer-form" id="delete-profile-form" onSubmit={submit}>
        <div className="delete-profile-who"><ProfileAvatar profile={profile} size={56} /><strong>{profile.name}</strong></div>
        <p className="security-warning-note">{profile.kind === "demo"
          ? <>Les données fictives du profil Démo seront <strong>effacées</strong>.</>
          : <>Ce profil n’aura plus accès à Valoria. Les comptes, transactions et le patrimoine de la base familiale <strong>ne sont pas touchés</strong>.</>}</p>
        {needsPassword && (
          <label>Votre mot de passe d’administrateur<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
        )}
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}
