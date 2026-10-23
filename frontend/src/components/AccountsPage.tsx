import { type FormEvent, type MouseEvent, useEffect, useMemo, useRef, useState } from "react";

import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { ReconciledPill } from "./ReconciledPill";
import { createAccount, deleteAccount, getAccounts, updateAccount, updateAccountReference, updateAccountStatus } from "../api/client";
import type { AccountActionResult, AccountOverview, AccountPayload, AccountsSnapshot } from "../api/contracts";

type AccountStatus = "Actif" | "Archivé" | "Clos";
type AccountEditorState = { mode: "create" } | { mode: "edit"; account: AccountOverview };

interface AccountsPageProps {
  editorRequestKey: number;
  onAccountChanged: () => void;
  onAttachImport: (accountId: number) => void;
  onShowOperations: (accountId: number) => void;
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

export function AccountsPage({ editorRequestKey, onAccountChanged, onAttachImport, onShowOperations, statusFilter, token }: AccountsPageProps) {
  const [snapshot, setSnapshot] = useState<AccountsSnapshot>();
  const [selectedId, setSelectedId] = useState<number>();
  const [menu, setMenu] = useState<ContextMenuState>();
  const [collapsed, setCollapsed] = useState<string[]>(["Investissements", "Crédits"]);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [editor, setEditor] = useState<AccountEditorState>();
  const [referenceAccount, setReferenceAccount] = useState<AccountOverview>();
  const [statusChange, setStatusChange] = useState<{ account: AccountOverview; target: AccountStatus }>();
  const [deletionAccount, setDeletionAccount] = useState<AccountOverview>();
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
    setStatusChange(undefined);
    setNotice(result.message);
    if (result.accountId) setSelectedId(result.accountId);
    setRefreshKey((key) => key + 1);
    onAccountChanged();
  }

  function deleted(result: AccountActionResult) {
    setDeletionAccount(undefined);
    setNotice(result.message);
    setSelectedId(undefined);
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

  function openMenu(event: MouseEvent, account: AccountOverview) {
    event.preventDefault();
    event.stopPropagation();
    setSelectedId(account.id);
    const hasMovements = account.transactionCount > 0;
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Modifier le compte…", onSelect: () => setEditor({ mode: "edit", account }) },
        { label: "Modifier le solde de référence…", onSelect: () => setReferenceAccount(account) },
        { label: "Rattacher un import…", disabled: account.status !== "Actif", hint: account.status !== "Actif" ? "Seul un compte actif peut recevoir un import." : undefined, onSelect: () => onAttachImport(account.id) },
        { label: "Voir les opérations", onSelect: () => onShowOperations(account.id) },
        ...(account.status !== "Actif" ? [{ label: "Restaurer", onSelect: () => setStatusChange({ account, target: "Actif" as AccountStatus }) }] : [{ label: "Archiver", onSelect: () => setStatusChange({ account, target: "Archivé" as AccountStatus }) }]),
        ...(account.status !== "Clos" ? [{ label: "Clôturer…", onSelect: () => setStatusChange({ account, target: "Clos" as AccountStatus }) }] : []),
        { label: "Supprimer définitivement…", danger: true, disabled: hasMovements, onSelect: () => setDeletionAccount(account) },
      ],
      note: hasMovements ? "Suppression impossible : ce compte a des opérations. Archivez-le pour conserver l’historique." : undefined,
    });
  }

  const liquidity = snapshot.accounts
    .filter((account) => account.status === "Actif" && isLiquidType(account.type))
    .reduce((sum, account) => sum + account.currentBalance, 0);
  const liquidityCount = snapshot.accounts.filter((account) => account.status === "Actif" && isLiquidType(account.type)).length;

  return (
    <div className="cpt-page">
      {notice && <div className="account-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}

      {visibleAccounts.length > 0 && selected ? (
        <section className="cpt-workspace" aria-label="Gestion du compte sélectionné">
          <AccountRail
            accounts={visibleAccounts}
            collapsed={collapsed}
            liquidity={liquidity}
            liquidityCount={liquidityCount}
            onContextMenu={openMenu}
            onSelect={setSelectedId}
            onToggle={(group) => setCollapsed((current) => current.includes(group) ? current.filter((item) => item !== group) : [...current, group])}
            selectedId={selected.id}
          />
          <AccountView account={selected} onContextMenu={(event) => openMenu(event, selected)} onShowOperations={() => onShowOperations(selected.id)} />
        </section>
      ) : <EmptyAccounts onCreate={() => setEditor({ mode: "create" })} />}

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
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
      {statusChange && (
        <AccountStatusDialog account={statusChange.account} onClose={() => setStatusChange(undefined)} onCompleted={completed} target={statusChange.target} token={token} />
      )}
      {deletionAccount && (
        <AccountDeleteDialog account={deletionAccount} onClose={() => setDeletionAccount(undefined)} onCompleted={deleted} token={token} />
      )}
    </div>
  );
}

const ACCOUNT_GROUPS = ["Comptes courants", "Épargne", "Investissements", "Crédits", "Autres"] as const;

function isLiquidType(type: string): boolean {
  return groupOf(type) === "Comptes courants" || groupOf(type) === "Épargne";
}

function groupOf(type: string): (typeof ACCOUNT_GROUPS)[number] {
  const normalized = type.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("fr-FR");
  if (normalized.includes("courant")) return "Comptes courants";
  if (normalized.includes("epargne")) return "Épargne";
  if (normalized.includes("invest")) return "Investissements";
  if (normalized.includes("credit")) return "Crédits";
  return "Autres";
}

function AccountRail({ accounts, collapsed, liquidity, liquidityCount, onContextMenu, onSelect, onToggle, selectedId }: {
  accounts: AccountOverview[];
  collapsed: string[];
  liquidity: number;
  liquidityCount: number;
  onContextMenu: (event: MouseEvent, account: AccountOverview) => void;
  onSelect: (accountId: number) => void;
  onToggle: (group: string) => void;
  selectedId: number;
}) {
  const groups = ACCOUNT_GROUPS
    .map((name) => ({ name, items: accounts.filter((account) => groupOf(account.type) === name) }))
    .filter((group) => group.items.length > 0);
  return (
    <aside className="card cpt-rail">
      <div className="cpt-rail__total">
        <span>Liquidités · {liquidityCount} compte{liquidityCount > 1 ? "s" : ""}</span>
        <strong>{formatMoney(liquidity)}</strong>
        <small>Comptes courants et épargne actifs</small>
      </div>
      <nav className="cpt-rail__list" aria-label="Sélection du compte">
        {groups.map((group) => {
          const closed = collapsed.includes(group.name) && !group.items.some((account) => account.id === selectedId);
          const subtotal = group.items.reduce((sum, account) => sum + account.currentBalance, 0);
          return (
            <div className="cpt-group" key={group.name}>
              <button aria-expanded={!closed} className="cpt-group__head" onClick={() => onToggle(group.name)} type="button">
                <span>{closed ? "▸" : "▾"} {group.name} · {group.items.length}</span>
                <b className={subtotal < 0 ? "amount--negative" : undefined}>{formatCompact(subtotal)}</b>
              </button>
              {!closed && group.items.map((account) => (
                <button
                  aria-current={account.id === selectedId ? "true" : undefined}
                  className={account.id === selectedId ? "cpt-row cpt-row--active" : "cpt-row"}
                  key={account.id}
                  onClick={() => onSelect(account.id)}
                  onContextMenu={(event) => onContextMenu(event, account)}
                  type="button"
                >
                  <BankBadge bank={account.bank} />
                  <span className="cpt-row__name" title={account.name}>{account.name}{account.status !== "Actif" && <small>{account.status}</small>}</span>
                  <b className={account.currentBalance < 0 ? "amount--negative" : undefined}>{formatCompact(account.currentBalance)}</b>
                </button>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}

function AccountView({ account, onContextMenu, onShowOperations }: {
  account: AccountOverview;
  onContextMenu: (event: MouseEvent) => void;
  onShowOperations: () => void;
}) {
  const credits = account.transactions.filter((item) => item.amount > 0).reduce((sum, item) => sum + item.amount, 0);
  const debits = Math.abs(account.transactions.filter((item) => item.amount < 0).reduce((sum, item) => sum + item.amount, 0));
  const fields = [
    ["Type de compte", account.type],
    ["Identifiant import", maskIdentifier(account.identifier)],
    ["Devise", account.currency],
    ["Solde de référence", formatMoney(account.initialBalance)],
    ["Date de référence", formatDate(account.initialDate, true)],
    ["Mouvements cumulés", signedMoney(account.movementTotal)],
    ["Calcul arrêté au", formatDate(account.currentDate, true)],
    ["Opérations", String(account.transactionCount)],
  ];
  return (
    <article className="card cpt-view" onContextMenu={onContextMenu}>
      <header className="cpt-view__head">
        <BankBadge bank={account.bank} large />
        <div className="cpt-view__title">
          <div><h2>{account.name}</h2><span className={`status-chip status-chip--${statusTone(account)}`}>{account.status}</span></div>
          <p>{account.bank || "Banque non renseignée"} · {account.type} · clic droit pour les actions</p>
        </div>
        <div className="cpt-view__balance">
          <span>Solde actuel</span>
          <strong className={account.currentBalance < 0 ? "amount amount--negative" : "amount"}>{formatMoney(account.currentBalance)}</strong>
        </div>
      </header>

      <div className="cpt-view__metrics">
        <BalanceBars history={account.balanceHistory} />
        <div className="cpt-flows">
          <div><span>Entrées récentes</span><b className="amount--positive">+ {formatMoney(credits)}</b></div>
          <div><span>Sorties récentes</span><b className="amount--negative">- {formatMoney(debits)}</b></div>
          <div><span>Solde calculé au</span><b>{formatDate(account.currentDate, true)}</b></div>
        </div>
      </div>

      <section className="cpt-fiche" aria-label="Fiche du compte">
        <h3>Fiche du compte</h3>
        <dl>{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      </section>

      <section className="cpt-ops" aria-label="Dernières opérations">
        <div className="cpt-ops__head">
          <h3>{Math.min(5, account.transactions.length)} dernière{account.transactions.length > 1 ? "s" : ""} opération{account.transactions.length > 1 ? "s" : ""}</h3>
          {account.transactionCount > 0 && <button onClick={onShowOperations} type="button">Voir toutes les opérations de ce compte ›</button>}
        </div>
        {account.transactions.length === 0 ? (
          <p className="cpt-ops__empty">Aucune opération enregistrée. Les mouvements apparaîtront ici après un import ou une saisie.</p>
        ) : (
          <table className="cpt-ops__table">
            <tbody>
              {account.transactions.slice(0, 5).map((transaction) => (
                <tr key={transaction.id}>
                  <td>{formatDate(transaction.date, false)}</td>
                  <td title={transaction.label}>{transaction.label} <ReconciledPill badge={transaction.reconciliation} /></td>
                  <td><span className={`category-chip ${transaction.category === "À catégoriser" ? "category-chip--warning" : ""}`}>{transaction.category}</span></td>
                  <td className={transaction.amount < 0 ? "amount amount--negative" : "amount amount--positive"}>{signedMoney(transaction.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </article>
  );
}

function shiftMonth(month: string, delta: number): string {
  const [year, number] = month.split("-").map(Number);
  const index = year * 12 + (number - 1) + delta;
  return `${Math.floor(index / 12)}-${String((index % 12) + 1).padStart(2, "0")}`;
}

function BalanceBars({ history }: { history: { month: string; balance: number }[] }) {
  if (history.length === 0) {
    return <div className="cpt-chart cpt-chart--empty">Pas encore d’historique de solde.</div>;
  }
  const low = Math.min(0, ...history.map((point) => point.balance));
  const high = Math.max(0, ...history.map((point) => point.balance));
  const span = high - low || 1;
  const monthLabel = (month: string) => new Date(`${month}-15T12:00:00`).toLocaleDateString("fr-FR", { month: "short" });
  return (
    <div className="cpt-chart" role="img" aria-label="Évolution du solde sur 12 mois">
      <span className="cpt-chart__title">Évolution du solde · 12 mois</span>
      <div className="cpt-chart__bars">
        {Array.from({ length: Math.max(0, 12 - history.length) }, (_, index) => (
          <div className="cpt-chart__col" key={`empty-${index}`} title="Pas encore d’historique"><i className="is-empty" style={{ alignSelf: "flex-end", height: "3px" }} /></div>
        ))}
        {history.map((point, index) => (
          <div className="cpt-chart__col" key={point.month} title={`${monthLabel(point.month)} ${point.month.slice(0, 4)} : ${formatMoney(point.balance)}`}>
            <i className={`${index === history.length - 1 ? "is-last" : ""} ${point.balance < 0 ? "is-negative" : ""}`} style={{ height: `${Math.max(3, (Math.abs(point.balance) / span) * 100)}%`, alignSelf: point.balance < 0 ? "flex-start" : "flex-end" }} />
          </div>
        ))}
      </div>
      <div className="cpt-chart__axis"><span>{monthLabel(shiftMonth(history[history.length - 1].month, -11))}</span><span>{monthLabel(history[history.length - 1].month)}</span></div>
    </div>
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
          </div>
          {account && <p className="account-editor-note">Le solde et sa date de référence se corrigent séparément. Le statut se gère depuis les actions « Archiver », « Clôturer » ou « Restaurer » afin de préserver la traçabilité.</p>}
          {formError && <div className="account-form-error" role="alert">{formError}</div>}
          <footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : account ? "Enregistrer" : "Ajouter le compte"}</button></footer>
        </form>
      </aside>
    </div>
  );
}

function AccountStatusDialog({ account, onClose, onCompleted, target, token }: {
  account: AccountOverview;
  onClose: () => void;
  onCompleted: (result: AccountActionResult) => void;
  target: AccountStatus;
  token: string;
}) {
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();
  const copy = {
    Actif: {
      eyebrow: "Restauration du compte",
      title: "Restaurer ce compte ?",
      detail: "Le compte réintégrera immédiatement les listes actives et pourra de nouveau recevoir des imports et de nouvelles opérations.",
      action: "Restaurer le compte",
    },
    Archivé: {
      eyebrow: "Archivage sans perte",
      title: "Archiver ce compte ?",
      detail: "Le compte sera retiré des listes de travail actives. Ses transactions, imports, rapprochements et statistiques resteront consultables et il pourra être restauré.",
      action: "Archiver le compte",
    },
    Clos: {
      eyebrow: "Clôture du compte",
      title: "Clôturer ce compte ?",
      detail: "Le compte sera marqué comme clôturé et retiré des sélecteurs actifs. Son historique financier sera intégralement conservé.",
      action: "Clôturer le compte",
    },
  }[target];

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(await updateAccountStatus(token, account.id, target));
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="account-status-title" aria-modal="true" className="account-editor account-editor--compact account-lifecycle-dialog" role="dialog">
        <header>
          <div><span className="eyebrow">{copy.eyebrow}</span><h2 id="account-status-title">{copy.title}</h2></div>
          <button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="account-lifecycle-dialog__body">
            <AccountDialogIdentity account={account} />
            <p>{copy.detail}</p>
            <p><strong>Aucune donnée liée ne sera supprimée.</strong></p>
            {formError && <div className="account-form-error" role="alert">{formError}</div>}
          </div>
          <footer>
            <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button>
            <button className={target === "Actif" ? "" : "account-status-confirm"} disabled={busy} type="submit">{busy ? "Enregistrement…" : copy.action}</button>
          </footer>
        </form>
      </aside>
    </div>
  );
}

function AccountDeleteDialog({ account, onClose, onCompleted, token }: {
  account: AccountOverview;
  onClose: () => void;
  onCompleted: (result: AccountActionResult) => void;
  token: string;
}) {
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      onCompleted(await deleteAccount(token, account.id));
    } catch (cause: unknown) {
      setFormError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}>
      <aside aria-labelledby="account-delete-title" aria-modal="true" className="account-editor account-editor--compact account-lifecycle-dialog" role="dialog">
        <header>
          <div><span className="eyebrow">Suppression protégée</span><h2 id="account-delete-title">Supprimer le compte ?</h2></div>
          <button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <div className="account-lifecycle-dialog__body">
            <AccountDialogIdentity account={account} />
            <p><strong>Cette action est définitive et réservée à un compte entièrement vide.</strong></p>
            <p>Si une opération, un import, une récurrence, une prévision, une règle ou un scénario est rattaché au compte, Valoria Vision bloquera la suppression et vous invitera à l’archiver.</p>
            {formError && <div className="account-form-error" role="alert">{formError}</div>}
          </div>
          <footer>
            <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Conserver le compte</button>
            <button className="account-delete-confirm" disabled={busy} type="submit">{busy ? "Vérification…" : "Supprimer définitivement"}</button>
          </footer>
        </form>
      </aside>
    </div>
  );
}

function AccountDialogIdentity({ account }: { account: AccountOverview }) {
  return (
    <div className="account-lifecycle-dialog__identity">
      <BankBadge bank={account.bank} />
      <div><strong>{account.name}</strong><span>{account.bank || "Banque non renseignée"} · {account.status}</span></div>
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

function formatCompact(value: number): string {
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(value);
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
