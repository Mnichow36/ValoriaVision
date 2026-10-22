import { type FormEvent, type MouseEvent, useEffect, useMemo, useState } from "react";

import { bulkUpdateTransactions, cancelReconciliation, createTransaction, createTransactionCategorizationRule, deleteRecurrence, getForecast, getTransactions, updateTransaction } from "../api/client";
import type { ForecastSnapshot, RecurrenceActionResult, RecurrenceItem, TransactionActionResult, TransactionCreatePayload, TransactionEditPayload, TransactionRow, TransactionsSnapshot } from "../api/contracts";
import { BankImportPage } from "./BankImportPage";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";
import { ReconciledPill } from "./ReconciledPill";
import { RecurrenceEditor } from "./RecurrenceEditor";

interface TransactionsPageProps {
  createRequestKey: number;
  importRequestKey: number;
  onDataChanged: () => void;
  onNavigateSettings: () => void;
  onViewChange: (view: TransactionsView) => void;
  preferredImportAccountId?: number;
  token: string;
  view: TransactionsView;
}

export type TransactionsView = "journal" | "recurrences" | "import" | "history";

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

export function TransactionsPage({ createRequestKey, importRequestKey, onDataChanged, onNavigateSettings, onViewChange, preferredImportAccountId, token, view }: TransactionsPageProps) {
  const [snapshot, setSnapshot] = useState<TransactionsSnapshot>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [accountId, setAccountId] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [allDates, setAllDates] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({ key: "date", direction: "desc" });
  const [editing, setEditing] = useState<TransactionRow>();
  const [creating, setCreating] = useState(false);
  const [menu, setMenu] = useState<ContextMenuState>();

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

  function openRowMenu(event: MouseEvent, transaction: TransactionRow) {
    event.preventDefault();
    const badge = transaction.reconciliation;
    const items = [
      { label: "Modifier la transaction", onSelect: () => setEditing(transaction) },
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

  if (view === "recurrences") {
    return (
      <TransactionsRecurrences
        onDataChanged={onDataChanged}
        onViewChange={onViewChange}
        token={token}
      />
    );
  }

  return (
    <div className="transactions-page">
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
            <button aria-label="Désélectionner" className="transaction-bulk-clear" disabled={bulkBusy} onClick={() => setSelectedIds([])} type="button">×</button>
            {bulkError && <span className="transaction-bulk-error" role="alert">{bulkError}</span>}
          </div>
        )}

        <div className="transactions-table-wrap">
          <table className="transactions-table">
            <thead><tr>
              <th aria-sort={ariaSort(sort, "date")}><label className="transaction-select"><input aria-label="Sélectionner toutes les transactions affichées" checked={allVisibleSelected} onChange={toggleVisible} type="checkbox" /><SortButton label="Date" onSort={toggleSort} sort={sort} sortKey="date" /></label></th>
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
      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
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

function TransactionsRecurrences({
  onDataChanged,
  onViewChange,
  token,
}: {
  onDataChanged: () => void;
  onViewChange: (view: TransactionsView) => void;
  token: string;
}) {
  const [snapshot, setSnapshot] = useState<ForecastSnapshot>();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [accountId, setAccountId] = useState("all");
  const [horizonDays, setHorizonDays] = useState(15);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [editing, setEditing] = useState<RecurrenceItem>();
  const [editorOpen, setEditorOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<number>();

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getForecast(token, { accountId, horizonDays, scenario: "Réaliste" }, controller.signal)
      .then(setSnapshot)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les récurrences ne peuvent pas être chargées.");
        }
      });
    return () => controller.abort();
  }, [accountId, horizonDays, refreshKey, token]);

  const query = search.trim().toLocaleLowerCase("fr");
  const visibleRules = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.recurrences.filter((item) => {
      const matchesAccount = accountId === "all" || item.accountId === Number(accountId);
      const matchesStatus = status === "all" || (status === "active" ? item.status === "Actif" : item.status !== "Actif");
      const matchesSearch = !query || [
        item.name,
        item.accountName,
        item.bank,
        item.category,
        item.frequency,
        item.scenario,
      ].some((value) => value.toLocaleLowerCase("fr").includes(query));
      return matchesAccount && matchesStatus && matchesSearch;
    });
  }, [accountId, query, snapshot, status]);

  const occurrences = useMemo(() => {
    if (!snapshot) return [];
    return snapshot.series.selected
      .flatMap((point) => point.events)
      .filter((event) => event.source.startsWith("Récurrence"))
      .filter((event) => !query || [
        event.name,
        event.account,
        event.category,
        event.source,
        event.scenario,
      ].some((value) => value.toLocaleLowerCase("fr").includes(query)))
      .sort((left, right) => left.date.localeCompare(right.date) || left.name.localeCompare(right.name, "fr"));
  }, [query, snapshot]);

  const recurringById = useMemo(
    () => new Map((snapshot?.recurrences ?? []).map((item) => [item.id, item])),
    [snapshot],
  );
  const totalIn = occurrences.reduce((sum, event) => sum + Math.max(event.amount, 0), 0);
  const totalOut = occurrences.reduce((sum, event) => sum + Math.abs(Math.min(event.amount, 0)), 0);

  function completed(result: RecurrenceActionResult) {
    setDeletingId(undefined);
    setEditorOpen(false);
    setEditing(undefined);
    setNotice(result.message);
    setRefreshKey((key) => key + 1);
    onDataChanged();
  }

  async function remove(item: RecurrenceItem) {
    if (!window.confirm(`Supprimer définitivement la récurrence « ${item.name} » ?`)) return;
    setDeletingId(item.id);
    setError(undefined);
    try {
      completed(await deleteRecurrence(token, item.id));
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La récurrence ne peut pas être supprimée.");
      setDeletingId(undefined);
    }
  }

  if (error && !snapshot) {
    return (
      <div className="transactions-page">
        <section className="error-state">
          <strong>Les récurrences ne peuvent pas être affichées.</strong>
          <p>{error}</p>
          <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
        </section>
      </div>
    );
  }

  if (!snapshot) {
    return (
      <div className="transactions-page">
        <div className="loading-state"><span aria-hidden="true" />Calcul des échéances dans l’horizon…</div>
      </div>
    );
  }

  return (
    <div className="transactions-page recurrence-workspace">
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      {error && <p className="account-form-error" role="alert">{error}</p>}

      <article className="card recurrence-catalog">
        <div className="recurrence-catalog__heading">
          <div>
            <span className="eyebrow">Transactions · Récurrences</span>
            <h2>Échéances et règles récurrentes</h2>
            <p>Du {formatDate(snapshot.filters.startDate)} au {formatDate(snapshot.filters.endDate)} · une seule source de données avec la courbe de trésorerie.</p>
          </div>
          <button onClick={() => {
            setEditing(undefined);
            setEditorOpen(true);
          }} type="button">Nouvelle récurrence</button>
        </div>

        <div className="recurrence-catalog__filters">
          <input aria-label="Rechercher une récurrence" onChange={(event) => setSearch(event.target.value)} placeholder="Recherche libellé, compte, catégorie…" type="search" value={search} />
          <select aria-label="Compte des récurrences" onChange={(event) => setAccountId(event.target.value)} value={accountId}>
            <option value="all">Tous les comptes</option>
            {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.bank ? `${account.bank} — ` : ""}{account.name}</option>)}
          </select>
          <select aria-label="Horizon des récurrences" onChange={(event) => setHorizonDays(Number(event.target.value))} value={horizonDays}>
            <option value={15}>J−5 à J+10</option>
            <option value={30}>J−5 à J+25</option>
            <option value={60}>J−5 à J+55</option>
            <option value={90}>J−5 à J+85</option>
          </select>
          <select aria-label="Statut des règles récurrentes" onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="all">Tous les statuts</option>
            <option value="active">Actives</option>
            <option value="inactive">Inactives</option>
          </select>
        </div>

        <section aria-label="Synthèse des récurrences" className="recurrence-catalog__summary">
          <div><span>Règles affichées</span><strong>{visibleRules.length}</strong></div>
          <div><span>Échéances dans l’horizon</span><strong>{occurrences.length}</strong></div>
          <div><span>Recettes prévues</span><strong className="positive">{signedMoney(totalIn)}</strong></div>
          <div><span>Dépenses prévues</span><strong className="negative">{signedMoney(-totalOut)}</strong></div>
        </section>

        <section className="recurrence-occurrences">
          <div className="recurrence-section-heading">
            <div><h3>Échéances dans l’horizon</h3><p>Toutes les opérations récurrentes qui impactent la courbe affichée.</p></div>
            <span>{occurrences.length} opération{occurrences.length > 1 ? "s" : ""}</span>
          </div>
          <div className="recurrence-table-wrap">
            <table className="recurrence-table">
              <thead><tr><th>Date</th><th>Opération</th><th>Compte</th><th>Catégorie / cadence</th><th>Statut</th><th>Montant</th></tr></thead>
              <tbody>
                {occurrences.map((event, index) => {
                  const rule = event.recurringId === null ? undefined : recurringById.get(event.recurringId);
                  return (
                    <tr key={`${event.date}-${event.recurringId ?? event.name}-${index}`}>
                      <td><strong>{formatDate(event.date)}</strong>{event.originalDate && event.originalDate !== event.date && <small>Initialement {formatDate(event.originalDate)}</small>}</td>
                      <td><strong>{event.name}</strong><small>{event.scenario && event.scenario !== "Tous" ? `Scénario ${event.scenario}` : "Tous scénarios"}</small></td>
                      <td>{event.account}</td>
                      <td><span>{event.category}</span>{rule && <small>{rule.frequency}</small>}</td>
                      <td><span className={event.source === "Récurrence décalée" ? "recurrence-status recurrence-status--rescheduled" : "recurrence-status recurrence-status--active"}>{event.source === "Récurrence décalée" ? "Décalée" : "Prévue"}</span></td>
                      <td className={event.amount >= 0 ? "positive recurrence-table__amount" : "negative recurrence-table__amount"}>{signedMoney(event.amount)}</td>
                    </tr>
                  );
                })}
                {occurrences.length === 0 && <tr><td className="transactions-empty" colSpan={6}>Aucune échéance récurrente dans cet horizon.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>

        <section className="recurrence-rules">
          <div className="recurrence-section-heading">
            <div><h3>Règles récurrentes</h3><p>Modifiez le calendrier, le montant, le compte ou supprimez une règle.</p></div>
            <span>{visibleRules.length} règle{visibleRules.length > 1 ? "s" : ""}</span>
          </div>
          <div className="recurrence-rules__grid">
            {visibleRules.map((item) => (
              <article className="recurrence-rule-card" key={item.id}>
                <div className="recurrence-rule-card__top">
                  <div><strong>{item.name}</strong><span>{item.bank ? `${item.bank} · ` : ""}{item.accountName}</span></div>
                  <b className={item.direction === "Crédit" ? "positive" : "negative"}>{signedMoney(item.direction === "Crédit" ? item.amount : -item.amount)}</b>
                </div>
                <div className="recurrence-rule-card__meta">
                  <span>{item.category}</span>
                  <span>{item.frequency}</span>
                  <span>{item.scenario}</span>
                  <span className={item.status === "Actif" ? "recurrence-status recurrence-status--active" : "recurrence-status"}>{item.status}</span>
                </div>
                <div className="recurrence-rule-card__dates">
                  <div><span>Prochaine échéance</span><strong>{item.nextOccurrenceDate ? formatDate(item.nextOccurrenceDate) : "Aucune"}</strong></div>
                  <div><span>Dans l’horizon</span><strong>{item.forecastOccurrenceCount}</strong></div>
                </div>
                {item.rescheduledOccurrenceCount > 0 && <p>{item.rescheduledOccurrenceCount} échéance{item.rescheduledOccurrenceCount > 1 ? "s" : ""} décalée{item.rescheduledOccurrenceCount > 1 ? "s" : ""} · prochaine le {formatDate(item.nextRescheduledDate)}</p>}
                <div className="recurrence-rule-card__actions">
                  <button className="secondary-button" disabled={Boolean(deletingId)} onClick={() => {
                    setEditing(item);
                    setEditorOpen(true);
                  }} type="button">Modifier</button>
                  <button className="danger-button" disabled={Boolean(deletingId)} onClick={() => void remove(item)} type="button">{deletingId === item.id ? "Suppression…" : "Supprimer"}</button>
                </div>
              </article>
            ))}
            {visibleRules.length === 0 && <div className="forecast-day-details__empty"><strong>Aucune règle trouvée</strong><p>Modifiez les filtres ou créez une nouvelle récurrence.</p></div>}
          </div>
        </section>
      </article>

      {editorOpen && (
        <RecurrenceEditor
          accounts={snapshot.accounts}
          categories={snapshot.categories}
          defaultAccountId={accountId}
          defaultScenario="Réaliste"
          key={editing?.id ?? "new"}
          onClose={() => {
            setEditorOpen(false);
            setEditing(undefined);
          }}
          onCompleted={completed}
          recurrence={editing}
          token={token}
        />
      )}
    </div>
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
  const hasDistinctBankLabel = Boolean(transaction.beneficiary)
    && transaction.beneficiary.trim().toLocaleLowerCase("fr") !== transaction.label.trim().toLocaleLowerCase("fr");
  return (
    <tr
      aria-label={`Modifier la transaction ${transaction.label}`}
      className={selected ? "transaction-row-action transaction-row-action--selected" : "transaction-row-action"}
      onClick={onEdit}
      onContextMenu={onContextMenu}
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
