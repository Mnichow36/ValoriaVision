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
        visibleAccounts.length > 0 && selected ? (
          <section className="accounts-workspace" aria-label="Gestion du compte sélectionné">
            <AccountRail
              accounts={visibleAccounts}
              onCreate={() => setEditor({ mode: "create" })}
              onSelect={setSelectedId}
              selectedId={selected.id}
            />
            <AccountActivity account={selected} />
            <AccountDetail
              account={selected}
              onAttachImport={() => onAttachImport(selected.id)}
              onEdit={() => setEditor({ mode: "edit", account: selected })}
              onReference={() => setReferenceAccount(selected)}
            />
          </section>
        ) : <EmptyAccounts onCreate={() => setEditor({ mode: "create" })} />
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

function AccountRail({
  accounts,
  onCreate,
  onSelect,
  selectedId,
}: {
  accounts: AccountOverview[];
  onCreate: () => void;
  onSelect: (accountId: number) => void;
  selectedId: number;
}) {
  const total = accounts.reduce((sum, account) => sum + account.currentBalance, 0);
  return (
    <aside className="card accounts-rail">
      <div className="accounts-rail__heading">
        <div><span className="eyebrow">Mes comptes</span><strong>{accounts.length} compte{accounts.length > 1 ? "s" : ""}</strong></div>
        <button aria-label="Ajouter un compte" onClick={onCreate} title="Ajouter un compte" type="button">+</button>
      </div>
      <div className="accounts-rail__total">
        <span>Solde cumulé affiché</span>
        <strong className={total < 0 ? "amount amount--negative" : "amount"}>{formatMoney(total)}</strong>
      </div>
      <nav className="accounts-rail__list" aria-label="Sélection du compte">
        {accounts.map((account) => (
          <AccountCard
            account={account}
            active={account.id === selectedId}
            key={account.id}
            onSelect={() => onSelect(account.id)}
          />
        ))}
      </nav>
    </aside>
  );
}

function AccountCard({ account, active, onSelect }: { account: AccountOverview; active: boolean; onSelect: () => void }) {
  return (
    <button
      aria-current={active ? "true" : undefined}
      className={active ? "account-list-card account-list-card--active" : "account-list-card"}
      onClick={onSelect}
      type="button"
    >
      <BankBadge bank={account.bank} />
      <span className="account-list-card__copy">
        <strong>{account.name}</strong>
        <small>{account.bank || "Banque non renseignée"} · {account.type}</small>
        <span className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</span>
      </span>
      <span className="account-list-card__chevron" aria-hidden="true">›</span>
    </button>
  );
}

function AccountActivity({ account }: { account: AccountOverview }) {
  const credits = account.transactions
    .filter((transaction) => transaction.amount > 0)
    .reduce((sum, transaction) => sum + transaction.amount, 0);
  const debits = Math.abs(account.transactions
    .filter((transaction) => transaction.amount < 0)
    .reduce((sum, transaction) => sum + transaction.amount, 0));

  return (
    <article className="card account-activity">
      <header className="account-activity__heading">
        <div>
          <span className="eyebrow">Opérations du compte</span>
          <h2>{account.name}</h2>
          <p>{account.bank} · {account.type} · solde calculé au {formatDate(account.currentDate, true)}</p>
        </div>
        <span className={`status-chip status-chip--${statusTone(account)}`}>{account.status}</span>
      </header>
      <div className="account-activity__summary" aria-label="Résumé des opérations affichées">
        <div><span>Solde actuel</span><strong className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</strong></div>
        <div><span>Entrées affichées</span><strong className="amount amount--positive">+ {formatMoney(credits)}</strong></div>
        <div><span>Sorties affichées</span><strong className="amount amount--negative">- {formatMoney(debits)}</strong></div>
      </div>
      <TransactionsTable account={account} />
    </article>
  );
}

function TransactionsTable({ account }: { account: AccountOverview }) {
  if (account.transactions.length === 0) {
    return (
      <div className="account-operations-empty">
        <span aria-hidden="true">↕</span>
        <strong>Aucune opération enregistrée</strong>
        <p>Les mouvements apparaîtront ici après un import ou une saisie.</p>
      </div>
    );
  }
  return (
    <div className="account-table-wrap account-table-wrap--operations">
      <table className="account-table account-table--operations">
        <thead><tr><th>Date</th><th>Opération</th><th>Catégorie</th><th>Montant</th></tr></thead>
        <tbody>
          {account.transactions.map((transaction) => (
            <tr key={transaction.id}>
              <td>{formatDate(transaction.date, false)}</td>
              <td><strong>{transaction.label}</strong><small>{transaction.status || "Enregistrée"}</small></td>
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
    ["Type de compte", account.type],
    ["Identifiant import", maskIdentifier(account.identifier)],
    ["Devise", account.currency],
    ["Solde de référence", formatMoney(account.initialBalance)],
    ["Date de référence", formatDate(account.initialDate, true)],
    ["Mouvements cumulés", signedMoney(account.movementTotal)],
    ["Calcul arrêté au", formatDate(account.currentDate, true)],
  ];
  return (
    <aside className="card account-inspector">
      <div className="account-inspector__bank">
        <BankBadge bank={account.bank} large />
        <div>
          <span className="eyebrow">Informations du compte</span>
          <h2>{account.name}</h2>
          <p>{account.bank || "Banque non renseignée"}</p>
        </div>
        <button className="account-edit-link" onClick={onEdit} type="button">Modifier</button>
      </div>
      <div className="account-inspector__balance">
        <span>Solde calculé</span>
        <strong className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</strong>
        <small>Compte {account.status.toLocaleLowerCase("fr-FR")}</small>
      </div>
      <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <div className="account-detail__actions">
        <button onClick={onReference} type="button">Modifier le solde de référence</button>
        <button className="primary-button" onClick={onAttachImport} type="button">Rattacher un import</button>
      </div>
    </aside>
  );
}

function BankBadge({ bank, large = false }: { bank: string; large?: boolean }) {
  const identity = bankIdentity(bank);
  return (
    <span
      aria-label={bank || "Banque"}
      className={`bank-badge bank-badge--${identity.tone} ${large ? "bank-badge--large" : ""}`}
      title={bank || "Banque"}
    >
      <b>{identity.label}</b>
      <i aria-hidden="true" />
    </span>
  );
}

function bankIdentity(bank: string): { label: string; tone: string } {
  const normalized = bank.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("fr-FR");
  const knownBanks = [
    { match: ["bnp", "hello bank"], label: "BNP", tone: "emerald" },
    { match: ["boursorama", "bourso"], label: "B", tone: "bourso" },
    { match: ["societe generale", "sg"], label: "SG", tone: "red" },
    { match: ["credit agricole"], label: "CA", tone: "teal" },
    { match: ["caisse d'epargne"], label: "CE", tone: "red" },
    { match: ["banque populaire"], label: "BP", tone: "violet" },
    { match: ["credit mutuel"], label: "CM", tone: "blue" },
    { match: ["cic"], label: "CIC", tone: "blue" },
    { match: ["lcl"], label: "LCL", tone: "blue" },
    { match: ["revolut"], label: "R", tone: "ink" },
    { match: ["n26"], label: "N26", tone: "teal" },
  ];
  const known = knownBanks.find((item) => item.match.some((value) => normalized.includes(value)));
  if (known) return { label: known.label, tone: known.tone };
  const words = bank.trim().split(/\s+/).filter(Boolean);
  const label = words.length > 1
    ? words.slice(0, 2).map((word) => word[0]).join("").toUpperCase()
    : (words[0] || "B").slice(0, 3).toUpperCase();
  const tones = ["blue", "violet", "teal", "amber", "ink"];
  const checksum = Array.from(normalized).reduce((sum, letter) => sum + letter.charCodeAt(0), 0);
  return { label, tone: tones[checksum % tones.length] };
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
