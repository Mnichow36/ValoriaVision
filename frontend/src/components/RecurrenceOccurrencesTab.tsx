import { useEffect, useMemo, useState } from "react";

import {
  deleteRecurrenceOccurrences,
  getRecurrenceOccurrences,
  restoreRecurrenceOccurrence,
  shiftRecurrenceOccurrences,
  updateRecurrenceOccurrence,
} from "../api/client";
import type { RecurrenceOccurrence, RecurrenceOccurrencesSnapshot } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";

type SortKey = "date" | "label" | "account" | "category" | "status" | "amount";
type Drawer =
  | { kind: "edit"; item: RecurrenceOccurrence }
  | { kind: "shift"; items: RecurrenceOccurrence[] }
  | { kind: "delete"; items: RecurrenceOccurrence[] };

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", minimumFractionDigits: 2 });
const dateFormat = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });

const STATUS_TONE: Record<string, string> = {
  planned: "blue",
  overdue: "red",
  to_review: "warning",
  partially_matched: "warning",
  auto_matched: "green",
  confirmed: "green",
  ignored: "muted",
  cancelled: "muted",
};

function formatDate(value: string): string {
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? value : dateFormat.format(date);
}

function signed(value: number): string {
  return `${value >= 0 ? "+ " : "- "}${money.format(Math.abs(value))}`;
}

function addDays(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

export function RecurrenceOccurrencesTab({ onDataChanged, token }: { onDataChanged: () => void; token: string }) {
  const [snapshot, setSnapshot] = useState<RecurrenceOccurrencesSnapshot>();
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [search, setSearch] = useState("");
  const [accountId, setAccountId] = useState("all");
  const [status, setStatus] = useState("all");
  const [period, setPeriod] = useState("all");
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({ key: "date", direction: "asc" });
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [menu, setMenu] = useState<ContextMenuState>();
  const [drawer, setDrawer] = useState<Drawer>();

  useEffect(() => {
    const controller = new AbortController();
    getRecurrenceOccurrences(token, controller.signal)
      .then((value) => { setSnapshot(value); setError(undefined); })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Les occurrences ne peuvent pas être chargées.");
      });
    return () => controller.abort();
  }, [refreshKey, token]);

  const accounts = useMemo(() => {
    const map = new Map<number, string>();
    snapshot?.items.forEach((item) => { if (item.accountId !== null) map.set(item.accountId, item.accountName); });
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1], "fr"));
  }, [snapshot]);
  const categories = useMemo(
    () => [...new Set((snapshot?.items ?? []).map((item) => item.category))].sort((a, b) => a.localeCompare(b, "fr")),
    [snapshot],
  );

  const visible = useMemo(() => {
    if (!snapshot) return [];
    const today = snapshot.referenceDate;
    const query = search.trim().toLocaleLowerCase("fr");
    const horizon = period === "30" ? addDays(today, 30) : period === "90" ? addDays(today, 90) : period === "180" ? addDays(today, 180) : "";
    const rows = snapshot.items.filter((item) => {
      if (accountId !== "all" && item.accountId !== Number(accountId)) return false;
      if (status === "todo" && !["planned", "overdue", "to_review", "partially_matched"].includes(item.status)) return false;
      if (status === "done" && !["auto_matched", "confirmed"].includes(item.status)) return false;
      if (status === "deleted" && !["cancelled", "ignored"].includes(item.status)) return false;
      if (["planned", "overdue", "to_review"].includes(status) && item.status !== status) return false;
      if (horizon && item.date > horizon) return false;
      if (period === "upcoming" && item.date < today) return false;
      if (query && ![item.label, item.accountName, item.category, item.frequency].some((value) => value.toLocaleLowerCase("fr").includes(query))) return false;
      return true;
    });
    const factor = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      let result = 0;
      if (sort.key === "date") result = a.date.localeCompare(b.date);
      else if (sort.key === "amount") result = a.amount - b.amount;
      else if (sort.key === "label") result = a.label.localeCompare(b.label, "fr");
      else if (sort.key === "account") result = a.accountName.localeCompare(b.accountName, "fr");
      else if (sort.key === "category") result = a.category.localeCompare(b.category, "fr");
      else result = a.statusLabel.localeCompare(b.statusLabel, "fr");
      return result * factor || a.id - b.id;
    });
  }, [accountId, period, search, snapshot, sort, status]);

  const selectedItems = visible.filter((item) => selectedIds.includes(item.id));
  const selectable = visible.filter((item) => item.canShift);
  const allSelected = selectable.length > 0 && selectable.every((item) => selectedIds.includes(item.id));
  const totalIn = visible.reduce((sum, item) => sum + Math.max(item.amount, 0), 0);
  const totalOut = visible.reduce((sum, item) => sum + Math.abs(Math.min(item.amount, 0)), 0);

  function toggleSort(key: SortKey) {
    setSort((current) => current.key === key ? { key, direction: current.direction === "asc" ? "desc" : "asc" } : { key, direction: key === "amount" ? "desc" : "asc" });
  }

  function done(message: string) {
    setDrawer(undefined);
    setSelectedIds([]);
    setNotice(message);
    setRefreshKey((key) => key + 1);
    onDataChanged();
  }

  async function restore(item: RecurrenceOccurrence) {
    try {
      done((await restoreRecurrenceOccurrence(token, item.id)).message);
    } catch (cause: unknown) {
      setNotice(cause instanceof Error ? cause.message : "Le rétablissement a échoué.");
    }
  }

  function openMenu(event: React.MouseEvent, item: RecurrenceOccurrence) {
    event.preventDefault();
    const group = selectedIds.includes(item.id) && selectedItems.length > 1 ? selectedItems.filter((row) => row.canShift) : [item];
    const plural = group.length > 1 ? ` (${group.length})` : "";
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Modifier l’occurrence…", disabled: !item.canEdit, hint: item.canEdit ? undefined : "Non modifiable", onSelect: () => setDrawer({ kind: "edit", item }) },
        { label: `Décaler${plural}…`, disabled: !item.canShift, onSelect: () => setDrawer({ kind: "shift", items: group }) },
        ...(item.canRestore ? [{ label: "Rétablir", onSelect: () => void restore(item) }] : []),
        { label: `Supprimer${plural}…`, danger: true, disabled: !item.canDelete, onSelect: () => setDrawer({ kind: "delete", items: group }) },
      ],
    });
  }

  if (error && !snapshot) {
    return (
      <section className="error-state">
        <strong>Les occurrences ne peuvent pas être affichées.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }
  if (!snapshot) return <div className="loading-state"><span aria-hidden="true" />Chargement des occurrences…</div>;

  return (
    <div className="transactions-page">
      {notice && <div className="transaction-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      <article className="card transactions-journal">
        <div className="transactions-heading"><h2>Occurrences de récurrence</h2></div>
        <div className="transaction-filters transaction-filters--occurrences" role="search">
          <input aria-label="Rechercher une occurrence" onChange={(event) => setSearch(event.target.value)} placeholder="Recherche libellé, compte, catégorie…" type="search" value={search} />
          <select aria-label="Filtrer par compte" onChange={(event) => setAccountId(event.target.value)} value={accountId}>
            <option value="all">Tous les comptes</option>
            {accounts.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          <select aria-label="Filtrer par statut" onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="all">Tous les statuts</option>
            <option value="todo">À traiter (prévues, en retard)</option>
            <option value="planned">Prévues</option>
            <option value="overdue">En retard</option>
            <option value="done">Rapprochées</option>
            <option value="deleted">Supprimées / ignorées</option>
          </select>
          <select aria-label="Filtrer par période" onChange={(event) => setPeriod(event.target.value)} value={period}>
            <option value="all">Toute la période</option>
            <option value="upcoming">À partir d’aujourd’hui</option>
            <option value="30">30 prochains jours</option>
            <option value="90">3 prochains mois</option>
            <option value="180">6 prochains mois</option>
          </select>
          <span className="transaction-count">{visible.length} occurrence{visible.length > 1 ? "s" : ""} · <span className="positive">{signed(totalIn)}</span> · <span className="negative">{signed(-totalOut)}</span></span>
        </div>

        {selectedItems.length > 0 && (
          <div className="transaction-bulkbar">
            <strong>{selectedItems.length} sélectionnée{selectedItems.length > 1 ? "s" : ""}</strong>
            <button className="secondary-button" onClick={() => setDrawer({ kind: "shift", items: selectedItems })} type="button">Décaler…</button>
            <button className="danger-button" onClick={() => setDrawer({ kind: "delete", items: selectedItems })} type="button">Supprimer…</button>
            <button aria-label="Désélectionner" className="transaction-bulk-clear" onClick={() => setSelectedIds([])} type="button">×</button>
          </div>
        )}

        <div className="transactions-table-wrap occurrence-table-wrap">
          <table className="transactions-table">
            <thead><tr>
              <th aria-sort={ariaSort(sort, "date")}><label className="transaction-select"><input aria-label="Sélectionner toutes les occurrences affichées" checked={allSelected} onChange={() => setSelectedIds(allSelected ? [] : selectable.map((item) => item.id))} type="checkbox" /><SortButton label="Date" onSort={toggleSort} sort={sort} sortKey="date" /></label></th>
              <th aria-sort={ariaSort(sort, "account")}><SortButton label="Compte" onSort={toggleSort} sort={sort} sortKey="account" /></th>
              <th aria-sort={ariaSort(sort, "label")}><SortButton label="Opération" onSort={toggleSort} sort={sort} sortKey="label" /></th>
              <th aria-sort={ariaSort(sort, "category")}><SortButton label="Catégorie" onSort={toggleSort} sort={sort} sortKey="category" /></th>
              <th aria-sort={ariaSort(sort, "status")}><SortButton label="Statut" onSort={toggleSort} sort={sort} sortKey="status" /></th>
              <th aria-sort={ariaSort(sort, "amount")}><SortButton label="Montant" onSort={toggleSort} sort={sort} sortKey="amount" /></th>
            </tr></thead>
            <tbody>
              {visible.length > 0 ? visible.map((item) => (
                <tr
                  className={item.status === "cancelled" ? "occurrence-row occurrence-row--deleted" : "occurrence-row"}
                  key={item.id}
                  onContextMenu={(event) => openMenu(event, item)}
                  onDoubleClick={() => item.canEdit && setDrawer({ kind: "edit", item })}
                >
                  <td>
                    <label className="transaction-select">
                      <input aria-label={`Sélectionner ${item.label} du ${formatDate(item.date)}`} checked={selectedIds.includes(item.id)} disabled={!item.canShift} onChange={() => setSelectedIds((current) => current.includes(item.id) ? current.filter((id) => id !== item.id) : [...current, item.id])} type="checkbox" />
                      <span>{formatDate(item.date)}</span>
                    </label>
                    {item.shifted && <small className="occurrence-note">Initialement {formatDate(item.originalDate)}</small>}
                  </td>
                  <td>{item.accountName}</td>
                  <td><strong>{item.label}</strong><small className="occurrence-note">{item.frequency}{item.edited ? " · modifiée" : ""}</small></td>
                  <td>{item.category}</td>
                  <td><span className={`transaction-pill transaction-pill--${STATUS_TONE[item.status] ?? "muted"}`}>{item.statusLabel}</span></td>
                  <td className={item.amount < 0 ? "transaction-amount transaction-amount--negative" : "transaction-amount transaction-amount--positive"}>{signed(item.amount)}</td>
                </tr>
              )) : (
                <tr><td className="transactions-empty" colSpan={6}>Aucune occurrence ne correspond aux filtres sélectionnés.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="occurrence-hint">Clic droit sur une ligne : modifier, décaler, supprimer ou rétablir. Les règles à l’origine des occurrences sont dans l’onglet « Règles de récurrence ».</p>
      </article>

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
      {drawer?.kind === "edit" && <EditDrawer categories={categories} item={drawer.item} onClose={() => setDrawer(undefined)} onDone={done} token={token} />}
      {drawer?.kind === "shift" && <ShiftDrawer items={drawer.items} onClose={() => setDrawer(undefined)} onDone={done} token={token} />}
      {drawer?.kind === "delete" && <DeleteDrawer items={drawer.items} onClose={() => setDrawer(undefined)} onDone={done} token={token} />}
    </div>
  );
}

function EditDrawer({ categories, item, onClose, onDone, token }: { categories: string[]; item: RecurrenceOccurrence; onClose: () => void; onDone: (message: string) => void; token: string }) {
  const [date, setDate] = useState(item.date);
  const [label, setLabel] = useState(item.label);
  const [category, setCategory] = useState(item.category);
  const [kind, setKind] = useState(item.amount >= 0 ? "credit" : "debit");
  const [amount, setAmount] = useState(String(Math.abs(item.amount)).replace(".", ","));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function save() {
    const value = Number(amount.replace(",", "."));
    if (!Number.isFinite(value) || value <= 0) { setError("Saisis un montant supérieur à zéro."); return; }
    setBusy(true);
    setError(undefined);
    try {
      const result = await updateRecurrenceOccurrence(token, item.id, { date, label, category, amount: kind === "credit" ? value : -value });
      onDone(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La modification a échoué.");
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Occurrence de récurrence"
      footer={(<><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} onClick={() => void save()} type="button">{busy ? "Enregistrement…" : "Enregistrer"}</button></>)}
      onClose={onClose}
      title="Modifier cette occurrence"
    >
      <p className="drawer-help">Seule cette occurrence change. La règle de récurrence « {item.label} » et les autres échéances restent identiques.</p>
      <label className="account-field"><span>Date</span><input onChange={(event) => setDate(event.target.value)} type="date" value={date} /></label>
      <label className="account-field"><span>Libellé</span><input onChange={(event) => setLabel(event.target.value)} value={label} /></label>
      <label className="account-field"><span>Catégorie</span><input list="occurrence-categories" onChange={(event) => setCategory(event.target.value)} value={category} /><datalist id="occurrence-categories">{categories.map((name) => <option key={name} value={name} />)}</datalist></label>
      <label className="account-field"><span>Type</span><select onChange={(event) => setKind(event.target.value)} value={kind}><option value="debit">Dépense</option><option value="credit">Recette</option></select></label>
      <label className="account-field"><span>Montant</span><div className="rules-input"><input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} value={amount} /><b>€</b></div></label>
      {item.shifted && <p className="drawer-help">Date d’origine de la règle : {formatDate(item.originalDate)}.</p>}
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}

function ShiftDrawer({ items, onClose, onDone, token }: { items: RecurrenceOccurrence[]; onClose: () => void; onDone: (message: string) => void; token: string }) {
  const [target, setTarget] = useState(items.length === 1 ? items[0].date : "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const single = items.length === 1 ? items[0] : undefined;

  async function save() {
    if (!target) { setError("Choisis la nouvelle date."); return; }
    setBusy(true);
    setError(undefined);
    try {
      onDone((await shiftRecurrenceOccurrences(token, items.map((item) => item.id), target)).message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Le décalage a échoué.");
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Occurrence de récurrence"
      footer={(<><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} onClick={() => void save()} type="button">{busy ? "Décalage…" : "Décaler"}</button></>)}
      onClose={onClose}
      title={items.length > 1 ? `Décaler ${items.length} occurrences` : "Décaler cette occurrence"}
    >
      <p className="drawer-help">{single ? `« ${single.label} » prévue le ${formatDate(single.date)}.` : "Toutes les occurrences sélectionnées seront déplacées à la même date."} La règle de récurrence n’est pas modifiée.</p>
      <label className="account-field"><span>Nouvelle date</span><input onChange={(event) => setTarget(event.target.value)} type="date" value={target} /></label>
      {single && (
        <div className="drawer-quick">
          {[1, 3, 7, 14].map((days) => <button className="secondary-button" key={days} onClick={() => setTarget(addDays(single.date, days))} type="button">+ {days} j</button>)}
        </div>
      )}
      {items.length > 1 && <ul className="drawer-list">{items.map((item) => <li key={item.id}>{formatDate(item.date)} · {item.label}</li>)}</ul>}
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}

function DeleteDrawer({ items, onClose, onDone, token }: { items: RecurrenceOccurrence[]; onClose: () => void; onDone: (message: string) => void; token: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  async function confirm() {
    setBusy(true);
    setError(undefined);
    try {
      onDone((await deleteRecurrenceOccurrences(token, items.map((item) => item.id))).message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La suppression a échoué.");
      setBusy(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Occurrence de récurrence"
      footer={(<><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button className="danger-button" disabled={busy} onClick={() => void confirm()} type="button">{busy ? "Suppression…" : "Supprimer"}</button></>)}
      onClose={onClose}
      title={items.length > 1 ? `Supprimer ${items.length} occurrences` : "Supprimer cette occurrence"}
    >
      <p className="drawer-help">Ces occurrences ne seront plus prévues et sortent du prévisionnel. Elles restent dans la liste (filtre « Supprimées / ignorées ») et peuvent être rétablies. La règle de récurrence n’est pas supprimée.</p>
      <ul className="drawer-list">{items.map((item) => <li key={item.id}>{formatDate(item.date)} · {item.label} · {signed(item.amount)}</li>)}</ul>
      {error && <p className="account-form-error" role="alert">{error}</p>}
    </SideDrawer>
  );
}

function ariaSort(sort: { key: SortKey; direction: "asc" | "desc" }, key: SortKey): "ascending" | "descending" | "none" {
  if (sort.key !== key) return "none";
  return sort.direction === "asc" ? "ascending" : "descending";
}

function SortButton({ label, onSort, sort, sortKey }: { label: string; onSort: (key: SortKey) => void; sort: { key: SortKey; direction: "asc" | "desc" }; sortKey: SortKey }) {
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
