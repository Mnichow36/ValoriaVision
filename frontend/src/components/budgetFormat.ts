const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
const moneyExact = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });

export const MONTH_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

export function formatMoney(value: number): string {
  return money.format(value);
}

export function formatMoneyExact(value: number): string {
  return moneyExact.format(value);
}

export function signedMoney(value: number): string {
  if (Math.round(value) === 0) return formatMoney(0);
  return `${value > 0 ? "+ " : "- "}${formatMoney(Math.abs(value))}`;
}

export function monthLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  const label = new Intl.DateTimeFormat("fr-FR", { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
  return label.charAt(0).toUpperCase() + label.slice(1);
}

export function monthShortLabel(value: string): string {
  const [year, month] = value.split("-").map(Number);
  if (!year || !month) return value;
  return `${MONTH_SHORT[month - 1]} ${year}`;
}

export function parseAmount(text: string): number {
  return Number(text.replace(/\s/g, "").replace(",", "."));
}

export type BudgetDrawerState =
  | { kind: "revise"; category: string }
  | { kind: "category"; category: string | null }
  | { kind: "rules" };
