import { useEffect, useState } from "react";

import { getForecast } from "../api/client";
import type { ForecastSnapshot, RecurrenceActionResult, TransactionRow } from "../api/contracts";
import { RecurrenceEditor } from "./RecurrenceEditor";
import { nextMonthlyDate } from "./recurrenceKinds";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code" });
const dateFormat = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

/** Volet « Créer une récurrence » prérempli à partir d'une opération du journal. */
export function RecurrenceFromTransaction({ onClose, onCompleted, token, transaction }: {
  onClose: () => void;
  onCompleted: (result: RecurrenceActionResult) => void;
  token: string;
  transaction: TransactionRow;
}) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    getForecast(token, { accountId: "all", horizonDays: 30, scenario: "Réaliste" }, controller.signal)
      .then(setSnapshot)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Les comptes et catégories ne peuvent pas être chargés.");
      });
    return () => controller.abort();
  }, [token]);

  if (!snapshot) {
    return (
      <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
        <aside aria-label="Créer une récurrence" className="account-editor recurrence-editor" role="dialog">
          <header><div><span className="eyebrow">Récurrences</span><h2>Créer une récurrence</h2></div><button aria-label="Fermer" onClick={onClose} type="button">×</button></header>
          {error ? <p className="account-form-error" role="alert">{error}</p> : <p className="drawer-help">Chargement…</p>}
        </aside>
      </div>
    );
  }

  const direction = transaction.amount >= 0 ? "Crédit" : "Débit";
  const knownCategory = snapshot.categories.some((category) => category.name === transaction.category);
  return (
    <RecurrenceEditor
      accounts={snapshot.accounts}
      categories={snapshot.categories}
      defaultAccountId={String(transaction.accountId)}
      defaultScenario="Réaliste"
      initial={{
        accountId: transaction.accountId,
        name: transaction.beneficiary || transaction.label,
        direction,
        amount: Math.abs(transaction.amount),
        ...(knownCategory ? { category: transaction.category } : {}),
        frequency: "Mensuel",
        nextDate: nextMonthlyDate(transaction.date),
      }}
      onClose={onClose}
      onCompleted={onCompleted}
      sourceNote={<>D’après l’opération du <b>{dateFormat.format(new Date(`${transaction.date}T12:00:00`))}</b> · <b>{transaction.beneficiary || transaction.label}</b> · <b className={transaction.amount < 0 ? "negative" : "positive"}>{transaction.amount < 0 ? "− " : "+ "}{money.format(Math.abs(transaction.amount))}</b></>}
      token={token}
    />
  );
}
