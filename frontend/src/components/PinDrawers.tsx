import { useState } from "react";
import type { FormEvent } from "react";

import { deletePin, removeProfilePin, savePin } from "../api/client";
import type { Profile } from "../api/contracts";
import { PIN_LENGTH } from "./PinPad";
import { SideDrawer } from "./SideDrawer";

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

function digitsOnly(value: string): string {
  return value.replace(/\D/g, "").slice(0, PIN_LENGTH);
}

/** Création ou changement du PIN du profil connecté. */
export function PinDrawer({ token, replacing, onClose, onDone }: { token: string; replacing: boolean; onClose: () => void; onDone: (notice: string) => void }) {
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pin.length !== PIN_LENGTH) return setError(`Le PIN doit contenir exactement ${PIN_LENGTH} chiffres.`);
    if (pin !== confirmation) return setError("Les deux PIN ne correspondent pas.");
    setBusy(true);
    setError("");
    try {
      await savePin(token, password, pin);
      onDone(replacing ? "PIN modifié." : "PIN créé.");
    } catch (reason: unknown) {
      setError(message(reason));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Sécurité" onClose={onClose} title={replacing ? "Changer mon code PIN" : "Créer mon code PIN"}
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-primary" disabled={busy || !password || pin.length !== PIN_LENGTH} form="pin-form" type="submit">{busy ? "Enregistrement…" : "Enregistrer le PIN"}</button></>}>
      <form className="drawer-form" id="pin-form" onSubmit={submit}>
        <p>Le PIN ne sert qu’à rouvrir votre profil après un verrouillage automatique. Il ne remplace pas votre mot de passe.</p>
        <label>Mot de passe du profil<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
        <label>Nouveau PIN ({PIN_LENGTH} chiffres)<input autoComplete="off" className="pin-input" inputMode="numeric" maxLength={PIN_LENGTH} onChange={(e) => setPin(digitsOnly(e.target.value))} type="password" value={pin} /></label>
        <label>Confirmer le PIN<input autoComplete="off" className="pin-input" inputMode="numeric" maxLength={PIN_LENGTH} onChange={(e) => setConfirmation(digitsOnly(e.target.value))} type="password" value={confirmation} /></label>
        <p className="drawer-note">Refusés : suites évidentes (123456, 654321) et chiffres répétés (111111, 000000).</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

/** Suppression du PIN du profil connecté (mot de passe exigé). */
export function DeletePinDrawer({ token, onClose, onDone }: { token: string; onClose: () => void; onDone: (notice: string) => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await deletePin(token, password);
      onDone("PIN supprimé.");
    } catch (reason: unknown) {
      setError(message(reason));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Sécurité" onClose={onClose} title="Supprimer mon code PIN"
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-danger" disabled={busy || !password} form="pin-delete-form" type="submit">{busy ? "Suppression…" : "Supprimer le PIN"}</button></>}>
      <form className="drawer-form" id="pin-delete-form" onSubmit={submit}>
        <p>Après la suppression, seul le mot de passe rouvrira votre profil. Vous pourrez recréer un PIN à tout moment.</p>
        <label>Mot de passe du profil<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}

/** Administrateur : retire le PIN d'un autre profil (oubli). Son mot de passe reste inchangé. */
export function RemoveProfilePinDrawer({ token, profile, onClose, onDone }: { token: string; profile: Profile; onClose: () => void; onDone: (notice: string) => void }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await removeProfilePin(token, profile.id, password);
      onDone(`PIN de « ${profile.name} » retiré.`);
    } catch (reason: unknown) {
      setError(message(reason));
      setBusy(false);
    }
  }

  return (
    <SideDrawer eyebrow="Profils et accès" onClose={onClose} title={`Retirer le PIN de ${profile.name}`}
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Annuler</button><button className="settings-danger" disabled={busy || !password} form="pin-remove-form" type="submit">{busy ? "Retrait…" : "Retirer le PIN"}</button></>}>
      <form className="drawer-form" id="pin-remove-form" onSubmit={submit}>
        <p>Le mot de passe de {profile.name} n’est pas modifié : il pourra se connecter avec et recréer un PIN.</p>
        <label>Votre mot de passe (administrateur)<input autoComplete="current-password" autoFocus onChange={(e) => setPassword(e.target.value)} type="password" value={password} /></label>
        {error && <p className="auth-error" role="alert">{error}</p>}
      </form>
    </SideDrawer>
  );
}
