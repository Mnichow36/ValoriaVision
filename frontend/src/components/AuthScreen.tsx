import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { evaluatePassword, MIN_PASSWORD_LENGTH } from "./passwordStrength";

interface AuthScreenProps {
  configured: boolean;
  busy: boolean;
  error?: string;
  retryAfter?: number;
  onSubmit: (password: string) => Promise<void>;
}

export function AuthScreen({ configured, busy, error, retryAfter, onSubmit }: AuthScreenProps) {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [localError, setLocalError] = useState("");
  const [wait, setWait] = useState(retryAfter ?? 0);
  const strength = evaluatePassword(password);

  useEffect(() => { setWait(retryAfter ?? 0); }, [retryAfter, error]);
  useEffect(() => {
    if (wait <= 0) return;
    const timer = window.setTimeout(() => setWait((value) => Math.max(0, value - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [wait]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!configured && password !== confirmation) {
      setLocalError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    if (!configured && !strength.acceptable) {
      setLocalError(strength.hint || "Mot de passe trop faible.");
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
            minLength={configured ? 1 : MIN_PASSWORD_LENGTH}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            value={password}
          />
          {!configured && password && (
            <div className="password-strength" data-score={strength.score}>
              <div className="password-strength__bar" aria-hidden="true"><i /><i /><i /><i /></div>
              <small>{strength.acceptable ? `Force : ${strength.label}` : strength.hint}</small>
            </div>
          )}
          {!configured && (
            <>
              <label htmlFor="master-password-confirmation">Confirmer le mot de passe</label>
              <input
                autoComplete="new-password"
                id="master-password-confirmation"
                minLength={MIN_PASSWORD_LENGTH}
                onChange={(event) => setConfirmation(event.target.value)}
                required
                type="password"
                value={confirmation}
              />
            </>
          )}
          {(localError || error) && <p className="auth-error" role="alert">{localError || error}</p>}
          {wait > 0 && !(localError || error) && <p className="auth-error" role="status">Nouvel essai possible dans {wait} s.</p>}
          <button disabled={busy || wait > 0} type="submit">
            {busy ? "Vérification…" : wait > 0 ? `Patientez ${wait} s` : configured ? "Déverrouiller" : "Créer et continuer"}
          </button>
        </form>
        <small>Session temporaire · aucune conservation du mot de passe dans l’interface</small>
      </section>
    </main>
  );
}
