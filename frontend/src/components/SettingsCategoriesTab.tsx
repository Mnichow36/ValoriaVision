import { useCanWrite } from "../permissions";
import { useMemo, useState } from "react";

import { createSettingsCategory, deleteSettingsCategory, updateSettingsCategory } from "../api/client";
import type { SettingsCategory, SettingsCategoryPayload } from "../api/contracts";
import { ContextMenu, type ContextMenuState } from "./ContextMenu";
import { SideDrawer } from "./SideDrawer";

type Filter = "all" | "Dépense" | "Recette" | "Neutre";

interface CategoryForm {
  name: string;
  kind: string;
  direction: string;
  color: string;
  budgetEnabled: boolean;
}

const emptyForm = (): CategoryForm => ({ name: "", kind: "Dépense", direction: "Dépense", color: "#64748B", budgetEnabled: true });

const formOf = (category: SettingsCategory): CategoryForm => ({
  name: category.name,
  kind: category.kind,
  direction: category.direction,
  color: category.color,
  budgetEnabled: category.budgetEnabled,
});

interface Props {
  categories: SettingsCategory[];
  onChanged: (message: string) => Promise<void>;
  onShowOperations: (categoryName: string) => void;
  token: string;
}

/** Paramètres › Catégories : tableau plein écran, actions par clic droit, édition dans un volet latéral. */
export function SettingsCategoriesTab({ categories, onChanged, onShowOperations, token }: Props) {
  const canWrite = useCanWrite();
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [menu, setMenu] = useState<ContextMenuState>();
  const [editing, setEditing] = useState<SettingsCategory | "new">();
  const [removing, setRemoving] = useState<SettingsCategory>();
  const [form, setForm] = useState<CategoryForm>(emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const counts = useMemo(() => ({
    all: categories.length,
    Dépense: categories.filter((item) => item.direction === "Dépense").length,
    Recette: categories.filter((item) => item.direction === "Recette").length,
    Neutre: categories.filter((item) => item.direction === "Neutre").length,
  }), [categories]);
  const used = categories.filter((item) => item.usage.transactions > 0).length;
  const inBudgets = categories.filter((item) => item.budgetEnabled).length;
  const unused = categories.filter((item) => item.usage.transactions + item.usage.recurrences + item.usage.budgets === 0).length;

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return categories.filter((item) => (filter === "all" || item.direction === filter) && (!needle || item.name.toLowerCase().includes(needle)));
  }, [categories, filter, search]);

  function open(target: SettingsCategory | "new") {
    setEditing(target);
    setForm(target === "new" ? emptyForm() : formOf(target));
    setError("");
  }

  function openMenu(event: React.MouseEvent, category: SettingsCategory) {
    event.preventDefault();
    setMenu({
      x: event.clientX,
      y: event.clientY,
      items: [
        { label: "Modifier…", onSelect: () => open(category) },
        { label: "Voir ses opérations", onSelect: () => onShowOperations(category.name), disabled: category.usage.transactions === 0 },
        { label: "Supprimer…", danger: true, disabled: category.isSystem, onSelect: () => { setRemoving(category); setError(""); } },
      ],
      note: category.isSystem ? "Catégorie système : elle ne peut pas être supprimée." : undefined,
    });
  }

  async function save() {
    if (!editing) return;
    const payload: SettingsCategoryPayload = {
      name: form.name,
      kind: form.kind,
      direction: form.direction,
      color: form.color,
      budget_enabled: form.budgetEnabled,
    };
    setBusy(true);
    setError("");
    try {
      const result = editing === "new" ? await createSettingsCategory(token, payload) : await updateSettingsCategory(token, editing.id, payload);
      setEditing(undefined);
      await onChanged(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La catégorie n’a pas pu être enregistrée.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!removing) return;
    setBusy(true);
    setError("");
    try {
      const result = await deleteSettingsCategory(token, removing.id);
      setRemoving(undefined);
      await onChanged(result.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La catégorie n’a pas pu être supprimée.");
    } finally {
      setBusy(false);
    }
  }

  const filters: Array<{ id: Filter; label: string }> = [
    { id: "all", label: "Toutes" },
    { id: "Dépense", label: "Dépenses" },
    { id: "Recette", label: "Revenus" },
    { id: "Neutre", label: "Neutres" },
  ];

  return (
    <article className="card stg-panel">
      <div className="stg-toolbar">
        <div className="stg-toolbar__left">
          <input aria-label="Rechercher une catégorie" onChange={(event) => setSearch(event.target.value)} placeholder="Rechercher une catégorie…" value={search} />
          <div className="stg-segment" role="group" aria-label="Filtrer par sens">
            {filters.map((item) => (
              <button aria-pressed={filter === item.id} key={item.id} onClick={() => setFilter(item.id)} type="button">{item.label} · {counts[item.id]}</button>
            ))}
          </div>
        </div>
        {canWrite && <button className="stg-primary" onClick={() => open("new")} type="button">Nouvelle catégorie</button>}
      </div>

      <div className="stg-kpis stg-kpis--4">
        <div><b>{categories.length}</b> catégories</div>
        <div><b>{used}</b> utilisées dans les opérations</div>
        <div><b>{inBudgets}</b> disponibles dans les budgets</div>
        <div className={unused > 0 ? "stg-kpis__warn" : undefined}><b>{unused}</b> jamais utilisées</div>
      </div>

      <div className="stg-table-wrap">
        <table className="stg-table">
          <thead>
            <tr><th>Catégorie</th><th>Sens</th><th className="num">Opérations</th><th className="num">Récurrences</th><th className="num">Budgets</th><th>Budget</th></tr>
          </thead>
          <tbody>
            {visible.map((category) => (
              <tr key={category.id} onContextMenu={(event) => openMenu(event, category)} onDoubleClick={() => { if (canWrite) open(category); }} title={canWrite ? "Double-clic : modifier · clic droit : actions" : undefined}>
                <td><span className="stg-dot" style={{ background: category.color }} /><strong>{category.name}</strong>{category.isSystem && <small className="stg-badge">système</small>}</td>
                <td>{category.direction === "Recette" ? "Revenu" : category.direction}</td>
                <td className={category.usage.transactions === 0 ? "num stg-zero" : "num"}>{category.usage.transactions}</td>
                <td className="num">{category.usage.recurrences}</td>
                <td className="num">{category.usage.budgets}</td>
                <td className={category.budgetEnabled ? "stg-yes" : "stg-no"}>{category.budgetEnabled ? "Oui" : "Non"}</td>
              </tr>
            ))}
            {visible.length === 0 && <tr><td className="stg-empty" colSpan={6}>Aucune catégorie ne correspond à la recherche.</td></tr>}
          </tbody>
        </table>
      </div>

      <p className="stg-footnote">Clic droit sur une catégorie : Modifier… · Voir ses opérations · Supprimer (impossible pour une catégorie système ; les usages d’une autre sont réaffectés à « À catégoriser »). Double-clic : modifier.</p>

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(undefined)} />}

      {editing && (
        <SideDrawer
          eyebrow="CATÉGORIES"
          footer={<><button className="secondary-button" onClick={() => setEditing(undefined)} type="button">Annuler</button><button className="primary-button" disabled={busy || !form.name.trim()} form="stg-category-form" type="submit">Enregistrer</button></>}
          onClose={() => setEditing(undefined)}
          title={editing === "new" ? "Nouvelle catégorie" : `Modifier « ${editing.name} »`}
        >
          <form className="stg-form" id="stg-category-form" onSubmit={(event) => { event.preventDefault(); void save(); }}>
            {error && <p className="stg-error" role="alert">{error}</p>}
            <label>Nom<input autoFocus onChange={(event) => setForm({ ...form, name: event.target.value })} required value={form.name} /></label>
            <div className="stg-form__row">
              <label>Type<select onChange={(event) => setForm({ ...form, kind: event.target.value })} value={form.kind}><option>Revenu</option><option>Dépense</option><option>Neutre</option></select></label>
              <label>Sens<select onChange={(event) => setForm({ ...form, direction: event.target.value })} value={form.direction}><option value="Recette">Recette</option><option>Dépense</option><option>Neutre</option></select></label>
            </div>
            <label>Couleur<span className="stg-color"><input onChange={(event) => setForm({ ...form, color: event.target.value })} type="color" value={form.color} /><input onChange={(event) => setForm({ ...form, color: event.target.value })} value={form.color} /></span></label>
            <label className="stg-check"><input checked={form.budgetEnabled} onChange={(event) => setForm({ ...form, budgetEnabled: event.target.checked })} type="checkbox" />Disponible dans les budgets</label>
            <p className="stg-hint">Le sens pilote le signe des saisies manuelles.</p>
          </form>
        </SideDrawer>
      )}

      {removing && (
        <SideDrawer
          eyebrow="CATÉGORIES"
          footer={<><button className="secondary-button" onClick={() => setRemoving(undefined)} type="button">Annuler</button><button className="primary-button stg-danger-btn" disabled={busy} onClick={() => void remove()} type="button">Supprimer la catégorie</button></>}
          onClose={() => setRemoving(undefined)}
          title={`Supprimer « ${removing.name} » ?`}
        >
          {error && <p className="stg-error" role="alert">{error}</p>}
          <p className="stg-hint">Cette action réaffecte automatiquement les usages de la catégorie :</p>
          <ul className="stg-impact">
            <li><b>{removing.usage.transactions}</b> opération(s) repasseront en « À catégoriser »</li>
            <li><b>{removing.usage.recurrences}</b> récurrence(s) seront rattachées à « À catégoriser »</li>
            <li><b>{removing.usage.budgets}</b> budget(s) seront supprimés</li>
          </ul>
        </SideDrawer>
      )}
    </article>
  );
}
