import { useEffect, useMemo, useState } from "react";

import { getAccounts } from "../api/client";
import type { AccountOverview, AccountsSnapshot } from "../api/contracts";

type AccountsView = "accounts" | "balances" | "imports";

interface AccountsPageProps {
  statusFilter: string;
  token: string;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  minimumFractionDigits: 2,
});

const shortDateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
});

const longDateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function AccountsPage({ statusFilter, token }: AccountsPageProps) {
  const [snapshot, setSnapshot] = useState<AccountsSnapshot>();
  const [selectedId, setSelectedId] = useState<number>();
  const [view, setView] = useState<AccountsView>("accounts");
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getAccounts(token, controller.signal)
      .then((data) => {
        setSnapshot(data);
        setSelectedId((current) => current ?? data.accounts[0]?.id);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Les comptes ne peuvent pas être chargés.");
        }
      });
    return () => controller.abort();
  }, [token, refreshKey]);

  const visibleAccounts = useMemo(() => {
    if (!snapshot) return [];
    return statusFilter === "Tous"
      ? snapshot.accounts
      : snapshot.accounts.filter((account) => account.status === statusFilter);
  }, [snapshot, statusFilter]);

  const selected = visibleAccounts.find((account) => account.id === selectedId)
    ?? visibleAccounts[0];

  if (error) {
    return (
      <section className="error-state">
        <strong>Les comptes ne peuvent pas être affichés.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Chargement des comptes depuis le moteur Python…</div>;
  }

  return (
    <div className="accounts-page">
      <section className="accounts-toolbar" aria-label="Vues des comptes">
        <div className="account-tabs" role="tablist" aria-label="Présentation des comptes">
          <Tab active={view === "accounts"} onClick={() => setView("accounts")}>Vue comptes</Tab>
          <Tab active={view === "balances"} onClick={() => setView("balances")}>Soldes à date</Tab>
          <Tab active={view === "imports"} onClick={() => setView("imports")}>Imports associés</Tab>
        </div>
      </section>

      {view === "accounts" && (
        <>
          {visibleAccounts.length > 0 ? (
            <section className="account-cards" aria-label="Liste des comptes">
              {visibleAccounts.map((account) => (
                <AccountCard
                  account={account}
                  active={account.id === selected?.id}
                  key={account.id}
                  onSelect={() => setSelectedId(account.id)}
                />
              ))}
            </section>
          ) : <EmptyAccounts />}

          {selected && (
            <section className="accounts-detail-grid">
              <article className="card account-movements">
                <div className="panel-heading">
                  <div><h2>Mouvements du compte sélectionné</h2><p>Derniers mouvements enregistrés par le moteur local.</p></div>
                </div>
                <TransactionsTable account={selected} />
              </article>
              <AccountDetail account={selected} />
            </section>
          )}
        </>
      )}

      {view === "balances" && <BalancesView accounts={visibleAccounts} />}
      {view === "imports" && <ImportsView accounts={visibleAccounts} />}

    </div>
  );
}

function Tab({ active, children, onClick }: { active: boolean; children: string; onClick: () => void }) {
  return <button aria-selected={active} className={active ? "account-tab account-tab--active" : "account-tab"} onClick={onClick} role="tab" type="button">{children}</button>;
}

function AccountCard({ account, active, onSelect }: { account: AccountOverview; active: boolean; onSelect: () => void }) {
  return (
    <button className={active ? "account-card account-card--active" : "account-card"} onClick={onSelect} type="button">
      <span className="account-card__title">{account.name}</span>
      <small>{account.bank} · {account.type}</small>
      <strong className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</strong>
      <span className="account-card__identifier">Identifiant import : {account.identifier || "non renseigné"}</span>
      <span className={`status-chip status-chip--${statusTone(account)}`}>{account.status}</span>
    </button>
  );
}

function TransactionsTable({ account }: { account: AccountOverview }) {
  if (account.transactions.length === 0) {
    return <p className="account-empty-row">Aucun mouvement enregistré pour ce compte.</p>;
  }
  return (
    <div className="account-table-wrap">
      <table className="account-table">
        <thead><tr><th>Date</th><th>Libellé</th><th>Catégorie</th><th>Montant</th></tr></thead>
        <tbody>
          {account.transactions.slice(0, 4).map((transaction) => (
            <tr key={transaction.id}>
              <td>{formatDate(transaction.date, false)}</td>
              <td>{transaction.label}</td>
              <td><span className={`category-chip ${transaction.category === "À catégoriser" ? "category-chip--warning" : ""}`}>{transaction.category}</span></td>
              <td className={transaction.amount < 0 ? "amount amount--negative" : "amount amount--positive"}>{signedMoney(transaction.amount)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AccountDetail({ account }: { account: AccountOverview }) {
  const fields = [
    ["Compte", account.name],
    ["Solde de référence", formatMoney(account.initialBalance)],
    ["Date de référence", formatDate(account.initialDate, true)],
    ["Solde calculé", formatMoney(account.currentBalance)],
  ];
  return (
    <aside className="card account-detail">
      <div className="panel-heading"><div><h2>Volet compte</h2><p>Détail issu du moteur métier.</p></div></div>
      <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <div className="account-detail__actions">
        <button aria-disabled="true" type="button">Modifier le solde</button>
        <button aria-disabled="true" className="primary-button" type="button">Rattacher un import</button>
      </div>
    </aside>
  );
}

function BalancesView({ accounts }: { accounts: AccountOverview[] }) {
  if (accounts.length === 0) return <EmptyAccounts />;
  return (
    <section className="card account-wide-panel">
      <div className="panel-heading"><div><h2>Soldes à date</h2><p>Traçabilité du solde initial jusqu’au solde calculé.</p></div></div>
      <div className="account-table-wrap">
        <table className="account-table account-table--balances">
          <thead><tr><th>Compte</th><th>Solde initial</th><th>Date initiale</th><th>Mouvements</th><th>Solde calculé</th><th>Calculé au</th></tr></thead>
          <tbody>{accounts.map((account) => <tr key={account.id}><td><strong>{account.name}</strong><small>{account.bank}</small></td><td>{formatMoney(account.initialBalance)}</td><td>{formatDate(account.initialDate, true)}</td><td>{signedMoney(account.movementTotal)}</td><td className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</td><td>{formatDate(account.currentDate, true)}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}

function ImportsView({ accounts }: { accounts: AccountOverview[] }) {
  if (accounts.length === 0) return <EmptyAccounts />;
  return (
    <section className="import-associations">
      {accounts.map((account) => (
        <article className="card import-association" key={account.id}>
          <span className="account-card__title">{account.name}</span>
          <small>{account.bank} · {account.type}</small>
          <dl><div><dt>Identifiant import</dt><dd>{account.identifier || "Non renseigné"}</dd></div></dl>
          <span className={account.identifier ? "status-chip status-chip--success" : "status-chip status-chip--warning"}>{account.identifier ? "Association disponible" : "À compléter"}</span>
        </article>
      ))}
    </section>
  );
}

function EmptyAccounts() {
  return <section className="card account-empty"><strong>Aucun compte pour ce filtre</strong><p>Les comptes apparaîtront ici dès qu’ils seront présents dans la base locale.</p></section>;
}

function statusTone(account: AccountOverview): "success" | "warning" | "muted" {
  if (account.status !== "Actif") return "muted";
  return account.currentBalance < 0 ? "warning" : "success";
}

function formatMoney(value: number): string {
  return currencyFormatter.format(value);
}

function signedMoney(value: number): string {
  if (value === 0) return formatMoney(value);
  return `${value > 0 ? "+ " : "- "}${formatMoney(Math.abs(value))}`;
}

function formatDate(value: string, withYear: boolean): string {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return (withYear ? longDateFormatter : shortDateFormatter).format(date);
}
