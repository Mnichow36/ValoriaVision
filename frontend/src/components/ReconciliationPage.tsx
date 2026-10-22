import { useEffect, useMemo, useState } from "react";
import type { MouseEvent } from "react";
import type { ReactNode } from "react";

import {
  cancelReconciliation,
  confirmManualReconciliation,
  confirmReconciliationProposal,
  getReconciliation,
  getReconciliationHistory,
  rejectReconciliationProposal,
  updateReconciliationRules,
} from "../api/client";
import { ContextMenu, type ContextMenuItem, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";
import type {
  ReconciliationAccount,
  ReconciliationHistoryItem,
  ReconciliationOccurrence,
  ReconciliationSnapshot,
  ReconciliationSuggestion,
  ReconciliationTransaction,
} from "../api/contracts";

interface ReconciliationPageProps {
  accountId: string;
  onAccountsChange: (accounts: ReconciliationAccount[]) => void;
  refreshKey: number;
  rulesRequestKey: number;
  status: string;
  token: string;
}

const money = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 2,
});

const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

export function ReconciliationPage({ accountId, onAccountsChange, refreshKey, rulesRequestKey, status, token }: ReconciliationPageProps) {
  const [snapshot, setSnapshot] = useState<ReconciliationSnapshot>();
  const [selectedTransactionId, setSelectedTransactionId] = useState<number>();
  const [selectedOccurrenceId, setSelectedOccurrenceId] = useState<number>();
  const [error, setError] = useState<string>();
  const [localRefreshKey, setLocalRefreshKey] = useState(0);
  const [manualMode, setManualMode] = useState(false);
  const [includeOverage, setIncludeOverage] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionFeedback, setActionFeedback] = useState<{ kind: "success" | "error"; text: string }>();
  const [menu, setMenu] = useState<ContextMenuState>();
  const [rulesOpen, setRulesOpen] = useState(false);

  useEffect(() => {
    if (rulesRequestKey > 0) setRulesOpen(true);
  }, [rulesRequestKey]);
  const [history, setHistory] = useState<{ title: string; items: ReconciliationHistoryItem[] }>();

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
        const manualId = data.transactions.find((row) => row.id === transactionId)?.manualCandidate?.occurrenceId;
        setSelectedTransactionId(transactionId);
        const chosenTransaction = data.transactions.find((row) => row.id === transactionId);
        setSelectedOccurrenceId(suggestion?.occurrenceId ?? manualId ?? closestOccurrenceId(chosenTransaction, data.occurrences));
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les rapprochements ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [accountId, localRefreshKey, onAccountsChange, refreshKey, status, token]);

  const selectedTransaction = snapshot?.transactions.find((row) => row.id === selectedTransactionId);
  const bestSuggestion = useMemo(
    () => snapshot?.suggestions.find((row) => row.transactionId === selectedTransactionId),
    [selectedTransactionId, snapshot],
  );
  const selectedOccurrence = snapshot?.occurrences.find((row) => row.id === (selectedOccurrenceId ?? bestSuggestion?.occurrenceId));
  const selectedSuggestion = snapshot?.suggestions.find(
    (row) => row.transactionId === selectedTransactionId && row.occurrenceId === selectedOccurrence?.id,
  );

  function selectTransaction(transaction: ReconciliationTransaction) {
    setSelectedTransactionId(transaction.id);
    const suggestion = snapshot?.suggestions.find((row) => row.transactionId === transaction.id);
    setSelectedOccurrenceId(suggestion?.occurrenceId ?? transaction.manualCandidate?.occurrenceId ?? closestOccurrenceId(transaction, snapshot?.occurrences ?? []));
    setManualMode(false);
    setIncludeOverage(false);
    setActionFeedback(undefined);
  }

  function selectOccurrence(occurrence: ReconciliationOccurrence) {
    setSelectedOccurrenceId(occurrence.id);
    setManualMode(false);
    setIncludeOverage(false);
    setActionFeedback(undefined);
  }

  async function runAction(
    action: "confirm" | "reject",
    pair: { transaction?: ReconciliationTransaction; occurrence?: ReconciliationOccurrence; suggestion?: ReconciliationSuggestion } = {},
  ) {
    const selectedTransaction = pair.transaction;
    const selectedOccurrence = pair.occurrence;
    const selectedSuggestion = pair.suggestion;
    if (!selectedTransaction || !selectedOccurrence) return;
    setActionBusy(true);
    setActionFeedback(undefined);
    try {
      if (action === "reject" && !selectedSuggestion?.proposalId) {
        throw new Error("Cette paire ne correspond pas à une proposition enregistrée.");
      }
      const result = action === "reject"
        ? await rejectReconciliationProposal(token, selectedSuggestion!.proposalId!)
        : selectedSuggestion?.proposalId && !manualMode
          ? await confirmReconciliationProposal(token, selectedSuggestion.proposalId)
          : await confirmManualReconciliation(token, {
              occurrenceId: selectedOccurrence.id,
              transactionId: selectedTransaction.id,
              includeOverage,
            });
      setActionFeedback({ kind: "success", text: result.message });
      setManualMode(false);
      setIncludeOverage(false);
      setLocalRefreshKey((key) => key + 1);
    } catch (cause: unknown) {
      setActionFeedback({
        kind: "error",
        text: cause instanceof Error ? cause.message : "L’action de rapprochement a échoué.",
      });
    } finally {
      setActionBusy(false);
    }
  }

  async function cancelLink(occurrenceId: number, transactionId?: number) {
    setActionBusy(true);
    setActionFeedback(undefined);
    try {
      const result = await cancelReconciliation(token, { occurrenceId, transactionId });
      setActionFeedback({ kind: result.success ? "success" : "error", text: result.message });
      setHistory(undefined);
      setLocalRefreshKey((key) => key + 1);
    } catch (cause: unknown) {
      setActionFeedback({
        kind: "error",
        text: cause instanceof Error ? cause.message : "L’annulation du rapprochement a échoué.",
      });
    } finally {
      setActionBusy(false);
    }
  }

  async function showHistory(title: string, filter: { transactionId?: number; occurrenceId?: number }) {
    try {
      const result = await getReconciliationHistory(token, filter);
      setHistory({ title, items: result.items });
    } catch (cause: unknown) {
      setActionFeedback({
        kind: "error",
        text: cause instanceof Error ? cause.message : "L’historique ne peut pas être chargé.",
      });
    }
  }

  function openTransactionMenu(event: MouseEvent, transaction: ReconciliationTransaction) {
    event.preventDefault();
    selectTransaction(transaction);
    const link = transaction.links[0];
    const proposal = snapshot?.suggestions.find((row) => row.transactionId === transaction.id && row.proposalId);
    const hasProposal = Boolean(proposal);
    const proposalOccurrence = snapshot?.occurrences.find((row) => row.id === proposal?.occurrenceId);
    const pair = { transaction, occurrence: proposalOccurrence, suggestion: proposal };
    const items: ContextMenuItem[] = transaction.reconciled && link
      ? [
          { label: "Annuler le rapprochement", danger: true, onSelect: () => void cancelLink(link.occurrenceId, transaction.id) },
          { label: "Voir l’historique", onSelect: () => void showHistory(transaction.beneficiary || transaction.label, { transactionId: transaction.id }) },
        ]
      : [
          { label: "Valider le rapprochement", disabled: !hasProposal, hint: hasProposal ? undefined : "Aucune proposition pour cette transaction", onSelect: () => void runAction("confirm", pair) },
          { label: "Ignorer la proposition", disabled: !hasProposal, hint: hasProposal ? undefined : "Aucune proposition pour cette transaction", onSelect: () => void runAction("reject", pair) },
          { label: "Voir l’historique", onSelect: () => void showHistory(transaction.beneficiary || transaction.label, { transactionId: transaction.id }) },
        ];
    setMenu({ x: event.clientX, y: event.clientY, items });
  }

  function openOccurrenceMenu(event: MouseEvent, occurrence: ReconciliationOccurrence) {
    event.preventDefault();
    selectOccurrence(occurrence);
    const link = occurrence.links[0];
    const items: ContextMenuItem[] = [];
    if (occurrence.reconciled && link) {
      items.push({ label: "Annuler le rapprochement", danger: true, onSelect: () => void cancelLink(occurrence.id, link.transactionId) });
    }
    items.push({ label: "Voir l’historique", onSelect: () => void showHistory(occurrence.label, { occurrenceId: occurrence.id }) });
    setMenu({ x: event.clientX, y: event.clientY, items });
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
        <ReconciliationKpi detail="Issues des imports et saisies" detailTone={snapshot.summary.unmatchedTransactions > 0 ? "danger" : "success"} label="Transactions non rapprochées" tone="orange" value={snapshot.summary.unmatchedTransactions} />
        <ReconciliationKpi detail={`${snapshot.summary.toReview} à vérifier · ${snapshot.summary.partial} écarts de montant`} detailTone="success" label="Prévisions ouvertes" tone="blue" value={snapshot.summary.openOccurrences} />
        <ReconciliationKpi detail={`Score moyen ${snapshot.summary.averageScore} %`} detailTone="success" label="Propositions auto" tone="cyan" value={snapshot.summary.automaticProposals} />
        <ReconciliationKpi detail="Automatiques + manuelles" detailTone="success" label="Rapprochées" tone="green" value={snapshot.summary.matched} />
      </section>

      <section className="reconciliation-workbench">
        <QueuePanel count={snapshot.transactions.length} subtitle={snapshot.view.transactionsSubtitle} title={snapshot.view.transactionsTitle}>
          {snapshot.transactions.length > 0 ? snapshot.transactions.map((transaction) => (
            <TransactionCard
              key={transaction.id}
              suggestion={snapshot.suggestions.find((row) => row.transactionId === transaction.id)}
              onContextMenu={(event) => openTransactionMenu(event, transaction)}
              onSelect={() => selectTransaction(transaction)}
              selected={transaction.id === selectedTransactionId}
              transaction={transaction}
            />
          )) : <EmptyQueue text="Aucune transaction à rapprocher pour ce filtre." />}
        </QueuePanel>

        <QueuePanel count={snapshot.occurrences.length} subtitle={snapshot.view.occurrencesSubtitle} title={snapshot.view.occurrencesTitle}>
          {snapshot.occurrences.length > 0 ? snapshot.occurrences.map((occurrence) => (
            <OccurrenceCard
              key={occurrence.id}
              occurrence={occurrence}
              onContextMenu={(event) => openOccurrenceMenu(event, occurrence)}
              onSelect={() => selectOccurrence(occurrence)}
              selected={occurrence.id === selectedOccurrence?.id}
            />
          )) : <EmptyQueue text="Aucune prévision ouverte pour ce filtre." />}
        </QueuePanel>

        <ProposalPanel
          actionBusy={actionBusy}
          actionFeedback={actionFeedback}
          includeOverage={includeOverage}
          manualMode={manualMode}
          onIncludeOverageChange={setIncludeOverage}
          onReject={() => runAction("reject", { transaction: selectedTransaction, occurrence: selectedOccurrence, suggestion: selectedSuggestion })}
          onToggleManual={() => {
            setManualMode((current) => !current);
            setIncludeOverage(false);
            setActionFeedback(undefined);
          }}
          onValidate={() => runAction("confirm", { transaction: selectedTransaction, occurrence: selectedOccurrence, suggestion: selectedSuggestion })}
          occurrence={selectedOccurrence}
          rules={snapshot.rules}
          suggestion={selectedSuggestion}
          transaction={selectedTransaction}
        />
      </section>

      {history && (
        <SideDrawer eyebrow="Rapprochements" onClose={() => setHistory(undefined)} title={`Historique · ${history.title}`}>
          <p className="side-drawer__intro">Les liens annulés restent consultables pour la traçabilité.</p>
          {history.items.length === 0 && <EmptyQueue text="Aucun rapprochement enregistré." />}
          {history.items.map((item) => (
            <div className={item.active ? "reconciliation-history__line" : "reconciliation-history__line reconciliation-history__line--cancelled"} key={item.linkId}>
              <strong>{item.transactionLabel} ↔ {item.recurrenceName || item.occurrenceLabel}</strong>
              <span>{formatDate(item.transactionDate)} · {signedMoney(item.transactionAmount)} · affecté {money.format(Math.abs(item.appliedAmount))} · {item.matchType === "manual" || item.matchType === "manual_overage" ? "manuel" : "automatique"}</span>
              <small>{item.active ? "Rapprochement actif" : `Annulé le ${item.cancelledAt ?? ""}`} · créé le {item.createdAt}</small>
            </div>
          ))}
        </SideDrawer>
      )}
      {rulesOpen && snapshot && (
        <RulesDrawer
          onClose={() => setRulesOpen(false)}
          onSaved={() => { setRulesOpen(false); setLocalRefreshKey((key) => key + 1); }}
          rules={snapshot.rules}
          token={token}
        />
      )}
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
    </div>
  );
}

function RulesDrawer({ onClose, onSaved, rules, token }: { onClose: () => void; onSaved: () => void; rules: ReconciliationSnapshot["rules"]; token: string }) {
  const [draft, setDraft] = useState({
    dateToleranceDays: String(rules.dateToleranceDays),
    amountToleranceAbs: String(rules.amountToleranceAbs),
    amountTolerancePercent: String(rules.amountTolerancePercent),
    manualWindowDays: String(rules.manualWindowDays),
    manualAmountTolerancePercent: String(rules.manualAmountTolerancePercent),
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  function field(key: keyof typeof draft, label: string, unit: string, hint: string) {
    return (
      <label className="account-field">
        <span>{label}</span>
        <div className="rules-input"><input inputMode="decimal" onChange={(event) => setDraft((current) => ({ ...current, [key]: event.target.value }))} value={draft[key]} /><b>{unit}</b></div>
        <small>{hint}</small>
      </label>
    );
  }

  async function save() {
    setBusy(true);
    setError(undefined);
    try {
      const toNumber = (value: string) => Number(value.replace(",", "."));
      await updateReconciliationRules(token, {
        dateToleranceDays: toNumber(draft.dateToleranceDays),
        amountToleranceAbs: toNumber(draft.amountToleranceAbs),
        amountTolerancePercent: toNumber(draft.amountTolerancePercent),
        manualWindowDays: toNumber(draft.manualWindowDays),
        manualAmountTolerancePercent: toNumber(draft.manualAmountTolerancePercent),
      });
      onSaved();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Les règles n’ont pas pu être enregistrées.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Rapprochements"
      footer={(
        <>
          <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button>
          <button disabled={busy} onClick={() => void save()} type="button">{busy ? "Enregistrement…" : "Enregistrer les écarts"}</button>
        </>
      )}
      onClose={onClose}
      title="Écarts de dates et de montants"
    >
      <section className="rules-group">
        <h3>Rapprochement automatique</h3>
        <p>Au-delà de ces écarts, le moteur ne propose aucune correspondance automatique.</p>
        {field("dateToleranceDays", "Écart de date maximum", "jours", "0 à 60")}
        {field("amountToleranceAbs", "Écart de montant minimum toléré", "€", "Toujours toléré, même sur un petit montant")}
        {field("amountTolerancePercent", "Écart de montant en pourcentage", "%", "0 à 100, appliqué au montant prévu")}
      </section>
      <section className="rules-group">
        <h3>Proposition manuelle</h3>
        <p>Pour les opérations qui arrivent plus tôt ou plus tard que prévu (retraite, salaire…). Elles sont listées avec la pastille « Écart de date ».</p>
        {field("manualWindowDays", "Fenêtre de date", "jours", "0 à 180, au moins égale à l’écart automatique")}
        {field("manualAmountTolerancePercent", "Écart de montant", "%", "0 à 100")}
      </section>
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}

function ReconciliationKpi({ detail, detailTone, label, tone, value }: { detail: string; detailTone: "danger" | "success"; label: string; tone: string; value: number }) {
  return (
    <article className="card reconciliation-kpi">
      <div><span>{label}</span><i className={`reconciliation-kpi__mark reconciliation-kpi__mark--${tone}`} /></div>
      <strong>{value.toLocaleString("fr-FR")}</strong>
      <small className={`reconciliation-kpi__detail reconciliation-kpi__detail--${detailTone}`}>{detail}</small>
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

function TransactionCard({ onContextMenu, onSelect, selected, suggestion, transaction }: { onContextMenu: (event: MouseEvent) => void; onSelect: () => void; selected: boolean; suggestion?: ReconciliationSuggestion; transaction: ReconciliationTransaction }) {
  const displayName = transaction.beneficiary || transaction.label;
  const hasDistinctBankLabel = Boolean(transaction.beneficiary)
    && transaction.beneficiary.trim().toLocaleLowerCase("fr") !== transaction.label.trim().toLocaleLowerCase("fr");
  let pill: ReactNode;
  if (transaction.reconciled) {
    pill = <span className="reconciliation-status reconciliation-status--success" title={`Rapprochée avec « ${transaction.links[0]?.label ?? ""} »`}>Rapprochée</span>;
  } else if (transaction.manualCandidate) {
    pill = <span className="reconciliation-status reconciliation-status--warning" title={transaction.manualCandidate.reason}>Écart de date · {transaction.manualCandidate.dayGap} j</span>;
  } else {
    pill = <span className={`reconciliation-status reconciliation-status--${suggestionTone(suggestion)}`} title={suggestion?.reason}>Non rapprochée</span>;
  }
  return (
    <button aria-pressed={selected} className={selected ? "reconciliation-item reconciliation-item--selected" : "reconciliation-item"} onClick={onSelect} onContextMenu={onContextMenu} type="button">
      <div className="reconciliation-item__top"><strong>{displayName}</strong></div>
      {hasDistinctBankLabel && <small className="reconciliation-item__bank-label" title={transaction.label}>{transaction.label}</small>}
      <div className="reconciliation-item__meta"><span>{formatDate(transaction.date)} - {transaction.accountName}</span></div>
      <div className="reconciliation-item__footer"><b className={transaction.amount >= 0 ? "positive" : "negative"}>{signedMoney(transaction.amount)}</b>{pill}</div>
      {!transaction.reconciled && transaction.remainingAmount < Math.abs(transaction.amount) && <small className="reconciliation-item__hint">{money.format(transaction.remainingAmount)} disponibles</small>}
    </button>
  );
}

function OccurrenceCard({ occurrence, onContextMenu, onSelect, selected }: { occurrence: ReconciliationOccurrence; onContextMenu: (event: MouseEvent) => void; onSelect: () => void; selected: boolean }) {
  return (
    <button aria-pressed={selected} className={selected ? "reconciliation-item reconciliation-item--selected" : "reconciliation-item"} onClick={onSelect} onContextMenu={onContextMenu} type="button">
      <div className="reconciliation-item__top"><strong>{occurrence.label}</strong></div>
      <div className="reconciliation-item__meta"><span>{formatDate(occurrence.date)} - {occurrence.accountName}</span></div>
      <div className="reconciliation-item__footer"><b className={occurrence.amount >= 0 ? "positive" : "negative"}>{signedMoney(occurrence.amount)}</b><span className={`reconciliation-status reconciliation-status--${statusTone(occurrence.displayStatus)}`}>{occurrence.statusLabel}</span></div>
      {Math.abs(occurrence.remainingAmount - Math.abs(occurrence.amount)) > 0.005 && <small className="reconciliation-item__hint">{money.format(occurrence.remainingAmount)} restants</small>}
    </button>
  );
}

/** Présélection par défaut : prévision de même sens dont le montant est le plus proche. */
function closestOccurrenceId(transaction: ReconciliationTransaction | undefined, occurrences: ReconciliationOccurrence[]): number | undefined {
  if (!transaction) return occurrences[0]?.id;
  const sameDirection = occurrences.filter((row) => Math.sign(row.amount) === Math.sign(transaction.amount) && row.accountId === transaction.accountId);
  const pool = sameDirection.length > 0 ? sameDirection : occurrences;
  const gap = (row: ReconciliationOccurrence) => Math.abs(Math.abs(row.amount) - Math.abs(transaction.amount));
  return [...pool].sort((a, b) => gap(a) - gap(b))[0]?.id;
}

function suggestionTone(suggestion?: ReconciliationSuggestion): string {
  if (!suggestion) return "muted";
  if (Math.abs(suggestion.amountDifference) > 0.005) return "danger";
  if (suggestion.decision === "automatic") return "success";
  return "warning";
}

function ProposalPanel({
  actionBusy,
  actionFeedback,
  includeOverage,
  manualMode,
  occurrence,
  onIncludeOverageChange,
  onReject,
  onToggleManual,
  onValidate,
  rules,
  suggestion,
  transaction,
}: {
  actionBusy: boolean;
  actionFeedback?: { kind: "success" | "error"; text: string };
  includeOverage: boolean;
  manualMode: boolean;
  occurrence?: ReconciliationOccurrence;
  onIncludeOverageChange: (value: boolean) => void;
  onReject: () => void;
  onToggleManual: () => void;
  onValidate: () => void;
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

  const transactionDisplayName = transaction.beneficiary || transaction.label;

  if (!occurrence) {
    return (
      <aside className="card reconciliation-proposal">
        <div className="reconciliation-heading"><div><h2>Proposition de rapprochement</h2><p>Sélectionnez également une prévision à traiter.</p></div></div>
        <SelectionSummary label="Transaction réelle sélectionnée" name={transactionDisplayName} date={transaction.date} account={transaction.accountName} amount={transaction.amount} tone="blue" />
        <p className="reconciliation-proposal__empty">Aucune prévision n’est sélectionnée.</p>
      </aside>
    );
  }

  const dateDifference = Math.abs((new Date(transaction.date).getTime() - new Date(occurrence.date).getTime()) / 86_400_000);
  const overage = Math.max(transaction.remainingAmount - occurrence.remainingAmount, 0);
  const amountGap = Math.abs(Math.abs(transaction.amount) - Math.abs(occurrence.amount));
  return (
    <aside className="card reconciliation-proposal">
      <div className="reconciliation-heading"><div><h2>Proposition de rapprochement</h2><p>Valoria compare date, montant, compte et libellé.</p></div></div>
      <SelectionSummary label="Transaction réelle sélectionnée" name={transactionDisplayName} date={transaction.date} account={transaction.accountName} amount={transaction.amount} tone="blue" />
      <SelectionSummary label="Prévision associée" name={occurrence.label} date={occurrence.date} account={occurrence.accountName} amount={occurrence.amount} tone="green" />
      {suggestion && (
        <div className="reconciliation-score">
          <div><span>Score de correspondance</span><strong className="reconciliation-score__badge">{suggestion.score} %</strong></div>
          <div className="reconciliation-score__track"><span style={{ width: `${Math.max(0, Math.min(100, suggestion.score))}%` }} /></div>
          <small>{decisionLabel(suggestion.decision, rules)}</small>
        </div>
      )}
      <div className="reconciliation-controls">
        <h3>Contrôles</h3>
        <p className={amountGap < 0.005 ? "ok" : "warn"}>{amountGap < 0.005 ? "Montant identique" : "Écart de montant"} : {money.format(amountGap)} d’écart</p>
        <p className={Math.round(dateDifference) <= rules.dateToleranceDays ? "ok" : "warn"}>{Math.round(dateDifference) === 0 ? "Même date" : `Date proche : ${new Date(transaction.date) >= new Date(occurrence.date) ? "+" : "-"} ${Math.round(dateDifference)} jour(s)`}</p>
        {suggestion ? <p className="muted">Critères : {suggestion.reason}</p> : (
          <p className="muted">{transaction.manualCandidate && transaction.manualCandidate.occurrenceId === occurrence.id ? transaction.manualCandidate.reason : "Cette paire n’est pas la proposition prioritaire du moteur. Vérifiez les montants et les comptes avant une affectation manuelle."}</p>
        )}
      </div>
      {manualMode && (
        <div className="reconciliation-manual-box">
          <div><span>Transaction disponible</span><strong>{money.format(transaction.remainingAmount)}</strong></div>
          <div><span>Prévision restante</span><strong>{money.format(occurrence.remainingAmount)}</strong></div>
          {overage > 0.005 && (
            <label>
              <input checked={includeOverage} onChange={(event) => onIncludeOverageChange(event.target.checked)} type="checkbox" />
              Affecter aussi le dépassement de {money.format(overage)}
            </label>
          )}
          <small>{includeOverage ? "Le dépassement sera enregistré explicitement." : "L’affectation sera limitée au montant restant de la prévision."}</small>
        </div>
      )}
      {actionFeedback && <p className={`reconciliation-feedback reconciliation-feedback--${actionFeedback.kind}`} role="status">{actionFeedback.text}</p>}
      <div className="reconciliation-actions">
        <button disabled={actionBusy || !suggestion?.proposalId} onClick={onReject} title={suggestion?.proposalId ? "Rejeter cette proposition sans supprimer les données" : "Aucune proposition enregistrée à rejeter"} type="button">Ignorer</button>
        <button aria-pressed={manualMode} className={manualMode ? "reconciliation-actions__manual-active" : ""} disabled={actionBusy} onClick={onToggleManual} type="button">{manualMode ? "Quitter le mode manuel" : "Mode manuel"}</button>
        <button className="reconciliation-actions__primary" disabled={actionBusy} onClick={onValidate} type="button">{actionBusy ? "Traitement…" : manualMode ? "Confirmer l’affectation" : "Valider le rapprochement"}</button>
      </div>
    </aside>
  );
}

function SelectionSummary({ account, amount, date, label, name, tone }: { account: string; amount: number; date: string; label: string; name: string; tone: "blue" | "green" }) {
  return (
    <div className={`reconciliation-selection reconciliation-selection--${tone}`}>
      <span>{label}</span>
      <strong>{name}</strong>
      <small>{formatDate(date)} · {account} · <b className={amount >= 0 ? "positive" : "negative"}>{signedMoney(amount)}</b></small>
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
  if (status === "to_review" || status === "amount_gap") return "warning";
  if (status === "matched") return "success";
  return "muted";
}

function signedMoney(value: number): string {
  return `${value > 0 ? "+ " : value < 0 ? "- " : ""}${money.format(Math.abs(value))}`;
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : shortDate.format(parsed);
}
