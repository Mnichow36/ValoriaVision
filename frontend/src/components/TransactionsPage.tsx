import { useCanWrite } from "../permissions";
import { type FormEvent, type MouseEvent, useEffect, useMemo, useState } from "react";

import { bulkUpdateTransactions, getRuleSuggestions, cancelReconciliation, createTransaction, createTransactionCategorizationRule, getTransactions, updateTransaction } from "../api/client";
import type { ReconciliationAccount, TransactionActionResult, TransactionCreatePayload, TransactionEditPayload, TransactionRow, TransactionsSnapshot } from "../api/contracts";
import { BankImportPage } from "./BankImportPage";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";
import { ReconciledPill } from "./ReconciledPill";
import { RecurrenceFromTransaction } from "./RecurrenceFromTransaction";
import { RecurrenceOccurrencesTab } from "./RecurrenceOccurrencesTab";
import { RecurrenceRulesTab } from "./RecurrenceRulesTab";
import { ReconciliationPage } from "./ReconciliationPage";
import { RuleSuggestionsTab } from "./RuleSuggestionsTab";

interface TransactionsPageProps {
  accountFocus?: { accountId?: number; category?: string; key: number };
  createRequestKey: number;
  importRequestKey: number;
  onDataChanged: () => void;
  onNavigateSettings: () => void;
  onViewChange: (view: TransactionsView) => void;
  preferredImportAccountId?: number;
  reconciliationBadge?: number;
  reconciliationRefreshKey?: number;
  ruleCreateRequestKey: number;
  token: string;
  view: TransactionsView;
}

export type TransactionsView = "journal" | "reconciliation" | "recurrences" | "rules" | "suggestions" | "import" | "history";

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

export function TransactionsPage({ accountFocus, createRequestKey, importRequestKey, onDataChanged, onNavigateSettings, onViewChange, preferredImportAccountId, reconciliationBadge = 0, reconciliationRefreshKey = 0, ruleCreateRequestKey, token, view }: TransactionsPageProps) {
  const canWrite = useCanWrite();
  const [snapshot, setSnapshot] = useState<TransactionsSnapshot>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [accountId, setAccountId] = useState(accountFocus?.accountId !== undefined ? String(accountFocus.accountId) : "all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [allDates, setAllDates] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({ key: "date", direction: "desc" });
  const [editing, setEditing] = useState<TransactionRow>();
  const [recurrenceFrom, setRecurrenceFrom] = useState<TransactionRow>();
  const [creating, setCreating] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    getRuleSuggestions(token, 0.9, controller.signal)
      .then((data) => setSuggestionBadge(data.suggestions.filter((item) => item.recommended && item.matches > 0).length))
      .catch(() => undefined);
    return () => controller.abort();
  }, [token, refreshKey]);

  useEffect(() => {
    if (!accountFocus) return;
    setAccountId(accountFocus.accountId === undefined ? "all" : String(accountFocus.accountId));
    setSearch("");
    setCategoryFilter(accountFocus.category ?? "all");
    setStatusFilter("all");
    setAllDates(true);
  }, [accountFocus]);
  const [menu, setMenu] = useState<ContextMenuState>();
  const [suggestionBadge, setSuggestionBadge] = useState(0);
  const [deleting, setDeleting] = useState<TransactionRow[]>();
  const [reconAccountId, setReconAccountId] = useState("all");
  const [reconAccounts, setReconAccounts] = useState<ReconciliationAccount[]>([]);
  const [reconStatus, setReconStatus] = useState("active");
  const [reconRulesKey, setReconRulesKey] = useState(0);
  const [reconRefresh, setReconRefresh] = useState(0);

  useEffect(() => {
    if (createRequestKey > 0) setCreating(true);
  }, [createRequestKey]);
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
        transaction.beneficiary,
        transaction.label,
        transaction.category,
        transaction.accountName,
        transaction.bank,
        String(transaction.amount),
      ].some((value) => value.toLocaleLowerCase("fr").includes(query));
      const matchesAccount = accountId === "all" || transaction.accountId === Number(accountId);
      const matchesFrom = allDates || !dateFrom || transaction.date >= dateFrom;
      const matchesTo = allDates || !dateTo || transaction.date <= dateTo;
      const matchesCategory = categoryFilter === "all" || transaction.category === categoryFilter;
      const matchesStatus = statusFilter === "all"
        || (statusFilter === RECONCILED_FILTER ? Boolean(transaction.reconciliation?.reconciled) : transaction.status === statusFilter);
      return matchesSearch && matchesAccount && matchesFrom && matchesTo && matchesCategory && matchesStatus;
    }).sort((left, right) => compareTransactions(left, right, sort.key, sort.direction));
  }, [accountId, allDates, categoryFilter, dateFrom, dateTo, search, snapshot, sort, statusFilter]);

  const categoryOptions = useMemo(
    () => Array.from(new Set((snapshot?.transactions ?? []).map((transaction) => transaction.category).filter(Boolean))).sort((a, b) => a.localeCompare(b, "fr")),
    [snapshot],
  );
  const statusOptions = useMemo(
    () => Array.from(new Set((snapshot?.transactions ?? []).map((transaction) => transaction.status).filter(Boolean))).sort((a, b) => a.localeCompare(b, "fr")),
    [snapshot],
  );
  const hasActiveFilter = categoryFilter !== "all" || statusFilter !== "all" || accountId !== "all" || search.trim() !== "";

  function toggleSort(key: SortKey) {
    setSort((current) => current.key === key
      ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
      : { key, direction: key === "date" || key === "amount" ? "desc" : "asc" });
  }

  function resetFilters() {
    clearSelectionForFilter(() => {
      setSearch("");
      setAccountId("all");
      setCategoryFilter("all");
      setStatusFilter("all");
    });
  }

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

  async function runBulkAction(action: "category" | "validate" | "delete") {
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

  function openRowMenu(event: MouseEvent, transaction: TransactionRow) {
    event.preventDefault();
    const badge = transaction.reconciliation;
    const group = selectedIds.includes(transaction.id) && visibleSelectedIds.length > 1
      ? visibleTransactions.filter((row) => selectedIds.includes(row.id))
      : [transaction];
    const items = [
      { label: "Modifier la transaction", onSelect: () => setEditing(transaction) },
      ...(group.length === 1
        ? [{ label: "Créer une récurrence…", onSelect: () => setRecurrenceFrom(transaction) }]
        : []),
      ...(badge?.reconciled && badge.occurrenceId
        ? [{
            label: "Annuler le rapprochement",
            danger: true,
            onSelect: () => {
              cancelReconciliation(token, { occurrenceId: badge.occurrenceId as number, transactionId: transaction.id })
                .then((result) => {
                  setNotice(result.message);
                  setRefreshKey((key) => key + 1);
                  onDataChanged();
                })
                .catch((cause: unknown) => setNotice(errorMessage(cause)));
            },
          }]
        : []),
    ];
    items.push({
      label: group.length > 1 ? `Supprimer les ${group.length} transactions…` : "Supprimer la transaction…",
      danger: true,
      onSelect: () => setDeleting(group),
    } as (typeof items)[number]);
    setMenu({ x: event.clientX, y: event.clientY, items });
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

  if (view === "import" || view === "history") {
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

  if (view === "reconciliation") {
    return (
      <>
        <div className="reconciliation-toolbar">
          <TransactionsTabs badge={reconciliationBadge} onViewChange={onViewChange} suggestionBadge={suggestionBadge} view={view} />
          <div className="header-actions reconciliation-toolbar__filters">
            <select aria-label="Compte des rapprochements" onChange={(event) => setReconAccountId(event.target.value)} value={reconAccountId}>
              <option value="all">Tous les comptes</option>
              {reconAccounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} - ` : ""}{account.name}</option>)}
            </select>
            <select aria-label="Statut des rapprochements" onChange={(event) => setReconStatus(event.target.value)} value={reconStatus}>
              <option value="active">À traiter</option>
              <option value="to_review">À vérifier</option>
              <option value="matched">Rapprochées</option>
              <option value="amount_gap">Écart de montant</option>
              <option value="ignored">Ignorées / annulées</option>
              <option value="finalized">Finalisées</option>
              <option value="all">Tous les statuts</option>
            </select>
            <button className="secondary-button" onClick={() => setReconRulesKey((key) => key + 1)} type="button">Écarts</button>
            <button onClick={() => setReconRefresh((key) => key + 1)} type="button">Actualiser</button>
          </div>
        </div>
        <ReconciliationPage
          accountId={reconAccountId}
          onAccountsChange={setReconAccounts}
          refreshKey={reconciliationRefreshKey + reconRefresh}
          rulesRequestKey={reconRulesKey}
          status={reconStatus}
          token={token}
        />
      </>
    );
  }

  if (view === "suggestions") {
    return (
      <>
        <TransactionsTabs badge={reconciliationBadge} onViewChange={onViewChange} suggestionBadge={suggestionBadge} view={view} />
        <RuleSuggestionsTab
          categories={snapshot.categories}
          onApplied={() => {
            setRefreshKey((key) => key + 1);
            onDataChanged();
          }}
          token={token}
        />
      </>
    );
  }

  if (view === "recurrences" || view === "rules") {
    return (
      <>
        <TransactionsTabs badge={reconciliationBadge} onViewChange={onViewChange} suggestionBadge={suggestionBadge} view={view} />
        {view === "recurrences"
          ? <RecurrenceOccurrencesTab onDataChanged={onDataChanged} token={token} />
          : <RecurrenceRulesTab createRequestKey={ruleCreateRequestKey} onDataChanged={onDataChanged} token={token} />}
      </>
    );
  }

  return (
    <div className="transactions-page">
      <div className="transactions-topbar">
        <TransactionsTabs badge={reconciliationBadge} onViewChange={onViewChange} suggestionBadge={suggestionBadge} view={view} />
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
      </div>
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      <article className="card transactions-journal">
        <div className="transactions-heading"><h2>Journal des transactions</h2></div>
        <div className="transaction-filters" role="search">
          <input aria-label="Rechercher une transaction" onChange={(event) => clearSelectionForFilter(() => setSearch(event.target.value))} placeholder="Recherche tiers, libellé, montant…" type="search" value={search} />
          <select aria-label="Filtrer par compte" onChange={(event) => clearSelectionForFilter(() => setAccountId(event.target.value))} value={accountId}>
            <option value="all">Tous les comptes</option>
            {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
          <label><span>Du</span><input aria-label="Date de début" disabled={allDates} onChange={(event) => clearSelectionForFilter(() => setDateFrom(event.target.value))} type="date" value={dateFrom} /></label>
          <label><span>Au</span><input aria-label="Date de fin" disabled={allDates} onChange={(event) => clearSelectionForFilter(() => setDateTo(event.target.value))} type="date" value={dateTo} /></label>
          <label className="transaction-all-dates"><input aria-label="Afficher toutes les dates" checked={allDates} onChange={(event) => clearSelectionForFilter(() => setAllDates(event.target.checked))} type="checkbox" /><span>Toutes dates</span></label>
          <span className="transaction-count">{visibleTransactions.length} opération{visibleTransactions.length > 1 ? "s" : ""}</span>
        </div>
        <div className="transaction-filters transaction-filters--secondary" role="group" aria-label="Filtres complémentaires">
          <select aria-label="Filtrer par catégorie" onChange={(event) => clearSelectionForFilter(() => setCategoryFilter(event.target.value))} value={categoryFilter}>
            <option value="all">Toutes les catégories</option>
            {categoryOptions.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
          <select aria-label="Filtrer par statut" onChange={(event) => clearSelectionForFilter(() => setStatusFilter(event.target.value))} value={statusFilter}>
            <option value="all">Tous les statuts</option>
            <option value={RECONCILED_FILTER}>Rapprochées (liées à une prévision)</option>
            {statusOptions.map((status) => <option key={status} value={status}>{status}</option>)}
          </select>
          {hasActiveFilter && <button className="transaction-filter-reset" onClick={resetFilters} type="button">Réinitialiser les filtres</button>}
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
            <button className="danger-button" disabled={bulkBusy} onClick={() => setDeleting(visibleTransactions.filter((row) => selectedIds.includes(row.id)))} type="button">Supprimer…</button>
            <button aria-label="Désélectionner" className="transaction-bulk-clear" disabled={bulkBusy} onClick={() => setSelectedIds([])} type="button">×</button>
            {bulkError && <span className="transaction-bulk-error" role="alert">{bulkError}</span>}
          </div>
        )}

        <div className="transactions-table-wrap">
          <table className="transactions-table">
            <thead><tr>
              <th aria-sort={ariaSort(sort, "date")}><label className="transaction-select">{canWrite && <input aria-label="Sélectionner toutes les transactions affichées" checked={allVisibleSelected} onChange={toggleVisible} type="checkbox" />}<SortButton label="Date" onSort={toggleSort} sort={sort} sortKey="date" /></label></th>
              <th aria-sort={ariaSort(sort, "account")}><SortButton label="Compte" onSort={toggleSort} sort={sort} sortKey="account" /></th>
              <th aria-sort={ariaSort(sort, "label")}><SortButton label="Tiers / Libellé" onSort={toggleSort} sort={sort} sortKey="label" /></th>
              <th aria-sort={ariaSort(sort, "category")}><SortButton label="Catégorie" onSort={toggleSort} sort={sort} sortKey="category" /></th>
              <th aria-sort={ariaSort(sort, "status")}><SortButton label="Statut" onSort={toggleSort} sort={sort} sortKey="status" /></th>
              <th aria-sort={ariaSort(sort, "amount")}><SortButton label="Montant" onSort={toggleSort} sort={sort} sortKey="amount" /></th>
            </tr></thead>
            <tbody>
              {visibleTransactions.length > 0 ? visibleTransactions.map((transaction) => (
                <TransactionLine
                  key={transaction.id}
                  onContextMenu={(event) => openRowMenu(event, transaction)}
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

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
      {deleting && (
        <DeleteTransactionsDrawer
          items={deleting}
          onClose={() => setDeleting(undefined)}
          onConfirm={async () => {
            const result = await bulkUpdateTransactions(token, deleting.map((row) => row.id), "delete");
            setDeleting(undefined);
            setSelectedIds([]);
            setNotice(result.message);
            setRefreshKey((key) => key + 1);
            onDataChanged();
          }}
        />
      )}
      {creating && (
        <TransactionCreator
          defaultAccountId={accountId !== "all" ? Number(accountId) : undefined}
          onClose={() => setCreating(false)}
          onCompleted={(result) => {
            setCreating(false);
            setNotice(result.message);
            setRefreshKey((key) => key + 1);
            onDataChanged();
          }}
          snapshot={snapshot}
          token={token}
        />
      )}
      {recurrenceFrom && (
        <RecurrenceFromTransaction
          onClose={() => setRecurrenceFrom(undefined)}
          onCompleted={(result) => {
            setRecurrenceFrom(undefined);
            setNotice(result.message);
            onDataChanged();
          }}
          token={token}
          transaction={recurrenceFrom}
        />
      )}
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

const TRANSACTION_TABS: { view: TransactionsView; label: string }[] = [
  { view: "journal", label: "Opérations" },
  { view: "reconciliation", label: "Rapprochements" },
  { view: "recurrences", label: "Récurrences" },
  { view: "rules", label: "Règles de récurrence" },
  { view: "suggestions", label: "Suggestions de catégorisation" },
];

function TransactionsTabs({ badge = 0, onViewChange, suggestionBadge = 0, view }: { badge?: number; onViewChange: (view: TransactionsView) => void; suggestionBadge?: number; view: TransactionsView }) {
  return (
    <nav aria-label="Sections des transactions" className="transactions-tabs" role="tablist">
      {TRANSACTION_TABS.map((tab) => (
        <button aria-selected={view === tab.view} className={view === tab.view ? "transactions-tab transactions-tab--active" : "transactions-tab"} key={tab.view} onClick={() => onViewChange(tab.view)} role="tab" type="button">{tab.label}{tab.view === "reconciliation" && badge > 0 && <span aria-label={`${badge} à traiter`} className="transactions-tab__badge">{badge}</span>}{tab.view === "suggestions" && suggestionBadge > 0 && <span aria-label={`${suggestionBadge} suggestions`} className="transactions-tab__badge">{suggestionBadge}</span>}</button>
      ))}
    </nav>
  );
}

type SortKey = "date" | "account" | "label" | "category" | "status" | "amount";
const RECONCILED_FILTER = "__reconciled__";

function ariaSort(sort: { key: SortKey; direction: "asc" | "desc" }, key: SortKey): "ascending" | "descending" | "none" {
  if (sort.key !== key) return "none";
  return sort.direction === "asc" ? "ascending" : "descending";
}

function SortButton({ label, onSort, sort, sortKey }: {
  label: string;
  onSort: (key: SortKey) => void;
  sort: { key: SortKey; direction: "asc" | "desc" };
  sortKey: SortKey;
}) {
  const active = sort.key === sortKey;
  return (
    <button
      className={active ? "transaction-sort transaction-sort--active" : "transaction-sort"}
      onClick={(event) => { event.preventDefault(); event.stopPropagation(); onSort(sortKey); }}
      title={`Trier par ${label.toLocaleLowerCase("fr")}`}
      type="button"
    >
      {label}<span aria-hidden="true">{active ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}</span>
    </button>
  );
}

function compareTransactions(left: TransactionRow, right: TransactionRow, key: SortKey, direction: "asc" | "desc"): number {
  const factor = direction === "asc" ? 1 : -1;
  let result = 0;
  if (key === "date") result = left.date.localeCompare(right.date);
  else if (key === "amount") result = left.amount - right.amount;
  else if (key === "account") result = shortAccount(left).localeCompare(shortAccount(right), "fr");
  else if (key === "label") result = (left.beneficiary || left.label).localeCompare(right.beneficiary || right.label, "fr");
  else if (key === "category") result = left.category.localeCompare(right.category, "fr");
  else if (key === "status") result = left.status.localeCompare(right.status, "fr");
  if (result !== 0) return result * factor;
  // Départage stable : date récente d'abord, puis identifiant.
  return right.date.localeCompare(left.date) || right.id - left.id;
}

function TransactionLine({ onContextMenu, onEdit, onToggle, selected, transaction }: { onContextMenu: (event: MouseEvent) => void; onEdit: () => void; onToggle: () => void; selected: boolean; transaction: TransactionRow }) {
  const canWrite = useCanWrite();
  const hasDistinctBankLabel = Boolean(transaction.beneficiary)
    && transaction.beneficiary.trim().toLocaleLowerCase("fr") !== transaction.label.trim().toLocaleLowerCase("fr");
  return (
    <tr
      aria-label={canWrite ? `Modifier la transaction ${transaction.label}` : transaction.label}
      className={selected ? "transaction-row-action transaction-row-action--selected" : "transaction-row-action"}
      onClick={canWrite ? onEdit : undefined}
      onContextMenu={onContextMenu}
      onKeyDown={(event) => {
        if (canWrite && (event.key === "Enter" || event.key === " ")) {
          event.preventDefault();
          onEdit();
        }
      }}
      tabIndex={0}
      title={canWrite ? "Ouvrir et modifier cette transaction" : undefined}
    >
      <td>{canWrite ? <label className="transaction-select" onClick={(event) => event.stopPropagation()}><input aria-label={`Sélectionner ${transaction.label}`} checked={selected} onChange={onToggle} type="checkbox" />{formatDate(transaction.date)}</label> : formatDate(transaction.date)}</td>
      <td>{shortAccount(transaction)}</td>
      <td><div className="transaction-counterparty"><strong>{transaction.beneficiary || transaction.label}</strong>{hasDistinctBankLabel && <small title={transaction.label}>{transaction.label}</small>}</div></td>
      <td><span className={`transaction-pill transaction-pill--${categoryTone(transaction.category)}`}>{transaction.category}</span></td>
      <td><span className={`transaction-pill transaction-pill--${statusTone(transaction.status)}`}>{transaction.status}</span> <ReconciledPill badge={transaction.reconciliation} /></td>
      <td className={transaction.amount < 0 ? "transaction-amount transaction-amount--negative" : "transaction-amount transaction-amount--positive"}>{signedMoney(transaction.amount)}</td>
    </tr>
  );
}

function TransactionCreator({ defaultAccountId, onClose, onCompleted, snapshot, token }: {
  defaultAccountId?: number;
  onClose: () => void;
  onCompleted: (result: TransactionActionResult) => void;
  snapshot: TransactionsSnapshot;
  token: string;
}) {
  const activeAccounts = snapshot.accounts.filter((account) => account.status === "Actif");
  const [draft, setDraft] = useState<TransactionCreatePayload>({
    accountId: activeAccounts.find((account) => account.id === defaultAccountId)?.id ?? activeAccounts[0]?.id ?? 0,
    date: new Date().toISOString().slice(0, 10),
    label: "",
    beneficiary: "",
    category: "",
    direction: "Débit",
    amount: 0,
  });
  const [amountText, setAmountText] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  function field<Key extends keyof TransactionCreatePayload>(key: Key, value: TransactionCreatePayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const amount = Number(amountText.replace(",", "."));
    if (!Number.isFinite(amount) || amount <= 0) {
      setFormError("Indiquez un montant supérieur à zéro.");
      return;
    }
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(await createTransaction(token, { ...draft, amount }));
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Transactions"
      footer={(
        <>
          <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button>
          <button disabled={busy || activeAccounts.length === 0} form="transaction-create-form" type="submit">{busy ? "Enregistrement…" : "Ajouter la transaction"}</button>
        </>
      )}
      onClose={onClose}
      title="Nouvelle transaction"
    >
      <form className="transaction-create-form" id="transaction-create-form" onSubmit={(event) => void submit(event)}>
        <div className="account-editor-grid">
          <label className="account-field account-field--wide"><span>Compte *</span><select onChange={(event) => field("accountId", Number(event.target.value))} value={draft.accountId}>{activeAccounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}</select></label>
          <label className="account-field"><span>Date *</span><input onChange={(event) => field("date", event.target.value)} required type="date" value={draft.date} /></label>
          <label className="account-field"><span>Sens *</span><select onChange={(event) => field("direction", event.target.value as "Débit" | "Crédit")} value={draft.direction}><option value="Débit">Dépense (débit)</option><option value="Crédit">Recette (crédit)</option></select></label>
          <label className="account-field"><span>Montant (EUR) *</span><input autoFocus inputMode="decimal" onChange={(event) => setAmountText(event.target.value)} placeholder="0,00" required value={amountText} /></label>
          <label className="account-field"><span>Catégorie</span><select onChange={(event) => field("category", event.target.value)} value={draft.category}><option value="">À catégoriser</option>{snapshot.categories.filter((category) => category.name && category.name !== "À catégoriser").map((category) => <option key={category.name} value={category.name}>{category.name}</option>)}</select></label>
          <label className="account-field account-field--wide"><span>Libellé *</span><input maxLength={240} onChange={(event) => field("label", event.target.value)} placeholder="Ex. Carte — boulangerie" required value={draft.label} /></label>
          <label className="account-field account-field--wide"><span>Tiers (facultatif)</span><input maxLength={120} onChange={(event) => field("beneficiary", event.target.value)} placeholder="Ex. Boulangerie Martin" value={draft.beneficiary} /><small>Laissé vide, le tiers est déduit du libellé.</small></label>
        </div>
        <p className="account-editor-note">La transaction est enregistrée comme saisie manuelle. Elle met à jour immédiatement le solde du compte, les budgets, le prévisionnel et les propositions de rapprochement.</p>
        {formError && <div className="account-form-error" role="alert">{formError}</div>}
      </form>
    </SideDrawer>
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
  const [rememberCategory, setRememberCategory] = useState(false);
  const [ruleValue, setRuleValue] = useState(transaction.ruleSuggestion);
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
    const selectedCategory = snapshot.categories.find((category) => category.name === draft.category);
    if (rememberCategory && !selectedCategory?.id) {
      setFormError("La catégorie choisie ne permet pas de créer une règle.");
      return;
    }
    if (rememberCategory && !ruleValue.trim()) {
      setFormError("Indiquez le nom du tiers à rechercher.");
      return;
    }

    setBusy(true);
    setFormError(undefined);
    let transactionSaved = false;
    try {
      const result = await updateTransaction(token, transaction.id, draft);
      transactionSaved = true;
      if (rememberCategory && selectedCategory) {
        const rule = await createTransactionCategorizationRule(
          token,
          transaction.id,
          selectedCategory.id,
          ruleValue.trim(),
        );
        onCompleted({ ...result, message: `${result.message} ${rule.message}` });
        return;
      }
      onCompleted(result);
    } catch (cause: unknown) {
      const message = errorMessage(cause);
      setFormError(transactionSaved
        ? `La transaction est enregistrée, mais la règle n’a pas pu être créée : ${message}`
        : message);
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
          {draft.category && (
            <div className="transaction-rule-option">
              <label className="transaction-rule-toggle">
                <input checked={rememberCategory} onChange={(event) => setRememberCategory(event.target.checked)} type="checkbox" />
                <span>
                  <strong>Mémoriser cette catégorisation</strong>
                  <small>Les prochaines opérations similaires de ce compte seront classées automatiquement.</small>
                </span>
              </label>
              {rememberCategory && (
                <label className="transaction-rule-value">
                  <span>Nom du tiers à rechercher *</span>
                  <input
                    autoComplete="off"
                    maxLength={120}
                    onChange={(event) => setRuleValue(event.target.value)}
                    placeholder="Ex. LIDL"
                    required
                    value={ruleValue}
                  />
                  <small>Les références de carte, dates et numéros doivent être exclus.</small>
                </label>
              )}
            </div>
          )}
          <p className="account-editor-note">La modification réévalue automatiquement les budgets, le prévisionnel et les rapprochements liés.</p>
          {formError && <div className="account-form-error" role="alert">{formError}</div>}
          <footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : "Enregistrer et valider"}</button></footer>
        </form>
      </aside>
    </div>
  );
}

function DeleteTransactionsDrawer({ items, onClose, onConfirm }: { items: TransactionRow[]; onClose: () => void; onConfirm: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const reconciled = items.filter((row) => row.reconciliation?.reconciled).length;
  const plural = items.length > 1;

  async function confirm() {
    setBusy(true);
    setError(undefined);
    try {
      await onConfirm();
    } catch (cause: unknown) {
      setError(errorMessage(cause));
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Transactions"
      footer={(<><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button className="danger-button" disabled={busy} onClick={() => void confirm()} type="button">{busy ? "Suppression…" : plural ? `Supprimer ${items.length} transactions` : "Supprimer"}</button></>)}
      onClose={onClose}
      title={plural ? `Supprimer ${items.length} transactions` : "Supprimer cette transaction"}
    >
      <p className="drawer-help">La suppression est définitive : les soldes, les budgets et le prévisionnel sont recalculés.</p>
      {reconciled > 0 && <p className="drawer-help">{reconciled} transaction{reconciled > 1 ? "s sont rapprochées" : " est rapprochée"} : le rapprochement sera annulé et la prévision correspondante redeviendra « Prévue » ou « En retard ».</p>}
      <ul className="drawer-list">{items.map((row) => <li key={row.id}>{formatDate(row.date)} · {row.beneficiary || row.label} · {signedMoney(row.amount)}</li>)}</ul>
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
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
      <div className="transaction-insight__head"><h2>{title}</h2><span className={`transaction-insight__badge transaction-insight__badge--${badgeTone}`}>{badge}</span></div>
      <p title={description}>{description}</p>
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
