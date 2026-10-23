import { useCallback, useEffect, useMemo, useState } from "react";

import { applyRuleSuggestions, dismissRuleSuggestion, getRuleSuggestions, previewRuleSuggestion } from "../api/client";
import type { RuleSuggestion, RuleSuggestionPreviewRow, RuleSuggestionsSnapshot, TransactionCategory } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code" });
const shortDate = new Intl.DateTimeFormat("fr-FR", { day: "2-digit", month: "2-digit" });

interface RuleSuggestionsTabProps {
  categories: TransactionCategory[];
  onApplied: () => void;
  token: string;
}

/** Onglet « Suggestions de catégorisation » : règles proposées d'après l'historique, validées par l'utilisateur. */
export function RuleSuggestionsTab({ categories, onApplied, token }: RuleSuggestionsTabProps) {
  const [snapshot, setSnapshot] = useState<RuleSuggestionsSnapshot>();
  const [reliability, setReliability] = useState(0.9);
  const [checked, setChecked] = useState<string[]>([]);
  const [error, setError] = useState<string>();
  const [notice, setNotice] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<ContextMenuState>();
  const [drawer, setDrawer] = useState<RuleSuggestion>();
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getRuleSuggestions(token, reliability, controller.signal)
      .then((data) => {
        setSnapshot(data);
        setChecked(data.suggestions.filter((item) => item.recommended).map((item) => item.key));
        setError(undefined);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Les suggestions ne peuvent pas être chargées.");
      });
    return () => controller.abort();
  }, [token, reliability, refreshKey]);

  const selected = useMemo(() => (snapshot?.suggestions ?? []).filter((item) => checked.includes(item.key)), [snapshot, checked]);

  function toggle(key: string) {
    setChecked((current) => current.includes(key) ? current.filter((item) => item !== key) : [...current, key]);
  }

  async function createChecked() {
    if (selected.length === 0) return;
    setBusy(true);
    setError(undefined);
    try {
      const items = await Promise.all(selected.map(async (item) => {
        const preview = await previewRuleSuggestion(token, item.matchValue, item.transactionType);
        return {
          match_value: item.matchValue,
          target_category_id: item.categoryId,
          transaction_type: item.transactionType,
          transaction_ids: preview.transactions.map((row) => row.id),
        };
      }));
      const result = await applyRuleSuggestions(token, items);
      setNotice(result.message);
      setRefreshKey((key) => key + 1);
      onApplied();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Les règles n’ont pas pu être créées.");
    } finally {
      setBusy(false);
    }
  }

  async function dismiss(item: RuleSuggestion) {
    try {
      await dismissRuleSuggestion(token, item.matchValue);
      setNotice(`Suggestion « ${item.matchValue} » ignorée.`);
      setRefreshKey((key) => key + 1);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La suggestion n’a pas pu être ignorée.");
    }
  }

  function openMenu(event: React.MouseEvent, item: RuleSuggestion) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Voir / modifier avant de créer…", onSelect: () => setDrawer(item) },
        { label: "Ignorer cette suggestion", onSelect: () => void dismiss(item) },
      ],
    });
  }

  if (!snapshot) {
    return error
      ? <section className="error-state"><strong>Les suggestions ne peuvent pas être affichées.</strong><p>{error}</p></section>
      : <div className="loading-state"><span aria-hidden="true" />Analyse de l’historique…</div>;
  }

  const items = snapshot.suggestions;
  const recommendedMatches = selected.reduce((sum, item) => sum + item.matches, 0);

  return (
    <section className="card rsg-panel">
      {notice && <div className="account-notice" role="status"><span aria-hidden="true">✓</span>{notice}</div>}
      {error && <div className="account-form-error" role="alert">{error}</div>}
      <header className="rsg-head">
        <div>
          <h2>Règles proposées à partir de votre historique</h2>
          <p>Une contrepartie vue au moins 3 fois, presque toujours dans la même catégorie. Rien n’est créé sans votre accord.</p>
        </div>
        <div className="rsg-head__actions">
          <select aria-label="Fiabilité minimale" onChange={(event) => setReliability(Number(event.target.value))} value={reliability}>
            <option value={0.8}>Fiabilité ≥ 80 %</option>
            <option value={0.9}>Fiabilité ≥ 90 %</option>
            <option value={1}>Fiabilité 100 %</option>
          </select>
          <button className="primary-button" disabled={busy || selected.length === 0} onClick={() => void createChecked()} type="button">
            {busy ? "Création…" : `Créer ${selected.length} règle${selected.length > 1 ? "s" : ""} cochée${selected.length > 1 ? "s" : ""}`}
          </button>
        </div>
      </header>

      <div className="rsg-kpis">
        <div><b>{items.length}</b> règle{items.length > 1 ? "s" : ""} suggérée{items.length > 1 ? "s" : ""}</div>
        <div><b className="rsg-kpis__accent">{recommendedMatches}</b> opération{recommendedMatches > 1 ? "s" : ""} « À catégoriser » classée{recommendedMatches > 1 ? "s" : ""} d’un coup</div>
        <div><b>{snapshot.discardedCount}</b> contrepartie{snapshot.discardedCount > 1 ? "s" : ""} écartée{snapshot.discardedCount > 1 ? "s" : ""} <span>(trop ambiguës)</span></div>
      </div>

      {items.length === 0 ? (
        <div className="rsg-empty">
          <strong>Aucune suggestion pour le moment</strong>
          <p>Catégorisez quelques opérations : dès qu’une contrepartie revient 3 fois dans la même catégorie, une règle sera proposée ici.</p>
        </div>
      ) : (
        <div className="rsg-table-wrap">
          <table className="rsg-table">
            <thead><tr><th aria-label="Sélection" /><th>Si le libellé contient</th><th>Catégorie</th><th>Fiabilité</th><th>Classerait</th><th>Vu</th></tr></thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.key} onContextMenu={(event) => openMenu(event, item)}>
                  <td><input aria-label={`Créer la règle ${item.matchValue}`} checked={checked.includes(item.key)} onChange={() => toggle(item.key)} type="checkbox" /></td>
                  <td><b>{item.matchValue}</b>{item.transactionType && <small> · {item.transactionType.toLowerCase()}s</small>}</td>
                  <td><span className={item.recommended ? "category-chip" : "category-chip category-chip--warning"}>{item.category}</span></td>
                  <td className={item.recommended ? "rsg-ok" : "rsg-warn"}>{Math.round(item.reliability * 100)} % <small>({item.agreeing}/{item.support})</small></td>
                  <td>
                    {item.matches > 0
                      ? <button className="rsg-link" onClick={() => setDrawer(item)} type="button">{item.matches} opération{item.matches > 1 ? "s" : ""} ›</button>
                      : <span className="rsg-muted">0 opération</span>}
                  </td>
                  <td className="rsg-muted">{item.support} fois</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="rsg-footnote">
        Les règles validées s’appliquent <b>aux opérations « À catégoriser » existantes</b> et à tous les prochains imports. Les opérations déjà catégorisées ne sont jamais modifiées. Clic droit sur une ligne : voir, modifier ou ignorer la suggestion.
      </p>

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}
      {drawer && (
        <RulePreviewDrawer
          categories={categories}
          item={drawer}
          onClose={() => setDrawer(undefined)}
          onCreated={(message) => {
            setDrawer(undefined);
            setNotice(message);
            setRefreshKey((key) => key + 1);
            onApplied();
          }}
          token={token}
        />
      )}
    </section>
  );
}

function RulePreviewDrawer({ categories, item, onClose, onCreated, token }: {
  categories: TransactionCategory[];
  item: RuleSuggestion;
  onClose: () => void;
  onCreated: (message: string) => void;
  token: string;
}) {
  const [matchValue, setMatchValue] = useState(item.matchValue);
  const [categoryId, setCategoryId] = useState(item.categoryId);
  const [rows, setRows] = useState<RuleSuggestionPreviewRow[]>([]);
  const [unchecked, setUnchecked] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const controller = new AbortController();
    const handle = window.setTimeout(() => {
      previewRuleSuggestion(token, matchValue, item.transactionType, controller.signal)
        .then((data) => { setRows(data.transactions); setUnchecked([]); setError(undefined); })
        .catch((cause: unknown) => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Aperçu indisponible."); });
    }, 250);
    return () => { window.clearTimeout(handle); controller.abort(); };
  }, [token, matchValue, item.transactionType]);

  const chosen = rows.filter((row) => !unchecked.includes(row.id));
  const categoryName = categories.find((category) => category.id === categoryId)?.name ?? item.category;

  const submit = useCallback(async () => {
    setBusy(true);
    setError(undefined);
    try {
      const result = await applyRuleSuggestions(token, [{
        match_value: matchValue.trim(),
        target_category_id: categoryId,
        transaction_type: item.transactionType,
        transaction_ids: chosen.map((row) => row.id),
      }]);
      onCreated(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La règle n’a pas pu être créée.");
    } finally {
      setBusy(false);
    }
  }, [token, matchValue, categoryId, item.transactionType, chosen, onCreated]);

  return (
    <SideDrawer
      eyebrow="Règle suggérée"
      footer={(
        <>
          <button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button>
          <button className="primary-button" disabled={busy || matchValue.trim().length < 3} onClick={() => void submit()} type="button">
            {busy ? "Création…" : `Créer la règle et classer ${chosen.length} opération${chosen.length > 1 ? "s" : ""}`}
          </button>
        </>
      )}
      onClose={onClose}
      title={`${matchValue || "…"} → ${categoryName}`}
    >
      <p className="rsg-drawer-lead">Vu {item.support} fois, {item.agreeing} fois classé « {item.category} ». Voici ce que la règle ferait.</p>
      <div className="rsg-drawer-fields">
        <label className="account-field"><span>Si le libellé contient</span><input onChange={(event) => setMatchValue(event.target.value)} value={matchValue} /></label>
        <label className="account-field"><span>Alors la catégorie est</span>
          <select onChange={(event) => setCategoryId(Number(event.target.value))} value={categoryId}>
            {categories.filter((category) => category.name && category.name !== "À catégoriser").map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
        </label>
      </div>
      {error && <div className="account-form-error" role="alert">{error}</div>}
      <div className="rsg-drawer-title">
        <span>{rows.length} opération{rows.length > 1 ? "s" : ""} « À catégoriser » seront classées</span>
        {rows.length > 0 && <button className="rsg-link" onClick={() => setUnchecked(unchecked.length === 0 ? rows.map((row) => row.id) : [])} type="button">{unchecked.length === 0 ? "Tout décocher" : "Tout cocher"}</button>}
      </div>
      {rows.length === 0 ? <p className="rsg-muted">Aucune opération en attente ne correspond. La règle servira aux prochains imports.</p> : (
        <table className="rsg-preview">
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td><input aria-label={`Classer ${row.label}`} checked={!unchecked.includes(row.id)} onChange={() => setUnchecked((current) => current.includes(row.id) ? current.filter((id) => id !== row.id) : [...current, row.id])} type="checkbox" /></td>
                <td>{shortDate.format(new Date(`${row.date}T12:00:00`))}</td>
                <td title={`${row.label} · ${row.account}`}>{row.label}</td>
                <td className={row.amount < 0 ? "amount amount--negative" : "amount amount--positive"}>{money.format(row.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="rsg-drawer-note">Les opérations déjà catégorisées ne sont jamais modifiées. Les prochains imports seront classés automatiquement.</p>
    </SideDrawer>
  );
}
