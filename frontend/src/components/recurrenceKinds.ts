import type { RecurrenceItem, RecurrencePayload } from "../api/contracts";

export type RecurrenceKind = NonNullable<RecurrencePayload["kind"]>;

export const recurrenceKinds: Array<{ id: RecurrenceKind; label: string; plural: string; help: string }> = [
  { id: "Abonnement", label: "Abonnement", plural: "Abonnements", help: "Service résiliable : téléphone, streaming, salle de sport…" },
  { id: "Charge fixe", label: "Charge fixe", plural: "Charges fixes", help: "Loyer, assurance, crédit, impôts, énergie…" },
  { id: "Revenu", label: "Revenu", plural: "Revenus", help: "Salaire, pension, loyer perçu…" },
  { id: "Autre", label: "Autre", plural: "Autres", help: "Tout ce qui revient sans entrer ailleurs." },
];

const FIXED_COST_CATEGORIES = new Set(["Logement", "Assurances", "Impôts", "Énergie", "Santé"]);

/** Type proposé par défaut ; l'utilisateur garde la main. */
export function suggestKind(direction: RecurrencePayload["direction"], category: string): RecurrenceKind {
  if (direction === "Crédit") return "Revenu";
  return FIXED_COST_CATEGORIES.has(category) ? "Charge fixe" : "Abonnement";
}

export function kindLabel(kind: string | undefined): string {
  return recurrenceKinds.find((item) => item.id === kind)?.label ?? "Autre";
}

/** Montant ramené à un mois (annuel ÷ 12, trimestriel ÷ 3, hebdomadaire × 52 ÷ 12). Ponctuel : 0. */
export function monthlyAmount(item: Pick<RecurrenceItem, "amount" | "frequency">): number {
  switch (item.frequency) {
    case "Mensuel": return item.amount;
    case "Trimestriel": return item.amount / 3;
    case "Annuel": return item.amount / 12;
    case "Hebdomadaire": return (item.amount * 52) / 12;
    default: return 0;
  }
}

function isoLocal(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Prochaine échéance mensuelle d'une opération passée : même jour du mois, jamais avant aujourd'hui. */
export function nextMonthlyDate(transactionDate: string, now: Date = new Date()): string {
  const base = new Date(`${transactionDate}T12:00:00`);
  if (Number.isNaN(base.getTime())) return isoLocal(now);
  const day = base.getDate();
  const todayIso = isoLocal(now);
  let months = 1;
  for (;;) {
    const candidate = new Date(base.getFullYear(), base.getMonth() + months, 1, 12);
    const lastDay = new Date(candidate.getFullYear(), candidate.getMonth() + 1, 0).getDate();
    candidate.setDate(Math.min(day, lastDay));
    if (isoLocal(candidate) >= todayIso) return isoLocal(candidate);
    months += 1;
    if (months > 600) return todayIso;
  }
}
