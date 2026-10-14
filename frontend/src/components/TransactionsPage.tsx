import { useEffect, useMemo, useState } from "react";

import { getTransactions } from "../api/client";
import type { TransactionRow, TransactionsSnapshot } from "../api/contracts";

interface TransactionsPageProps {
  token: string;
}

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

export function TransactionsPage({ token }: TransactionsPageProps) {
  const [snapshot, setSnapshot] = useState<TransactionsSnapshot>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [accountId, setAccountId] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

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

  return (
    <div className="transactions-page">
      <article className="card transactions-journal">
        <div className="transactions-heading"><h2>Journal des transactions</h2></div>
        <div className="transaction-filters" role="search">
          <input aria-label="Rechercher une transaction" onChange={(event) => setSearch(event.target.value)} placeholder="Recherche libellé, montant…" type="search" value={search} />
          <select aria-label="Filtrer par compte" onChange={(event) => setAccountId(event.target.value)} value={accountId}>
            <option value="all">Tous les comptes</option>
            {snapshot.accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
          <label><span>Du</span><input aria-label="Date de début" onChange={(event) => setDateFrom(event.target.value)} type="date" value={dateFrom} /></label>
          <label><span>Au</span><input aria-label="Date de fin" onChange={(event) => setDateTo(event.target.value)} type="date" value={dateTo} /></label>
          <span className="transaction-count">{visibleTransactions.length} opération{visibleTransactions.length > 1 ? "s" : ""}</span>
        </div>

        <div className="transactions-table-wrap">
          <table className="transactions-table">
            <thead><tr><th>Date</th><th>Compte</th><th>Libellé</th><th>Catégorie</th><th>Statut</th><th>Montant</th></tr></thead>
            <tbody>
              {visibleTransactions.length > 0 ? visibleTransactions.map((transaction) => (
                <TransactionLine key={transaction.id} transaction={transaction} />
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
    </div>
  );
}

function TransactionLine({ transaction }: { transaction: TransactionRow }) {
  return (
    <tr>
      <td>{formatDate(transaction.date)}</td>
      <td>{shortAccount(transaction)}</td>
      <td>{transaction.label}</td>
      <td><span className={`transaction-pill transaction-pill--${categoryTone(transaction.category)}`}>{transaction.category}</span></td>
      <td><span className={`transaction-pill transaction-pill--${statusTone(transaction.status)}`}>{transaction.status}</span></td>
      <td className={transaction.amount < 0 ? "transaction-amount transaction-amount--negative" : "transaction-amount transaction-amount--positive"}>{signedMoney(transaction.amount)}</td>
    </tr>
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
