import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { createAccount, getAccounts, updateAccount, updateAccountReference } from "../api/client";
import type { AccountActionResult, AccountOverview, AccountPayload, AccountsSnapshot } from "../api/contracts";

type AccountsView = "accounts" | "balances" | "imports";
type AccountEditorState = { mode: "create" } | { mode: "edit"; account: AccountOverview };

interface AccountsPageProps {
  editorRequestKey: number;
  onAccountChanged: () => void;
  onAttachImport: (accountId: number) => void;
  statusFilter: string;
  token: string;
}

const currencyFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  minimumFractionDigits: 2,
});

const shortDateFormatter = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" });
const longDateFormatter = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

export function AccountsPage({ editorRequestKey, onAccountChanged, onAttachImport, statusFilter, token }: AccountsPageProps) {
  const [snapshot, setSnapshot] = useState<AccountsSnapshot>();
  const [selectedId, setSelectedId] = useState<number>();
  const [view, setView] = useState<AccountsView>("accounts");
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [editor, setEditor] = useState<AccountEditorState>();
  const [referenceAccount, setReferenceAccount] = useState<AccountOverview>();
  const lastEditorRequestKey = useRef(0);

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

  useEffect(() => {
    if (editorRequestKey > 0 && editorRequestKey !== lastEditorRequestKey.current) {
      lastEditorRequestKey.current = editorRequestKey;
      setEditor({ mode: "create" });
    }
  }, [editorRequestKey]);

  const visibleAccounts = useMemo(() => {
    if (!snapshot) return [];
    return statusFilter === "Tous"
      ? snapshot.accounts
      : snapshot.accounts.filter((account) => account.status === statusFilter);
  }, [snapshot, statusFilter]);

  const selected = visibleAccounts.find((account) => account.id === selectedId) ?? visibleAccounts[0];

  function completed(result: AccountActionResult) {
    setEditor(undefined);
    setReferenceAccount(undefined);
    setNotice(result.message);
    if (result.accountId) setSelectedId(result.accountId);
    setRefreshKey((key) => key + 1);
    onAccountChanged();
  }

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
      {notice && <div className="account-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}

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
                <AccountCard account={account} active={account.id === selected?.id} key={account.id} onSelect={() => setSelectedId(account.id)} />
              ))}
            </section>
          ) : <EmptyAccounts onCreate={() => setEditor({ mode: "create" })} />}

          {selected && (
            <section className="accounts-detail-grid">
              <article className="card account-movements">
                <div className="panel-heading"><div><h2>Mouvements du compte sélectionné</h2><p>Derniers mouvements enregistrés par le moteur local.</p></div></div>
                <TransactionsTable account={selected} />
              </article>
              <AccountDetail
                account={selected}
                onAttachImport={() => onAttachImport(selected.id)}
                onEdit={() => setEditor({ mode: "edit", account: selected })}
                onReference={() => setReferenceAccount(selected)}
              />
            </section>
          )}
        </>
      )}

      {view === "balances" && <BalancesView accounts={visibleAccounts} />}
      {view === "imports" && <ImportsView accounts={visibleAccounts} />}

      {editor && (
        <AccountEditor
          account={editor.mode === "edit" ? editor.account : undefined}
          onClose={() => setEditor(undefined)}
          onCompleted={completed}
          token={token}
        />
      )}
      {referenceAccount && (
        <ReferenceEditor account={referenceAccount} onClose={() => setReferenceAccount(undefined)} onCompleted={completed} token={token} />
      )}
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
      <span className="account-card__identifier">Identifiant import : {maskIdentifier(account.identifier)}</span>
      <span className={`status-chip status-chip--${statusTone(account)}`}>{account.status}</span>
    </button>
  );
}

function TransactionsTable({ account }: { account: AccountOverview }) {
  if (account.transactions.length === 0) return <p className="account-empty-row">Aucun mouvement enregistré pour ce compte.</p>;
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

function AccountDetail({ account, onAttachImport, onEdit, onReference }: {
  account: AccountOverview;
  onAttachImport: () => void;
  onEdit: () => void;
  onReference: () => void;
}) {
  const fields = [
    ["Compte", account.name],
    ["Solde de référence", formatMoney(account.initialBalance)],
    ["Date de référence", formatDate(account.initialDate, true)],
    ["Solde calculé", formatMoney(account.currentBalance)],
  ];
  return (
    <aside className="card account-detail">
      <div className="panel-heading">
        <div><h2>Volet compte</h2><p>Détail issu du moteur métier.</p></div>
        <button className="account-edit-link" onClick={onEdit} type="button">Modifier le compte</button>
      </div>
      <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <div className="account-detail__actions">
        <button onClick={onReference} type="button">Modifier le solde</button>
        <button className="primary-button" onClick={onAttachImport} type="button">Rattacher un import</button>
      </div>
    </aside>
  );
}

function AccountEditor({ account, onClose, onCompleted, token }: {
  account?: AccountOverview;
  onClose: () => void;
  onCompleted: (result: AccountActionResult) => void;
  token: string;
}) {
  const [draft, setDraft] = useState<AccountPayload>(() => ({
    name: account?.name ?? "",
    bank: account?.bank ?? "",
    type: account?.type || "Compte courant",
    identifier: account?.identifier ?? "",
    initialBalance: account?.initialBalance ?? 0,
    initialDate: account?.initialDate || today(),
    currency: account?.currency || "EUR",
    status: account?.status || "Actif",
  }));
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  function field<Key extends keyof AccountPayload>(key: Key, value: AccountPayload[Key]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      const result = account ? await updateAccount(token, account.id, draft) : await createAccount(token, draft);
      onCompleted(result);
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="account-editor-title" aria-modal="true" className="account-editor" role="dialog">
        <header>
          <div><span className="eyebrow">Compte bancaire</span><h2 id="account-editor-title">{account ? "Modifier le compte" : "Ajouter un compte"}</h2></div>
          <button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="account-editor-grid">
            <label className="account-field account-field--wide"><span>Nom du compte *</span><input autoFocus maxLength={120} onChange={(event) => field("name", event.target.value)} required value={draft.name} /></label>
            <label className="account-field"><span>Banque *</span><input maxLength={120} onChange={(event) => field("bank", event.target.value)} required value={draft.bank} /></label>
            <label className="account-field"><span>Type *</span><select onChange={(event) => field("type", event.target.value)} value={draft.type}>{accountTypes.map((value) => <option key={value}>{value}</option>)}</select></label>
            <label className="account-field account-field--wide"><span>Identifiant bancaire</span><input autoComplete="off" maxLength={120} onChange={(event) => field("identifier", event.target.value)} placeholder="IBAN partiel ou identifiant présent sur le relevé" value={draft.identifier} /><small>Utilisé localement pour sécuriser l’association des imports.</small></label>
            {!account && <label className="account-field"><span>Solde initial *</span><input onChange={(event) => field("initialBalance", Number(event.target.value))} required step="0.01" type="number" value={draft.initialBalance} /></label>}
            {!account && <label className="account-field"><span>Date initiale *</span><input onChange={(event) => field("initialDate", event.target.value)} required type="date" value={draft.initialDate} /></label>}
            <label className="account-field"><span>Devise *</span><select onChange={(event) => field("currency", event.target.value)} value={draft.currency}>{["EUR", "USD", "GBP", "CHF"].map((value) => <option key={value}>{value}</option>)}</select></label>
            <label className="account-field"><span>Statut *</span><select onChange={(event) => field("status", event.target.value)} value={draft.status}>{["Actif", "Archivé", "Clos"].map((value) => <option key={value}>{value}</option>)}</select></label>
          </div>
          {account && <p className="account-editor-note">Le solde et sa date de référence se corrigent séparément avec « Modifier le solde » afin de préserver la traçabilité.</p>}
          {formError && <div className="account-form-error" role="alert">{formError}</div>}
          <footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : account ? "Enregistrer" : "Ajouter le compte"}</button></footer>
        </form>
      </aside>
    </div>
  );
}

function ReferenceEditor({ account, onClose, onCompleted, token }: {
  account: AccountOverview;
  onClose: () => void;
  onCompleted: (result: AccountActionResult) => void;
  token: string;
}) {
  const [balance, setBalance] = useState(account.initialBalance);
  const [referenceDate, setReferenceDate] = useState(account.initialDate || today());
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(await updateAccountReference(token, account.id, balance, referenceDate));
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="reference-editor-title" aria-modal="true" className="account-editor account-editor--compact" role="dialog">
        <header><div><span className="eyebrow">{account.name}</span><h2 id="reference-editor-title">Modifier le solde initial</h2></div><button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button></header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="account-editor-grid">
            <label className="account-field"><span>Nouveau solde initial *</span><input autoFocus onChange={(event) => setBalance(Number(event.target.value))} required step="0.01" type="number" value={balance} /></label>
            <label className="account-field"><span>Nouvelle date initiale *</span><input onChange={(event) => setReferenceDate(event.target.value)} required type="date" value={referenceDate} /></label>
          </div>
          <p className="account-editor-note">Le solde calculé sera recalculé à partir de cette nouvelle référence et des transactions postérieures.</p>
          {formError && <div className="account-form-error" role="alert">{formError}</div>}
          <footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : "Mettre à jour"}</button></footer>
        </form>
      </aside>
    </div>
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
          <dl><div><dt>Identifiant import</dt><dd>{maskIdentifier(account.identifier)}</dd></div></dl>
          <span className={account.identifier ? "status-chip status-chip--success" : "status-chip status-chip--warning"}>{account.identifier ? "Association disponible" : "À compléter"}</span>
        </article>
      ))}
    </section>
  );
}

function EmptyAccounts({ onCreate }: { onCreate?: () => void }) {
  return <section className="card account-empty"><strong>Aucun compte pour ce filtre</strong><p>Ajoutez un compte ou choisissez un autre statut.</p>{onCreate && <button onClick={onCreate} type="button">Ajouter un compte</button>}</section>;
}

const accountTypes = ["Compte courant", "Compte épargne", "Compte investissement", "Compte crédit", "Compte espèces", "Autre"];

function statusTone(account: AccountOverview): "success" | "warning" | "muted" {
  if (account.status !== "Actif") return "muted";
  return account.currentBalance < 0 ? "warning" : "success";
}

function maskIdentifier(value: string): string {
  const normalized = value.trim();
  if (!normalized) return "non renseigné";
  if (normalized.length <= 4) return normalized;
  return `****${normalized.slice(-4)}`;
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

function today(): string {
  const value = new Date();
  value.setMinutes(value.getMinutes() - value.getTimezoneOffset());
  return value.toISOString().slice(0, 10);
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Le moteur des comptes ne répond pas.";
}
