import { useEffect, useMemo, useState } from "react";

import { createRecurrence, simulateForecast } from "../api/client";
import type { ForecastAccount, ForecastCategory, ForecastSimulationResult } from "../api/contracts";
import { SideDrawer } from "./SideDrawer";

interface ForecastSimulationDrawerProps {
  accounts: ForecastAccount[];
  categories: ForecastCategory[];
  defaultAccountId: string;
  onClose: () => void;
  onSaved: (message: string) => void;
  scenario: string;
  token: string;
}

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });

function addDays(base: Date, days: number): string {
  const copy = new Date(base);
  copy.setDate(copy.getDate() + days);
  return `${copy.getFullYear()}-${String(copy.getMonth() + 1).padStart(2, "0")}-${String(copy.getDate()).padStart(2, "0")}`;
}

function frDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-");
  return `${day}/${month}/${year}`;
}

function shortDate(value: string | null): string {
  if (!value) return "—";
  const [, month, day] = value.split("-");
  return `${day}/${month}`;
}

/** Volet « Et si ? » : simulation jetable, rien n'est enregistré sans demande explicite. */
export function ForecastSimulationDrawer({ accounts, categories, defaultAccountId, onClose, onSaved, scenario, token }: ForecastSimulationDrawerProps) {
  const activeAccounts = useMemo(() => accounts.filter((account) => account.status === "Actif"), [accounts]);
  const tomorrow = useMemo(() => addDays(new Date(), 1), []);
  const [kind, setKind] = useState<"Dépense" | "Recette">("Dépense");
  const [date, setDate] = useState(() => addDays(new Date(), 7));
  const [amount, setAmount] = useState("");
  const [accountId, setAccountId] = useState(defaultAccountId !== "all" && activeAccounts.some((a) => String(a.id) === defaultAccountId) ? defaultAccountId : "all");
  const [label, setLabel] = useState("");
  const [category, setCategory] = useState("");
  const [result, setResult] = useState<ForecastSimulationResult>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);

  const compatible = useMemo(() => {
    const expected = kind === "Recette" ? "Recette" : "Dépense";
    return categories.filter((item) => item.direction === expected || item.direction === "Neutre");
  }, [categories, kind]);

  useEffect(() => {
    if (!compatible.some((item) => item.name === category)) setCategory(compatible[0]?.name ?? "");
  }, [compatible, category]);

  const numericAmount = Number(amount.replace(/\s/g, "").replace(",", "."));
  const valid = Number.isFinite(numericAmount) && numericAmount > 0 && date >= tomorrow;

  useEffect(() => {
    if (!valid) {
      setResult(undefined);
      setError(date < tomorrow ? "La date doit être postérieure à aujourd’hui." : undefined);
      return;
    }
    const controller = new AbortController();
    setBusy(true);
    const timer = window.setTimeout(() => {
      simulateForecast(token, { kind, date, amount: numericAmount, accountId: accountId === "all" ? null : Number(accountId), label, scenario }, controller.signal)
        .then((data) => { setResult(data); setError(undefined); })
        .catch((cause: unknown) => {
          if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "La simulation a échoué.");
        })
        .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    }, 250);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [kind, date, numericAmount, accountId, label, scenario, token, valid, tomorrow]);

  async function save() {
    if (accountId === "all") { setError("Choisis un compte précis pour enregistrer la prévision."); return; }
    if (!category) { setError("Choisis une catégorie pour enregistrer la prévision."); return; }
    setSaving(true);
    try {
      const response = await createRecurrence(token, {
        accountId: Number(accountId),
        name: label.trim() || (kind === "Dépense" ? "Dépense simulée" : "Recette simulée"),
        category,
        direction: kind === "Dépense" ? "Débit" : "Crédit",
        amount: numericAmount,
        frequency: "Ponctuel",
        nextDate: date,
        endDate: "",
        scenario: "Réaliste",
      });
      onSaved(response.message);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "La prévision n’a pas pu être enregistrée.");
      setSaving(false);
    }
  }

  return (
    <SideDrawer
      eyebrow="Prévisionnel · Simulation"
      footer={(
        <>
          <button className="secondary-button" onClick={onClose} type="button">Fermer sans rien enregistrer</button>
          <button disabled={!valid || saving} onClick={() => void save()} type="button">{saving ? "Enregistrement…" : "Enregistrer comme prévision"}</button>
        </>
      )}
      onClose={onClose}
      title="Et si… ?"
    >
      <p className="drawer-help">Teste une dépense ou une recette avant de la décider. Rien n’est enregistré tant que tu ne le demandes pas.</p>
      <div className="sim-grid">
        <div className="account-field">
          <span>Type</span>
          <div className="sim-segmented" role="group" aria-label="Type">
            <button aria-pressed={kind === "Dépense"} className={kind === "Dépense" ? "is-active is-expense" : ""} onClick={() => setKind("Dépense")} type="button">Dépense</button>
            <button aria-pressed={kind === "Recette"} className={kind === "Recette" ? "is-active is-income" : ""} onClick={() => setKind("Recette")} type="button">Recette</button>
          </div>
        </div>
        <label className="account-field"><span>Date</span><input min={tomorrow} onChange={(event) => setDate(event.target.value)} type="date" value={date} /></label>
        <label className="account-field"><span>Montant</span><div className="rules-input"><input inputMode="decimal" onChange={(event) => setAmount(event.target.value)} placeholder="0,00" value={amount} /><b>EUR</b></div></label>
        <label className="account-field"><span>Compte</span>
          <select onChange={(event) => setAccountId(event.target.value)} value={accountId}>
            <option value="all">Tous les comptes</option>
            {activeAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
          </select>
        </label>
      </div>
      <div className="sim-grid">
        <label className="account-field"><span>Libellé</span><input onChange={(event) => setLabel(event.target.value)} placeholder="Ex. Achat véhicule" value={label} /></label>
        <label className="account-field"><span>Catégorie (pour l’enregistrement)</span>
          <select onChange={(event) => setCategory(event.target.value)} value={category}>
            {compatible.map((item) => <option key={item.id} value={item.name}>{item.name}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="account-form-error" role="alert">{error}</p>}
      {!result && !error && <p className="drawer-help">Saisis un montant pour voir l’effet sur ta trésorerie.</p>}
      {result && <SimulationResult busy={busy} onTryDate={setDate} result={result} />}
    </SideDrawer>
  );
}

function SimulationResult({ busy, onTryDate, result }: { busy: boolean; onTryDate: (date: string) => void; result: ForecastSimulationResult }) {
  const tone = result.verdict === "ko" ? "ko" : result.verdict === "ok" ? "ok" : "neutral";
  const threshold = result.threshold;
  let headline = "Cette décision passe";
  let detail = `Le solde reste au-dessus de ton seuil de sécurité (${money.format(threshold)}).`;
  if (result.verdict === "ko" && result.without.daysBelow > 0) {
    headline = "Cette décision ne passe pas";
    detail = `Ton solde est déjà sous le seuil de sécurité (${money.format(threshold)}) ${result.without.daysBelow} jour${result.without.daysBelow > 1 ? "s" : ""} ; cette opération le ferait descendre jusqu’à ${money.format(result.with.minBalance)}.`;
  } else if (result.verdict === "ko") {
    headline = "Cette décision ne passe pas";
    detail = `Le solde passerait sous ton seuil de sécurité (${money.format(threshold)}) pendant ${result.with.daysBelow} jour${result.with.daysBelow > 1 ? "s" : ""}, du ${shortDate(result.with.firstBelow)} au ${shortDate(result.with.lastBelow)}.`;
  } else if (result.verdict === "no_threshold") {
    headline = "Effet sur la trésorerie";
    detail = "Aucun seuil de sécurité n’est défini : règle-le depuis l’écran Prévisionnel pour savoir si la décision passe.";
  } else if (result.with.daysBelow > 0) {
    headline = "Cette décision n’aggrave pas la situation";
    detail = `Le solde reste sous le seuil ${result.with.daysBelow} jour${result.with.daysBelow > 1 ? "s" : ""}, comme sans l’opération.`;
  }
  return (
    <section className={`sim-result sim-result--${tone}`} aria-busy={busy}>
      <div className="sim-result__title"><span className="sim-dot" /><strong>{headline}</strong></div>
      <p>{detail}</p>
      <SimulationChart result={result} />
      <div className="sim-tiles">
        <div><small>Point bas</small><span>Sans : {money.format(result.without.minBalance)}</span><strong className={result.verdict === "ko" ? "is-bad" : ""}>Avec : {money.format(result.with.minBalance)}</strong></div>
        <div><small>Solde au {shortDate(result.series[result.series.length - 1]?.date ?? null)}</small><span>Sans : {money.format(result.without.finalBalance)}</span><strong>Avec : {money.format(result.with.finalBalance)}</strong></div>
      </div>
      {result.suggestion && (
        <div className="sim-tip">
          <strong>Piste :</strong> décaler l’opération au {frDate(result.suggestion.date)} ramène le point bas à {money.format(result.suggestion.minBalance)}{result.without.daysBelow > 0 ? " (sans aggraver la situation actuelle)" : ", au-dessus du seuil"}.
          <button className="secondary-button" onClick={() => onTryDate(result.suggestion!.date)} type="button">Tester cette date</button>
        </div>
      )}
    </section>
  );
}

function SimulationChart({ result }: { result: ForecastSimulationResult }) {
  const width = 400;
  const height = 110;
  const values = result.series.flatMap((point) => [point.without, point.with]);
  if (result.threshold > 0) values.push(result.threshold);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const x = (index: number) => (index / Math.max(1, result.series.length - 1)) * width;
  const y = (value: number) => height - 6 - ((value - min) / span) * (height - 14);
  const step = (key: "without" | "with") =>
    result.series.map((point, index) => (index === 0 ? `M${x(index).toFixed(1)} ${y(point[key]).toFixed(1)}` : `H${x(index).toFixed(1)} V${y(point[key]).toFixed(1)}`)).join(" ");
  return (
    <svg aria-label="Comparaison du solde avec et sans l’opération simulée" className="sim-chart" role="img" viewBox={`0 0 ${width} ${height}`}>
      {result.threshold > 0 && (
        <>
          <rect fill="var(--s-fee2e2)" height={Math.max(0, height - y(result.threshold))} opacity="0.6" width={width} x="0" y={y(result.threshold)} />
          <line stroke="#dc2626" strokeDasharray="5 4" strokeWidth="1.5" x1="0" x2={width} y1={y(result.threshold)} y2={y(result.threshold)} />
        </>
      )}
      <path d={step("without")} fill="none" stroke="#2563eb" strokeWidth="2.2" />
      <path d={step("with")} fill="none" stroke={result.verdict === "ko" ? "#dc2626" : "#7c3aed"} strokeWidth="2.2" />
    </svg>
  );
}
