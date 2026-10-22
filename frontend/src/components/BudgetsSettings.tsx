import type { MouseEvent } from "react";

import type { BudgetsSnapshot } from "../api/contracts";
import { formatMoney } from "./budgetFormat";

interface BudgetsSettingsProps {
  onEdit: (category: string | null) => void;
  onMenu: (event: MouseEvent, category: string) => void;
  onRules: () => void;
  onToggle: (category: string, active: boolean) => void;
  snapshot: BudgetsSnapshot;
}

/** Onglet 3 : paramétrage des catégories budgétées et des règles générales. */
export function BudgetsSettings({ onEdit, onMenu, onRules, onToggle, snapshot }: BudgetsSettingsProps) {
  const { settings } = snapshot;
  return (
    <div className="bgt-tab bgt-settings">
      <article className="bgt-card bgt-table-card">
        <div className="bgt-card__heading">
          <div><h2>Catégories budgétées</h2><span>Clic sur une ligne : ouvrir le volet de réglage. Clic droit : activer, réviser, retirer.</span></div>
          <button className="bgt-primary" onClick={() => onEdit(null)} type="button">+ Ajouter une catégorie</button>
        </div>
        <div className="bgt-row bgt-row--set bgt-row--head">
          <span>Catégorie</span><span className="is-num">Budget / mois</span><span>Mode</span><span className="is-num">Seuil d’alerte</span><span>Dernière révision</span><span>Actif</span>
        </div>
        <div className="bgt-rows">
          {settings.categories.length === 0 && <p className="bgt-empty">Aucune catégorie budgétée : ajoute-en une pour démarrer.</p>}
          {settings.categories.map((row) => (
            <div
              className={`bgt-row bgt-row--set bgt-row--body${row.active ? "" : " is-off"}`}
              key={row.category}
              onClick={() => onEdit(row.category)}
              onContextMenu={(event) => onMenu(event, row.category)}
              onKeyDown={(event) => { if (event.key === "Enter") onEdit(row.category); }}
              role="button"
              tabIndex={0}
            >
              <strong>{row.category}</strong>
              <span className="is-num"><b>{row.active || row.amount > 0 ? formatMoney(row.amount) : "–"}</b></span>
              <span className="bgt-pill">{row.mode}</span>
              <span className="is-num">{Math.round(row.alertThreshold)} %</span>
              <span className="bgt-muted">{row.lastRevision ?? "Jamais"}</span>
              <button
                aria-checked={row.active}
                aria-label={`${row.category} : ${row.active ? "actif" : "inactif"}`}
                className={row.active ? "bgt-switch is-on" : "bgt-switch"}
                onClick={(event) => { event.stopPropagation(); onToggle(row.category, !row.active); }}
                role="switch"
                type="button"
              ><i /></button>
            </div>
          ))}
        </div>
      </article>

      <aside className="bgt-side">
        <article className="bgt-card bgt-rules">
          <div className="bgt-card__heading"><h2>Règles générales</h2><button className="bgt-ghost" onClick={onRules} type="button">Modifier</button></div>
          <dl>
            <div><dt>Seuil d’alerte par défaut</dt><dd>{Math.round(settings.defaultAlertThreshold)} %</dd></div>
            <div><dt>Reconduction mensuelle</dt><dd>Automatique</dd></div>
            <div><dt>Début de l’exercice</dt><dd>Janvier</dd></div>
            <div><dt>Épargne et remboursements de prêt</dt><dd>Comptés en dépenses</dd></div>
            <div><dt>Exclus du suivi</dt><dd>Transferts, Investissement</dd></div>
            <div><dt>Comptes archivés</dt><dd>Exclus</dd></div>
          </dl>
          <p className="bgt-note">Seul le seuil par défaut est modifiable : les autres règles sont celles du moteur de calcul.</p>
        </article>
        <article className="bgt-modes">
          <b>Les modes</b>
          <span><strong>Fixe</strong> : même montant chaque mois.</span>
          <span><strong>Annuel réparti</strong> : montant annuel divisé par 12.</span>
          <span><strong>Saisonnier</strong> : montant propre à chaque mois (réviser « ce mois seulement »).</span>
        </article>
      </aside>
    </div>
  );
}
