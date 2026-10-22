import { type FormEvent, useCallback, useEffect, useState } from "react";

import { createAsset, deleteAsset, getAssets, updateAsset } from "../api/client";
import { CategoryDrawer, DebtDrawer } from "./PatrimonyDrawers";
import { PatrimonyOverview } from "./PatrimonyOverview";
import type { AssetsSnapshot, PatrimonialAsset, PatrimonialAssetActionResult, PatrimonialAssetPayload } from "../api/contracts";

interface AssetsPageProps { editorRequestKey?: number; onDataChanged?: () => void; token: string; }
type Tab = "assets" | "liabilities";
type DrawerMode = "create" | "view" | "edit" | "delete";
interface DrawerState { asset?: PatrimonialAsset; kind: Tab; mode: DrawerMode; }
interface DetailField { key: string; label: string; type?: "date" | "number" | "text"; }
interface NatureDefinition { category: string; fields: DetailField[]; id: string; kind: Tab; label: string; }
interface AssetDraft { comment: string; details: Record<string, string>; name: string; natureId: string; valuationDate: string; valuationMode: string; value: number; }
const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", maximumFractionDigits: 0 });

const NATURES: NatureDefinition[] = [
  { id: "residence", kind: "assets", label: "Résidence principale", category: "Immobilier", fields: [{ key: "location", label: "Adresse ou commune" }, { key: "ownership", label: "Quote-part détenue" }, { key: "surface", label: "Surface (m²)", type: "number" }] },
  { id: "rental", kind: "assets", label: "Investissement locatif", category: "Immobilier", fields: [{ key: "location", label: "Adresse ou commune" }, { key: "occupancy", label: "Occupation" }, { key: "monthlyRent", label: "Loyer mensuel hors charges", type: "number" }] },
  { id: "scpi", kind: "assets", label: "SCPI / immobilier papier", category: "Immobilier papier", fields: [{ key: "manager", label: "Société de gestion" }, { key: "shares", label: "Nombre de parts", type: "number" }, { key: "yield", label: "Rendement annuel (%)", type: "number" }] },
  { id: "securities", kind: "assets", label: "PEA / compte-titres", category: "Placements financiers", fields: [{ key: "institution", label: "Établissement" }, { key: "envelope", label: "Enveloppe fiscale" }, { key: "holder", label: "Titulaire" }] },
  { id: "lifeInsurance", kind: "assets", label: "Assurance-vie / PER", category: "Assurance-vie", fields: [{ key: "institution", label: "Assureur ou établissement" }, { key: "contract", label: "Contrat" }, { key: "holder", label: "Titulaire" }] },
  { id: "business", kind: "assets", label: "Parts d’entreprise", category: "Participation", fields: [{ key: "company", label: "Société" }, { key: "ownership", label: "Part détenue (%)", type: "number" }, { key: "holder", label: "Titulaire" }] },
  { id: "valuable", kind: "assets", label: "Objets de valeur", category: "Objets de valeur", fields: [{ key: "itemKind", label: "Nature de l’objet" }, { key: "storage", label: "Lieu de conservation" }, { key: "insurance", label: "Assurance" }] },
  { id: "vehicle", kind: "assets", label: "Véhicule de collection", category: "Véhicules", fields: [{ key: "brand", label: "Marque / modèle" }, { key: "year", label: "Année", type: "number" }, { key: "registration", label: "Immatriculation" }] },
  { id: "otherAsset", kind: "assets", label: "Autre actif patrimonial", category: "Autres actifs", fields: [{ key: "holder", label: "Titulaire" }, { key: "reference", label: "Référence ou localisation" }] },
  { id: "mortgage", kind: "liabilities", label: "Crédit immobilier", category: "Crédit immobilier", fields: [{ key: "lender", label: "Banque prêteuse" }, { key: "initialAmount", label: "Capital emprunté", type: "number" }, { key: "rate", label: "Taux (%)", type: "number" }, { key: "monthlyPayment", label: "Mensualité", type: "number" }, { key: "endDate", label: "Date de fin", type: "date" }] },
  { id: "consumerLoan", kind: "liabilities", label: "Crédit à la consommation", category: "Crédit à la consommation", fields: [{ key: "lender", label: "Organisme prêteur" }, { key: "monthlyPayment", label: "Mensualité", type: "number" }, { key: "endDate", label: "Date de fin", type: "date" }] },
  { id: "familyDebt", kind: "liabilities", label: "Dette familiale", category: "Dette familiale", fields: [{ key: "creditor", label: "Créancier" }, { key: "repayment", label: "Modalité de remboursement" }] },
  { id: "taxDebt", kind: "liabilities", label: "Dette fiscale", category: "Dette fiscale", fields: [{ key: "creditor", label: "Administration ou créancier" }, { key: "dueDate", label: "Échéance", type: "date" }] },
  { id: "otherLiability", kind: "liabilities", label: "Autre dette", category: "Autres passifs", fields: [{ key: "creditor", label: "Créancier" }, { key: "dueDate", label: "Échéance", type: "date" }] },
];

export function AssetsPage({ editorRequestKey = 0, onDataChanged, token }: AssetsPageProps) {
  const [snapshot, setSnapshot] = useState<AssetsSnapshot>();
  const [drawer, setDrawer] = useState<DrawerState>();
  const [categoryName, setCategoryName] = useState<string>();
  const [debtId, setDebtId] = useState<number>();
  const [error, setError] = useState<string>();

  const load = useCallback(async () => {
    try {
      setSnapshot(await getAssets(token));
      setError(undefined);
    } catch (cause: unknown) { setError(messageFrom(cause)); }
  }, [token]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (editorRequestKey) setDrawer({ kind: "assets", mode: "create" }); }, [editorRequestKey]);

  async function completeChange(_result: PatrimonialAssetActionResult, _kind: Tab) {
    setDrawer(undefined);
    setCategoryName(undefined);
    setDebtId(undefined);
    await load();
    onDataChanged?.();
  }

  if (error) return <section className="error-state"><strong>Le patrimoine ne peut pas être affiché.</strong><p>{error}</p></section>;
  if (!snapshot) return <div className="loading-state"><span aria-hidden="true" />Calcul du patrimoine local…</div>;

  const category = snapshot.categories.find((item) => item.name === categoryName);
  const debt = snapshot.debts.find((item) => item.id === debtId);

  return <section className="assets-studio assets-studio--v2">
    <PatrimonyOverview onOpenCategory={setCategoryName} onOpenDebt={setDebtId} snapshot={snapshot} />
    {category && !drawer && <CategoryDrawer assets={snapshot.assets} category={category} colorIndex={snapshot.categories.indexOf(category)} onClose={() => setCategoryName(undefined)} onOpenAsset={(asset) => { setCategoryName(undefined); setDrawer({ asset, kind: "assets", mode: "view" }); }} />}
    {debt && !drawer && <DebtDrawer debt={debt} liability={snapshot.liabilities.find((item) => item.id === debt.id)} onClose={() => setDebtId(undefined)} onOpenAsset={(asset) => { setDebtId(undefined); setDrawer({ asset, kind: "liabilities", mode: "view" }); }} />}
    {drawer && <AssetDrawer asset={drawer.asset} kind={drawer.kind} mode={drawer.mode} onClose={() => setDrawer(undefined)} onCompleted={completeChange} onDelete={() => setDrawer((current) => current && { ...current, mode: "delete" })} onEdit={() => setDrawer((current) => current && { ...current, mode: "edit" })} token={token} />}
  </section>;
}

function AssetDrawer({ asset, kind, mode, onClose, onCompleted, onDelete, onEdit, token }: {
  asset?: PatrimonialAsset;
  kind: Tab;
  mode: DrawerMode;
  onClose: () => void;
  onCompleted: (result: PatrimonialAssetActionResult, kind: Tab) => Promise<void>;
  onDelete: () => void;
  onEdit: () => void;
  token: string;
}) {
  const [draft, setDraft] = useState<AssetDraft>(() => initialDraft(asset, kind));
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string>();
  const nature = findNature(draft.natureId, kind);
  const viewing = mode === "view";
  const deleting = mode === "delete";

  function field<Key extends keyof AssetDraft>(key: Key, value: AssetDraft[Key]) { setDraft((current) => ({ ...current, [key]: value })); }
  function detail(key: string, value: string) { setDraft((current) => ({ ...current, details: { ...current.details, [key]: value } })); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setFormError(undefined);
    try {
      const payload: PatrimonialAssetPayload = {
        name: draft.name.trim(), category: nature.category, assetType: nature.label, value: Math.abs(draft.value), valuationDate: draft.valuationDate,
        valuationMode: draft.valuationMode, comment: draft.comment.trim(), details: draft.details, status: "Actif",
      };
      const result = asset ? await updateAsset(token, asset.id, payload) : await createAsset(token, payload);
      await onCompleted(result, kind);
    } catch (cause: unknown) { setFormError(messageFrom(cause)); } finally { setBusy(false); }
  }

  async function confirmDeletion() {
    if (!asset) return;
    setBusy(true);
    setFormError(undefined);
    try { await onCompleted(await deleteAsset(token, asset.id), kind); } catch (cause: unknown) { setFormError(messageFrom(cause)); } finally { setBusy(false); }
  }

  const title = mode === "create" ? `Ajouter ${kind === "assets" ? "un actif" : "un passif"}` : mode === "edit" ? `Modifier ${kind === "assets" ? "l’actif" : "le passif"}` : mode === "delete" ? `Supprimer ${asset?.name}` : asset?.name;
  return <div className="asset-drawer-backdrop" onMouseDown={(event) => event.target === event.currentTarget && !busy && onClose()}><aside aria-labelledby="asset-drawer-title" aria-modal="true" className="asset-drawer" role="dialog"><header><div><span className="eyebrow">{kind === "assets" ? "Patrimoine · actif" : "Patrimoine · passif"}</span><h2 id="asset-drawer-title">{title}</h2></div><button aria-label="Fermer" disabled={busy} onClick={onClose} type="button">×</button></header>{deleting ? <div className="asset-drawer__delete"><p>La suppression est définitive. Les valorisations associées seront également retirées.</p><strong>{asset?.name}</strong><small>{asset?.type} · {money.format(Math.abs(asset?.value ?? 0))}</small>{formError && <div className="account-form-error" role="alert">{formError}</div>}<footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Conserver</button><button className="asset-delete-confirm" disabled={busy} onClick={() => void confirmDeletion()} type="button">{busy ? "Suppression…" : "Supprimer définitivement"}</button></footer></div> : viewing ? <div className="asset-drawer__view"><div className="asset-drawer__amount"><span>Valeur estimée</span><strong>{money.format(Math.abs(asset?.value ?? 0))}</strong><small>Valorisée le {formatDate(asset?.valuationDate ?? "")}</small></div><AssetDetails asset={asset} nature={findNatureForAsset(asset, kind)} /><div className="asset-drawer__view-actions"><button className="secondary-button" onClick={onDelete} type="button">Supprimer</button><button onClick={onEdit} type="button">Modifier</button></div></div> : <form onSubmit={(event) => void submit(event)}><div className="asset-drawer__form"><label className="asset-field asset-field--wide"><span>Nom *</span><input autoFocus maxLength={120} onChange={(event) => field("name", event.target.value)} required value={draft.name} /></label><label className="asset-field asset-field--wide"><span>Nature *</span><select onChange={(event) => field("natureId", event.target.value)} value={draft.natureId}>{NATURES.filter((option) => option.kind === kind).map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label><label className="asset-field"><span>{kind === "assets" ? "Valeur estimée" : "Capital restant dû"} *</span><input min="0" onChange={(event) => field("value", Number(event.target.value))} required step="0.01" type="number" value={draft.value} /></label><label className="asset-field"><span>Date de valorisation *</span><input onChange={(event) => field("valuationDate", event.target.value)} required type="date" value={draft.valuationDate} /></label>{nature.fields.map((definition) => <label className="asset-field" key={definition.key}><span>{definition.label}</span><input onChange={(event) => detail(definition.key, event.target.value)} type={definition.type ?? "text"} value={draft.details[definition.key] ?? ""} /></label>)}<label className="asset-field asset-field--wide"><span>Mode de valorisation</span><select onChange={(event) => field("valuationMode", event.target.value)} value={draft.valuationMode}><option>Manuelle</option><option>Estimation</option><option>Documentée</option></select></label><label className="asset-field asset-field--wide"><span>Note</span><textarea maxLength={800} onChange={(event) => field("comment", event.target.value)} rows={4} value={draft.comment} /></label></div>{formError && <div className="account-form-error" role="alert">{formError}</div>}<footer><button className="secondary-button" disabled={busy} onClick={onClose} type="button">Annuler</button><button disabled={busy} type="submit">{busy ? "Enregistrement…" : mode === "create" ? "Ajouter" : "Enregistrer"}</button></footer></form>}</aside></div>;
}

function AssetDetails({ asset, nature }: { asset?: PatrimonialAsset; nature: NatureDefinition }) {
  if (!asset) return null;
  return <dl className="asset-details"><div><dt>Nature</dt><dd>{asset.type}</dd></div><div><dt>Catégorie</dt><dd>{asset.category}</dd></div>{nature.fields.map((field) => <div key={field.key}><dt>{field.label}</dt><dd>{asset.details[field.key] || "Non renseigné"}</dd></div>)}{asset.comment && <div className="asset-details__note"><dt>Note</dt><dd>{asset.comment}</dd></div>}</dl>;
}

function initialDraft(asset: PatrimonialAsset | undefined, kind: Tab): AssetDraft {
  const nature = findNatureForAsset(asset, kind);
  return { name: asset?.name ?? "", natureId: nature.id, value: Math.abs(asset?.value ?? 0), valuationDate: asset?.valuationDate || today(), valuationMode: asset?.valuationMode || "Manuelle", comment: asset?.comment ?? "", details: asset?.details ?? {} };
}

function findNature(id: string, kind: Tab) { return NATURES.find((nature) => nature.id === id && nature.kind === kind) ?? NATURES.find((nature) => nature.kind === kind)!; }
function findNatureForAsset(asset: PatrimonialAsset | undefined, kind: Tab) { return NATURES.find((nature) => nature.kind === kind && (nature.label === asset?.type || nature.category === asset?.category)) ?? findNature("", kind); }
function signedPercent(value: number) { return `${value > 0 ? "+ " : ""}${value.toLocaleString("fr-FR")} %`; }
function formatDate(value: string) { const date = new Date(`${value}T12:00:00`); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("fr-FR").format(date); }
function today() { return new Date().toISOString().slice(0, 10); }
function monthLabel(value: string) { const date = new Date(`${value}T12:00:00`); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("fr-FR", { month: "short" }).format(date).replace(".", ""); }
function messageFrom(cause: unknown) { return cause instanceof Error ? cause.message : "Une erreur est survenue."; }
