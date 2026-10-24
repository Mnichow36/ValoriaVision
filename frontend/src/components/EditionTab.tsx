import { useState } from "react";

import { setEdition } from "../api/client";
import { useEdition } from "../edition";

export function EditionTab({ token, isAdmin, onChanged }: { token: string; isAdmin: boolean; onChanged: () => void }) {
  const { edition } = useEdition();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (!edition) return <section className="loading-state"><span /><p>Lecture de l’édition…</p></section>;

  async function choose(code: "standard" | "premium") {
    if (!edition || busy || edition.code === code) return;
    setBusy(true);
    setError("");
    try {
      await setEdition(token, code);
      onChanged();
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "L’édition n’a pas pu être changée.");
    } finally {
      setBusy(false);
    }
  }

  const limit = edition.accountLimit;
  const usage = limit ? Math.min(100, Math.round((edition.activeAccounts / limit) * 100)) : 0;
  const over = limit !== null && edition.activeAccounts > limit;

  return (
    <div className="edition-grid">
      <article className="card settings-summary-card">
        <div className="panel-heading"><div><h2>Votre édition</h2><p>Édition en cours : <strong>{edition.label}</strong></p></div></div>
        <div aria-label="Édition" className="edition-switch" role="group">
          {(["standard", "premium"] as const).map((code) => (
            <button
              aria-pressed={edition.code === code}
              className={edition.code === code ? "is-active" : ""}
              disabled={!isAdmin || busy}
              key={code}
              onClick={() => void choose(code)}
              type="button"
            >{code === "standard" ? "Standard" : "Premium"}</button>
          ))}
        </div>
        <p className="edition-note">Mode d’essai local : ce commutateur change l’édition sur cet ordinateur uniquement. Aucun paiement n’est demandé, rien n’est envoyé.{!isAdmin && " Seul l’administrateur peut le modifier."}</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        <div className="edition-usage">
          <div className="edition-usage__row"><span>Comptes actifs</span><strong>{limit ? `${edition.activeAccounts} sur ${limit}` : `${edition.activeAccounts} (illimités)`}</strong></div>
          {limit !== null && <div aria-hidden="true" className="edition-meter"><div className={over ? "is-over" : ""} style={{ width: `${usage}%` }} /></div>}
          <p className="edition-note">Au-delà de {limit ?? 3}, vos comptes restent intacts : seule la création d’un nouveau compte est bloquée.</p>
        </div>
      </article>
      <article className="card settings-summary-card">
        <div className="panel-heading"><div><h2>Ce que comprend chaque édition</h2></div></div>
        <table className="edition-table">
          <thead><tr><th scope="col">Fonction</th><th scope="col">Standard</th><th scope="col">Premium</th></tr></thead>
          <tbody>
            {edition.catalogue.map((row) => (
              <tr key={row.key}><th scope="row">{row.label}</th><td>{row.standard}</td><td>{row.premium}</td></tr>
            ))}
          </tbody>
        </table>
      </article>
      <p className="edition-banner" role="note">Passer en Standard avec plus de {limit ?? 3} comptes ou plusieurs profils ne supprime rien : les éléments au-delà de la limite restent visibles, avec un cadenas Premium, et se réactivent en repassant Premium.</p>
    </div>
  );
}
