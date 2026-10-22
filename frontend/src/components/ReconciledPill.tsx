import type { ReconciliationBadge } from "../api/contracts";

/** Pastille « Rapprochée » : visible sur toute opération liée à une prévision ou une récurrence. */
export function ReconciledPill({ badge }: { badge?: ReconciliationBadge }) {
  if (!badge?.reconciled) return null;
  const mode = badge.matchType === "manual" || badge.matchType === "manual_overage" ? "manuellement" : "automatiquement";
  const title = badge.label
    ? `Rapprochée ${mode} avec « ${badge.label} »`
    : `Rapprochée ${mode} avec une prévision`;
  return <span className="reconciled-pill" title={title}>Rapprochée</span>;
}
