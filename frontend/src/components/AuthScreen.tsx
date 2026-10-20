import { useState } from "react";
import type { FormEvent } from "react";

interface AuthScreenProps {
  configured: boolean;
  busy: boolean;
  error?: string;
  onSubmit: (password: string) => Promise<void>;
}

export function AuthScreen({ configured, busy, error, onSubmit }: AuthScreenProps) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [localError, setLocalError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configured && password !== confirmation) {
      setLocalError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setLocalError("");
    await onSubmit(password);
  }

  return (
    <main className="auth-shell">
      <section className="auth-card">
        <div className="auth-brand"><span>V</span><strong>Valoria Vision</strong></div>
        <p className="eyebrow">Données financières locales</p>
        <h1>{configured ? "Déverrouiller votre espace" : "Protéger votre espace"}</h1>
        <p className="auth-intro">
          {configured
            ? "Saisissez votre mot de passe maître. Il ne quitte jamais cet ordinateur."
            : "Créez le mot de passe maître qui protégera l’accès à vos données locales."}
        </p>
        <form onSubmit={submit}>
          <label htmlFor="master-password">Mot de passe maître</label>
          <input
            autoComplete={configured ? "current-password" : "new-password"}
            autoFocus
            id="master-password"
            minLength={8}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {!configured && (
            <>
              <label htmlFor="master-password-confirmation">Confirmer le mot de passe</label>
              <input
                autoComplete="new-password"
                id="master-password-confirmation"
                minLength={8}
                onChange={(event) => setConfirmation(event.target.value)}
                required
                type="password"
                value={confirmation}
              />
            </>
          )}
          {(localError || error) && <p className="auth-error" role="alert">{localError || error}</p>}
          <button disabled={busy} type="submit">
            {busy ? "Vérification…" : configured ? "Déverrouiller" : "Créer et continuer"}
          </button>
        </form>
        <small>Session temporaire · aucune conservation du mot de passe dans l’interface</small>
      </section>
    </main>
  );
}
