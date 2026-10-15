import { type FormEvent, useEffect, useMemo, useState } from "react";

import { bulkUpdateTransactions, getTransactions, updateTransaction } from "../api/client";
import type { TransactionActionResult, TransactionEditPayload, TransactionRow, TransactionsSnapshot } from "../api/contracts";
import { BankImportPage } from "./BankImportPage";

interface TransactionsPageProps {
  importRequestKey: number;
  onDataChanged: () => void;
  onNavigateSettings: () => void;
  onViewChange: (view: TransactionsView) => void;
  preferredImportAccountId?: number;
  token: string;
  view: TransactionsView;
}

export type TransactionsView = "journal" | "import" | "history";

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  minimumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function TransactionsPage({ importRequestKey, onDataChanged, onNavigateSettings, onViewChange, preferredImportAccountId, token, view }: TransactionsPageProps) {
  const [snapshot, setSnapshot] = useState<TransactionsSnapshot>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [accountId, setAccountId] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [editing, setEditing] = useState<TransactionRow>();
  const [notice, setNotice] = useState<string>();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkCategory, setBulkCategory] = useState("");
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getTransactions(token, controller.signal)
      .then((data) => {
        setSnapshot(data);
        const dates = data.transactions.map((transaction) => transaction.date).filter(Boolean).sort();
        setDateFrom((current) => current || dates[0] || "");
        setDateTo((current) => current || dates[dates.length - 1] || "");
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les transactions ne peuvent pas être chargées.");
        }
      });
    return () => controller.abort();
  }, [token, refreshKey]);

  const visibleTransactions = useMemo(() => {
    if (!snapshot) return [];
    const query = search.trim().toLocaleLowerCase("fr");
    return snapshot.transactions.filter((transaction) => {
      const matchesSearch = !query || [
        transaction.label,
        transaction.category,
        transaction.accountName,
        transaction.bank,
        String(transaction.amount),
      ].some((value) => value.toLocaleLowerCase("fr").includes(query));
      const matchesAccount = accountId === "all" || transaction.accountId === Number(accountId);
      const matchesFrom = !dateFrom || transaction.date >= dateFrom;
      const matchesTo = !dateTo || transaction.date <= dateTo;
      return matchesSearch && matchesAccount && matchesFrom && matchesTo;
    });
  }, [accountId, dateFrom, dateTo, search, snapshot]);

  const visibleIds = visibleTransactions.map((transaction) => transaction.id);
  const visibleSelectedIds = selectedIds.filter((id) => visibleIds.includes(id));
  const allVisibleSelected = visibleIds.length > 0 && visibleSelectedIds.length === visibleIds.length;

  function clearSelectionForFilter(change: () => void) {
    setSelectedIds([]);
    setBulkError(undefined);
    change();
  }

  function toggleTransaction(transactionId: number) {
    setSelectedIds((current) => current.includes(transactionId)
      ? current.filter((id) => id !== transactionId)
      : [...current, transactionId]);
    setBulkError(undefined);
  }

  function toggleVisible() {
    setSelectedIds((current) => allVisibleSelected
      ? current.filter((id) => !visibleIds.includes(id))
      : Array.from(new Set([...current, ...visibleIds])));
    setBulkError(undefined);
  }

  async function runBulkAction(action: "category" | "validate") {
    if (visibleSelectedIds.length === 0) return;
    if (action === "category" && !bulkCategory) {
      setBulkError("Choisissez une catégorie à appliquer.");
      return;
    }
    setBulkBusy(true);
    setBulkError(undefined);
    try {
      const result = await bulkUpdateTransactions(token, visibleSelectedIds, action, bulkCategory);
      setNotice(result.message);
      setSelectedIds([]);
      setBulkCategory("");
      setRefreshKey((key) => key + 1);
      onDataChanged();
    } catch (cause: unknown) {
      setBulkError(errorMessage(cause));
    } finally {
      setBulkBusy(false);
    }
  }

  if (error) {
    return (
      <section className="error-state">
        <strong>Le journal des transactions ne peut pas être affiché.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Chargement du journal depuis le moteur Python…</div>;
  }

  if (view !== "journal") {
    return (
      <BankImportPage
        importRequestKey={importRequestKey}
        onImportCompleted={() => {
          setRefreshKey((key) => key + 1);
          onDataChanged();
        }}
        onNavigateSettings={onNavigateSettings}
        onViewChange={onViewChange}
        preferredAccountId={preferredImportAccountId}
        snapshot={snapshot}
        token={token}
        view={view}
      />
    );
  }

  return (
    <div className="transactions-page">
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      <article className="card transactions-journal">
        <div className="transactions-heading"><h2>Journal des transactions</h2></div>
        <div className="transaction-filters" role="search">
          <input aria-label="Rechercher une transaction" onChange={(event) => clearSelectionForFilter(() => setSearch(event.target.value))} placeholder="Recherche libellé, montant…" type="search" value={search} />
          <select aria-label="Filtrer par compte" onChange={(event) => clearSelectionForFilter(() => setAccountId(event.target.value))} value={accountId}>
            <option value="all">Tous les comptes</option>
            {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
          <label><span>Du</span><input aria-label="Date de début" onChange={(event) => clearSelectionForFilter(() => setDateFrom(event.target.value))} type="date" value={dateFrom} /></label>
          <label><span>Au</span><input aria-label="Date de fin" onChange={(event) => clearSelectionForFilter(() => setDateTo(event.target.value))} type="date" value={dateTo} /></label>
          <span className="transaction-count">{visibleTransactions.length} opération{visibleTransactions.length > 1 ? "s" : ""}</span>
        </div>

        {visibleSelectedIds.length > 0 && (
          <div className="transaction-bulkbar">
            <strong>{visibleSelectedIds.length} sélectionnée{visibleSelectedIds.length > 1 ? "s" : ""}</strong>
            <select aria-label="Catégorie groupée" disabled={bulkBusy} onChange={(event) => setBulkCategory(event.target.value)} value={bulkCategory}>
              <option value="">Choisir une catégorie</option>
              {snapshot.categories.filter((category) => category.name && category.name !== "À catégoriser").map((category) => <option key={category.name} value={category.name}>{category.name}</option>)}
            </select>
            <button className="secondary-button" disabled={bulkBusy || !bulkCategory} onClick={() => void runBulkAction("category")} type="button">Appliquer la catégorie</button>
            <button disabled={bulkBusy} onClick={() => void runBulkAction("validate")} type="button">Valider la sélection</button>
            <button aria-label="Désélectionner" className="transaction-bulk-clear" disabled={bulkBusy} onClick={() => setSelectedIds([])} type="button">×</button>
            {bulkError && <span className="transaction-bulk-error" role="alert">{bulkError}</span>}
          </div>
        )}

        <div className="transactions-table-wrap">
          <table className="transactions-table">
            <thead><tr><th><label className="transaction-select"><input aria-label="Sélectionner toutes les transactions affichées" checked={allVisibleSelected} onChange={toggleVisible} type="checkbox" />Date</label></th><th>Compte</th><th>Libellé</th><th>Catégorie</th><th>Statut</th><th>Montant</th></tr></thead>
            <tbody>
              {visibleTransactions.length > 0 ? visibleTransactions.map((transaction) => (
                <TransactionLine
                  key={transaction.id}
                  onEdit={() => setEditing(transaction)}
                  onToggle={() => toggleTransaction(transaction.id)}
                  selected={selectedIds.includes(transaction.id)}
                  transaction={transaction}
                />
              )) : (
                <tr><td className="transactions-empty" colSpan={6}>Aucune opération ne correspond aux filtres sélectionnés.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </article>

      <section className="transaction-insights" aria-label="Indicateurs du journal">
        <InsightCard
          badge={`${snapshot.recentImport ? snapshot.recentImport.duplicateCount + snapshot.recentImport.errorCount : 0} rejet`}
          badgeTone="success"
          description={snapshot.recentImport
            ? `${snapshot.recentImport.fileName} · ${snapshot.recentImport.recognizedCount} lignes reconnues`
            : "Aucun lot d’import enregistré"}
          progress={snapshot.recentImport?.recognizedCount
            ? (snapshot.recentImport.importedCount / snapshot.recentImport.recognizedCount) * 100
            : 0}
          title="Import récent"
        />
        <InsightCard
          badge={`${snapshot.summary.categorizedPercent} %`}
          badgeTone="blue"
          description="Règles personnelles appliquées localement"
          progress={snapshot.summary.categorizedPercent}
          title="Catégorisation locale"
        />
        <InsightCard
          badge={`${snapshot.summary.reviewCount} à revoir`}
          badgeTone="warning"
          description="Dates et montants homogènes avant rapprochement"
          progress={snapshot.summary.transactionCount
            ? ((snapshot.summary.transactionCount - snapshot.summary.reviewCount) / snapshot.summary.transactionCount) * 100
            : 100}
          title="Qualité données"
        />
      </section>
      {editing && (
        <TransactionEditor
          onClose={() => setEditing(undefined)}
          onCompleted={(result) => {
            setEditing(undefined);
            setNotice(result.message);
            setRefreshKey((key) => key + 1);
            onDataChanged();
          }}
          snapshot={snapshot}
          token={token}
          transaction={editing}
        />
      )}
    </div>
  );
}

function TransactionLine({ onEdit, onToggle, selected, transaction }: { onEdit: () => void; onToggle: () => void; selected: boolean; transaction: TransactionRow }) {
  return (
    <tr
      aria-label={`Modifier la transaction ${transaction.label}`}
      className={selected ? "transaction-row-action transaction-row-action--selected" : "transaction-row-action"}
      onClick={onEdit}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onEdit();
        }
      }}
      tabIndex={0}
      title="Ouvrir et modifier cette transaction"
    >
      <td><label className="transaction-select" onClick={(event) => event.stopPropagation()}><input aria-label={`Sélectionner ${transaction.label}`} checked={selected} onChange={onToggle} type="checkbox" />{formatDate(transaction.date)}</label></td>
      <td>{shortAccount(transaction)}</td>
      <td>{transaction.label}</td>
      <td><span className={`transaction-pill transaction-pill--${categoryTone(transaction.category)}`}>{transaction.category}</span></td>
      <td><span className={`transaction-pill transaction-pill--${statusTone(transaction.status)}`}>{transaction.status}</span></td>
      <td className={transaction.amount < 0 ? "transaction-amount transaction-amount--negative" : "transaction-amount transaction-amount--positive"}>{signedMoney(transaction.amount)}</td>
    </tr>
  );
}

function TransactionEditor({ onClose, onCompleted, snapshot, token, transaction }: {
  onClose: () => void;
  onCompleted: (result: TransactionActionResult) => void;
  snapshot: TransactionsSnapshot;
  token: string;
  transaction: TransactionRow;
}) {
  const [draft, setDraft] = useState<TransactionEditPayload>({
    accountId: transaction.accountId,
    date: transaction.date,
    label: transaction.label,
    category: transaction.category === "À catégoriser" ? "" : transaction.category,
    direction: transaction.type === "Crédit" || transaction.amount >= 0 ? "Crédit" : "Débit",
    amount: Math.abs(transaction.amount),
    status: transaction.status,
  });
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();
  const statuses = Array.from(new Set([
    transaction.status,
    "Validée",
    "À catégoriser",
    "À vérifier",
    "À revoir",
  ].filter(Boolean)));

  function field<Key extends keyof TransactionEditPayload>(key: Key, value: TransactionEditPayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function changeCategory(category: string) {
    setDraft((current) => ({
      ...current,
      category,
      status: category && current.status === "À catégoriser" ? "Validée" : !category ? "À catégoriser" : current.status,
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(await updateTransaction(token, transaction.id, draft));
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="transaction-editor-title" aria-modal="true" className="account-editor transaction-editor" role="dialog">
        <header>
          <div><span className="eyebrow">Transaction n°{transaction.id}</span><h2 id="transaction-editor-title">Modifier et valider</h2></div>
          <button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="transaction-editor-source"><span>Source</span><strong>{transaction.source || "Non renseignée"}</strong>{transaction.importBatchId && <small>Lot d’import n°{transaction.importBatchId}</small>}</div>
          <div className="account-editor-grid">
            <label className="account-field account-field--wide"><span>Compte *</span><select onChange={(event) => field("accountId", Number(event.target.value))} value={draft.accountId}>{snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}</select></label>
            <label className="account-field"><span>Date *</span><input onChange={(event) => field("date", event.target.value)} required type="date" value={draft.date} /></label>
            <label className="account-field"><span>Catégorie</span><select onChange={(event) => changeCategory(event.target.value)} value={draft.category}><option value="">À catégoriser</option>{snapshot.categories.filter((category) => category.name && category.name !== "À catégoriser").map((category) => <option key={category.name} value={category.name}>{category.name}</option>)}</select></label>
            <label className="account-field account-field--wide"><span>Libellé *</span><input autoFocus maxLength={240} onChange={(event) => field("label", event.target.value)} required value={draft.label} /></label>
            <label className="account-field"><span>Sens *</span><select onChange={(event) => field("direction", event.target.value as "Débit" | "Crédit")} value={draft.direction}><option>Débit</option><option>Crédit</option></select></label>
            <label className="account-field"><span>Montant *</span><input min="0" onChange={(event) => field("amount", Number(event.target.value))} required step="0.01" type="number" value={draft.amount} /></label>
            <label className="account-field account-field--wide"><span>Statut *</span><select onChange={(event) => field("status", event.target.value)} value={draft.status}>{statuses.map((status) => <option key={status}>{status}</option>)}</select></label>
          </div>
          <p className="account-editor-note">La modification réévalue automatiquement les budgets, le prévisionnel et les rapprochements liés.</p>
          {formError && <div className="account-form-error" role="alert">{formError}</div>}
          <footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : "Enregistrer et valider"}</button></footer>
        </form>
      </aside>
    </div>
  );
}

function InsightCard({ badge, badgeTone, description, progress, title }: {
  badge: string;
  badgeTone: "blue" | "success" | "warning";
  description: string;
  progress: number;
  title: string;
}) {
  const safeProgress = Math.max(0, Math.min(100, progress));
  return (
    <article className="card transaction-insight">
      <h2>{title}</h2>
      <p title={description}>{description}</p>
      <span className={`transaction-insight__badge transaction-insight__badge--${badgeTone}`}>{badge}</span>
      <div className="transaction-progress"><span style={{ width: `${safeProgress}%` }} /></div>
    </article>
  );
}

function shortAccount(transaction: TransactionRow): string {
  const bank = transaction.bank.trim();
  const name = transaction.accountName.trim();
  return bank ? `${bank} - ${name}` : name;
}

function categoryTone(category: string): "blue" | "cyan" | "green" | "muted" | "warning" {
  const value = category.toLocaleLowerCase("fr");
  if (value.includes("revenu") || value.includes("salaire")) return "green";
  if (value.includes("épargne") || value.includes("epargne")) return "cyan";
  if (value.includes("loisir") || value.includes("restaurant")) return "warning";
  if (value.includes("catégoriser") || value.includes("confirmer")) return "warning";
  if (value.includes("charge") || value.includes("assurance")) return "muted";
  return "blue";
}

function statusTone(status: string): "blue" | "green" | "muted" | "red" | "warning" {
  const value = status.toLocaleLowerCase("fr");
  if (value.includes("rapproch")) return "green";
  if (value.includes("revoir")) return "red";
  if (value.includes("catégoriser") || value.includes("confirmer")) return "warning";
  if (value.includes("valid") || value.includes("règle") || value.includes("regle")) return "blue";
  return "muted";
}

function signedMoney(value: number): string {
  if (value === 0) return currencyFormatter.format(value);
  return `${value > 0 ? "+ " : "- "}${currencyFormatter.format(Math.abs(value))}`;
}

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormatter.format(date);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Le moteur des transactions ne répond pas.";
}
