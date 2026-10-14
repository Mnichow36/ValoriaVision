import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getReconciliation } from "../api/client";
import type {
  ReconciliationAccount,
  ReconciliationOccurrence,
  ReconciliationSnapshot,
  ReconciliationSuggestion,
  ReconciliationTransaction,
} from "../api/contracts";

interface ReconciliationPageProps {
  accountId: string;
  onAccountsChange: (accounts: ReconciliationAccount[]) => void;
  refreshKey: number;
  status: string;
  token: string;
}

const money = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 2,
});

const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "short" });

export function ReconciliationPage({ accountId, onAccountsChange, refreshKey, status, token }: ReconciliationPageProps) {
  const [snapshot, setSnapshot] = useState<ReconciliationSnapshot>();
  const [selectedTransactionId, setSelectedTransactionId] = useState<number>();
  const [selectedOccurrenceId, setSelectedOccurrenceId] = useState<number>();
  const [error, setError] = useState<string>();
  const [localRefreshKey, setLocalRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getReconciliation(token, { accountId, status }, controller.signal)
      .then((data) => {
        setSnapshot(data);
        onAccountsChange(data.accounts);
        const transactionId = data.transactions.some((row) => row.id === selectedTransactionId)
          ? selectedTransactionId
          : data.transactions[0]?.id;
        const suggestion = data.suggestions.find((row) => row.transactionId === transactionId);
        setSelectedTransactionId(transactionId);
        setSelectedOccurrenceId((current) => data.occurrences.some((row) => row.id === current)
          ? current
          : suggestion?.occurrenceId ?? data.occurrences[0]?.id);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les rapprochements ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [accountId, localRefreshKey, onAccountsChange, refreshKey, status, token]);

  const selectedTransaction = snapshot?.transactions.find((row) => row.id === selectedTransactionId);
  const suggestedMatch = useMemo(
    () => snapshot?.suggestions.find((row) => row.transactionId === selectedTransactionId),
    [selectedTransactionId, snapshot],
  );
  const selectedOccurrence = snapshot?.occurrences.find((row) => row.id === (suggestedMatch?.occurrenceId ?? selectedOccurrenceId));

  function selectTransaction(transaction: ReconciliationTransaction) {
    setSelectedTransactionId(transaction.id);
    const suggestion = snapshot?.suggestions.find((row) => row.transactionId === transaction.id);
    if (suggestion) setSelectedOccurrenceId(suggestion.occurrenceId);
  }

  if (error) {
    return (
      <section className="error-state">
        <strong>Les rapprochements ne peuvent pas être affichés.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setLocalRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Analyse des correspondances par le moteur Python…</div>;
  }

  return (
    <div className="reconciliation-page">
      <section className="reconciliation-kpis" aria-label="Indicateurs de rapprochement">
        <ReconciliationKpi detail="Issues des imports et saisies" label="Transactions non rapprochées" tone="blue" value={snapshot.summary.unmatchedTransactions} />
        <ReconciliationKpi detail={`${snapshot.summary.toReview} à vérifier · ${snapshot.summary.partial} partielles`} label="Prévisions ouvertes" tone="cyan" value={snapshot.summary.openOccurrences} />
        <ReconciliationKpi detail={`Score moyen ${snapshot.summary.averageScore} %`} label="Propositions auto" tone="purple" value={snapshot.summary.automaticProposals} />
        <ReconciliationKpi detail="Automatiques + manuelles" label="Rapprochées" tone="green" value={snapshot.summary.matched} />
      </section>

      <section className="reconciliation-workbench">
        <QueuePanel count={snapshot.transactions.length} subtitle="Transactions compatibles avec au moins une prévision." title="Transactions à rapprocher">
          {snapshot.transactions.length > 0 ? snapshot.transactions.map((transaction) => (
            <TransactionCard
              key={transaction.id}
              onSelect={() => selectTransaction(transaction)}
              selected={transaction.id === selectedTransactionId}
              transaction={transaction}
            />
          )) : <EmptyQueue text="Aucune transaction à rapprocher pour ce filtre." />}
        </QueuePanel>

        <QueuePanel count={snapshot.occurrences.length} subtitle="Récurrences et opérations ponctuelles ouvertes." title="Prévisions à traiter">
          {snapshot.occurrences.length > 0 ? snapshot.occurrences.map((occurrence) => (
            <OccurrenceCard
              key={occurrence.id}
              occurrence={occurrence}
              onSelect={() => setSelectedOccurrenceId(occurrence.id)}
              selected={occurrence.id === selectedOccurrence?.id}
            />
          )) : <EmptyQueue text="Aucune prévision ouverte pour ce filtre." />}
        </QueuePanel>

        <ProposalPanel
          occurrence={selectedOccurrence}
          rules={snapshot.rules}
          suggestion={suggestedMatch}
          transaction={selectedTransaction}
        />
      </section>
    </div>
  );
}

function ReconciliationKpi({ detail, label, tone, value }: { detail: string; label: string; tone: string; value: number }) {
  return (
    <article className="card reconciliation-kpi">
      <div><span>{label}</span><i className={`reconciliation-kpi__mark reconciliation-kpi__mark--${tone}`} /></div>
      <strong>{value.toLocaleString("fr-FR")}</strong>
      <small>{detail}</small>
    </article>
  );
}

function QueuePanel({ children, count, subtitle, title }: { children: ReactNode; count: number; subtitle: string; title: string }) {
  return (
    <article className="card reconciliation-queue">
      <div className="reconciliation-heading">
        <div><h2>{title}</h2><p>{subtitle}</p></div>
        <span>{count}</span>
      </div>
      <div className="reconciliation-queue__list">{children}</div>
    </article>
  );
}

function TransactionCard({ onSelect, selected, transaction }: { onSelect: () => void; selected: boolean; transaction: ReconciliationTransaction }) {
  return (
    <button aria-pressed={selected} className={selected ? "reconciliation-item reconciliation-item--selected" : "reconciliation-item"} onClick={onSelect} type="button">
      <div className="reconciliation-item__top"><strong>{transaction.label}</strong><b className={transaction.amount >= 0 ? "positive" : "negative"}>{signedMoney(transaction.amount)}</b></div>
      <div className="reconciliation-item__meta"><span>{formatDate(transaction.date)}</span><span>{transaction.accountName}</span></div>
      <div className="reconciliation-item__footer"><span className="transaction-pill transaction-pill--muted">{transaction.category}</span><small>{transaction.remainingAmount < Math.abs(transaction.amount) ? `${money.format(transaction.remainingAmount)} disponibles` : "Non rapprochée"}</small></div>
    </button>
  );
}

function OccurrenceCard({ occurrence, onSelect, selected }: { occurrence: ReconciliationOccurrence; onSelect: () => void; selected: boolean }) {
  return (
    <button aria-pressed={selected} className={selected ? "reconciliation-item reconciliation-item--selected" : "reconciliation-item"} onClick={onSelect} type="button">
      <div className="reconciliation-item__top"><strong>{occurrence.label}</strong><b className={occurrence.amount >= 0 ? "positive" : "negative"}>{signedMoney(occurrence.amount)}</b></div>
      <div className="reconciliation-item__meta"><span>{formatDate(occurrence.date)}</span><span>{occurrence.accountName}</span></div>
      <div className="reconciliation-item__footer"><span className={`reconciliation-status reconciliation-status--${statusTone(occurrence.status)}`}>{occurrence.statusLabel}</span><small>{money.format(occurrence.remainingAmount)} restants</small></div>
    </button>
  );
}

function ProposalPanel({ occurrence, rules, suggestion, transaction }: {
  occurrence?: ReconciliationOccurrence;
  rules: ReconciliationSnapshot["rules"];
  suggestion?: ReconciliationSuggestion;
  transaction?: ReconciliationTransaction;
}) {
  if (!transaction) {
    return (
      <aside className="card reconciliation-proposal">
        <div className="reconciliation-heading"><div><h2>Proposition de rapprochement</h2><p>Sélectionnez une transaction pour analyser la meilleure correspondance.</p></div></div>
        <EmptyQueue text="Aucune transaction sélectionnée." />
      </aside>
    );
  }

  if (!suggestion || !occurrence) {
    return (
      <aside className="card reconciliation-proposal">
        <div className="reconciliation-heading"><div><h2>Proposition de rapprochement</h2><p>Aucune correspondance éligible.</p></div></div>
        <SelectionSummary label="Transaction" name={transaction.label} amount={transaction.amount} />
        <p className="reconciliation-proposal__empty">Le moteur ne trouve pas de prévision dans les tolérances actives.</p>
      </aside>
    );
  }

  const dateDifference = Math.abs((new Date(transaction.date).getTime() - new Date(occurrence.date).getTime()) / 86_400_000);
  return (
    <aside className="card reconciliation-proposal">
      <div className="reconciliation-heading"><div><h2>Proposition de rapprochement</h2><p>Meilleure correspondance expliquée par le moteur.</p></div></div>
      <SelectionSummary label="Transaction réelle" name={transaction.label} amount={transaction.amount} />
      <div className="reconciliation-link" aria-hidden="true"><span /><b>↕</b><span /></div>
      <SelectionSummary label="Prévision attendue" name={occurrence.label} amount={occurrence.amount} />
      <div className="reconciliation-score">
        <div><span>Score de confiance</span><strong>{suggestion.score} %</strong></div>
        <div className="reconciliation-score__track"><span style={{ width: `${Math.max(0, Math.min(100, suggestion.score))}%` }} /></div>
        <small>{decisionLabel(suggestion.decision, rules)}</small>
      </div>
      <dl className="reconciliation-criteria">
        <div><dt>Écart de montant</dt><dd>{money.format(suggestion.amountDifference)}</dd></div>
        <div><dt>Écart de date</dt><dd>{Math.round(dateDifference)} jour(s)</dd></div>
        <div><dt>Critères</dt><dd>{suggestion.reason}</dd></div>
      </dl>
      <div className="reconciliation-actions">
        <button disabled title="Le rejet sécurisé sera raccordé dans l’incrément d’écriture" type="button">Ignorer</button>
        <button disabled title="L’allocation manuelle sera raccordée dans l’incrément d’écriture" type="button">Mode manuel</button>
        <button className="reconciliation-actions__primary" disabled title="La validation sécurisée sera raccordée dans l’incrément d’écriture" type="button">Valider le rapprochement</button>
      </div>
      <p className="reconciliation-readonly-note">Consultation active · les actions d’écriture restent verrouillées dans ce premier raccordement.</p>
    </aside>
  );
}

function SelectionSummary({ amount, label, name }: { amount: number; label: string; name: string }) {
  return (
    <div className="reconciliation-selection">
      <span>{label}</span>
      <div><strong>{name}</strong><b className={amount >= 0 ? "positive" : "negative"}>{signedMoney(amount)}</b></div>
    </div>
  );
}

function EmptyQueue({ text }: { text: string }) {
  return <p className="reconciliation-empty">{text}</p>;
}

function decisionLabel(decision: ReconciliationSuggestion["decision"], rules: ReconciliationSnapshot["rules"]): string {
  if (decision === "automatic") return `Rapprochement automatique possible (seuil ${rules.automaticThreshold} %).`;
  if (decision === "to_review") return `Contrôle manuel requis (seuil ${rules.reviewThreshold} % ou ambiguïté).`;
  return "Correspondance proposée uniquement pour une allocation manuelle.";
}

function statusTone(status: string): string {
  if (status === "overdue") return "danger";
  if (status === "to_review" || status === "partially_matched") return "warning";
  if (status === "auto_matched" || status === "confirmed") return "success";
  return "muted";
}

function signedMoney(value: number): string {
  return `${value > 0 ? "+ " : value < 0 ? "- " : ""}${money.format(Math.abs(value))}`;
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : shortDate.format(parsed);
}
