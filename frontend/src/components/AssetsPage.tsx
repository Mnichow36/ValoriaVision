import { useEffect, useMemo, useState } from "react";

import { getAssets } from "../api/client";
import type { AssetEvolutionPoint, AssetsSnapshot, PatrimonialAsset } from "../api/contracts";
import { InteractiveDonutChart, InteractiveLineChart } from "./InteractiveCharts";

interface AssetsPageProps {
  token: string;
}

const money = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  currencyDisplay: "code",
  maximumFractionDigits: 0,
});

export function AssetsPage({ token }: AssetsPageProps) {
  const [snapshot, setSnapshot] = useState<AssetsSnapshot>();
  const [selectedAssetId, setSelectedAssetId] = useState<number>();
  const [error, setError] = useState<string>();
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    getAssets(token, controller.signal)
      .then((data) => {
        setSnapshot(data);
        setSelectedAssetId((current) => data.assets.some((asset) => asset.id === current)
          ? current
          : data.leadingAssetId ?? data.assets[0]?.id);
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : "Le patrimoine ne peut pas être chargé.");
        }
      });
    return () => controller.abort();
  }, [refreshKey, token]);

  const selectedAsset = snapshot?.assets.find((asset) => asset.id === selectedAssetId) ?? snapshot?.assets[0];
  const selectedWeight = snapshot && selectedAsset && snapshot.summary.totalAssets
    ? Math.max(0, Math.min(100, selectedAsset.value / snapshot.summary.totalAssets * 100))
    : 0;

  const familyAssetIds = useMemo(() => {
    const result = new Map<string, number>();
    snapshot?.assets.forEach((asset) => {
      if (!result.has(asset.category)) result.set(asset.category, asset.id);
    });
    return result;
  }, [snapshot]);

  if (error) {
    return (
      <section className="error-state">
        <strong>Le patrimoine ne peut pas être affiché.</strong>
        <p>{error}</p>
        <button className="secondary-button" onClick={() => setRefreshKey((key) => key + 1)} type="button">Réessayer</button>
      </section>
    );
  }

  if (!snapshot) {
    return <div className="loading-state"><span aria-hidden="true" />Calcul du patrimoine par le moteur Python…</div>;
  }

  return (
    <div className="assets-page">
      <section className="assets-kpis" aria-label="Indicateurs patrimoniaux">
        <AssetKpi detail={`${snapshot.summary.assetCount} élément(s) actif(s)`} label="Actifs" tone="purple" value={money.format(snapshot.summary.totalAssets)} />
        <AssetKpi detail={`${snapshot.summary.liabilityCount} crédit(s) ou dette(s)`} label="Passifs" tone="red" value={money.format(snapshot.summary.totalLiabilities)} />
        <AssetKpi detail={`${signedPercent(snapshot.summary.changePercent)} sur l’historique affiché`} label="Net" tone="green" value={money.format(snapshot.summary.netWorth)} />
        <AssetKpi detail="Disponible immédiatement" label="Liquidités" tone="cyan" value={money.format(snapshot.summary.liquidities)} />
      </section>

      <section className="assets-main-grid">
        <article className="card assets-evolution-card">
          <div className="assets-heading"><h2>Évolution du patrimoine net</h2><p>Historique réel des valorisations consolidées.</p></div>
          <AssetsEvolutionChart points={snapshot.evolution} />
          <div className="assets-chart-legend"><span><i className="assets-dot assets-dot--net" />Net</span><span><i className="assets-dot assets-dot--assets" />Actifs</span><span><i className="assets-dot assets-dot--liabilities" />Passifs</span></div>
          <div className="assets-family-table-wrap">
            <table className="assets-family-table">
              <thead><tr><th>Famille</th><th>Valeur</th><th>Poids</th><th>Statut</th></tr></thead>
              <tbody>
                {snapshot.families.length > 0 ? snapshot.families.slice(0, 5).map((family) => (
                  <tr key={family.name}>
                    <td><button onClick={() => setSelectedAssetId(familyAssetIds.get(family.name))} type="button">{family.name}</button></td>
                    <td>{money.format(family.value)}</td>
                    <td>{family.weight.toLocaleString("fr-FR")} %</td>
                    <td><span className={family.status === "Disponible" ? "assets-status assets-status--available" : "assets-status"}>{family.status}</span></td>
                  </tr>
                )) : <tr><td className="assets-empty-row" colSpan={4}>Aucun actif enregistré.</td></tr>}
              </tbody>
            </table>
          </div>
        </article>

        <AssetDetail asset={selectedAsset} selectedWeight={selectedWeight} totalAssets={snapshot.summary.totalAssets} />
      </section>
    </div>
  );
}

function AssetKpi({ detail, label, tone, value }: { detail: string; label: string; tone: string; value: string }) {
  return (
    <article className="card asset-kpi">
      <div><span>{label}</span><i className={`asset-kpi__mark asset-kpi__mark--${tone}`} /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function AssetDetail({ asset, selectedWeight, totalAssets }: { asset?: PatrimonialAsset; selectedWeight: number; totalAssets: number }) {
  if (!asset) {
    return <aside className="card asset-detail"><div className="assets-heading"><h2>Volet actif</h2><p>Aucun actif disponible.</p></div></aside>;
  }
  const otherAssets = Math.max(0, totalAssets - asset.value);
  return (
    <aside className="card asset-detail">
      <div className="assets-heading"><h2>Volet actif</h2><p>{asset.name} · {selectedWeight.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % du portefeuille.</p></div>
      <InteractiveDonutChart
        ariaLabel={`Poids de ${asset.name} dans les actifs`}
        showLegend={false}
        slices={[
          { label: asset.name, value: asset.value, color: "#2563eb" },
          { label: "Autres actifs", value: otherAssets, color: "#dfe6ef" },
        ]}
        valueFormatter={compactMoney}
      />
      <dl>
        <div><dt>Type</dt><dd>{asset.type}</dd></div>
        <div><dt>Valeur estimée</dt><dd>{money.format(asset.value)}</dd></div>
        <div><dt>Crédit associé</dt><dd>Non renseigné</dd></div>
        <div><dt>Date de valorisation</dt><dd>{formatDate(asset.valuationDate)}</dd></div>
        <div><dt>Mode</dt><dd>{asset.valuationMode}</dd></div>
      </dl>
      {asset.comment && <p className="asset-detail__comment">{asset.comment}</p>}
      <button aria-disabled="true" disabled title="Modification de valorisation prévue dans l’incrément d’écriture" type="button">Modifier la valorisation</button>
    </aside>
  );
}

function AssetsEvolutionChart({ points }: { points: AssetEvolutionPoint[] }) {
  if (points.length < 2) return <div className="assets-chart-empty">Ajoutez au moins deux valorisations pour afficher une évolution.</div>;
  return (
    <InteractiveLineChart
      ariaLabel="Évolution des actifs, passifs et du patrimoine net"
      series={[
        {
          id: "net",
          label: "Patrimoine net",
          color: "#2563eb",
          area: true,
          points: points.map((point) => ({ date: point.date, value: point.net })),
        },
        {
          id: "assets",
          label: "Actifs",
          color: "#7c3aed",
          points: points.map((point) => ({ date: point.date, value: point.assets })),
        },
        {
          id: "liabilities",
          label: "Passifs",
          color: "#e11d48",
          dashed: true,
          points: points.map((point) => ({ date: point.date, value: point.liabilities })),
        },
      ]}
      valueFormatter={compactMoney}
    />
  );
}

function compactMoney(value: number): string {
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000).toLocaleString("fr-FR")} kEUR`;
  return money.format(value);
}

function signedPercent(value: number): string {
  return `${value > 0 ? "+ " : value < 0 ? "- " : ""}${Math.abs(value).toLocaleString("fr-FR")} %`;
}

function formatDate(value: string): string {
  const parsed = new Date(`${value}T12:00:00`);
  return Number.isNaN(parsed.getTime()) ? value : new Intl.DateTimeFormat("fr-FR").format(parsed);
}
