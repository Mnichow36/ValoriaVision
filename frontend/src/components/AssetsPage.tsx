import { useEffect, useMemo, useState } from "react";

import { getAssets } from "../api/client";
import type { AssetEvolutionPoint, AssetsSnapshot, PatrimonialAsset } from "../api/contracts";

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

        <AssetDetail asset={selectedAsset} selectedWeight={selectedWeight} />
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

function AssetDetail({ asset, selectedWeight }: { asset?: PatrimonialAsset; selectedWeight: number }) {
  if (!asset) {
    return <aside className="card asset-detail"><div className="assets-heading"><h2>Volet actif</h2><p>Aucun actif disponible.</p></div></aside>;
  }
  const gradient = `conic-gradient(#2563eb 0 ${selectedWeight}%, #7c3aed ${selectedWeight}% ${Math.min(100, selectedWeight + 8)}%, #dfe6ef ${Math.min(100, selectedWeight + 8)}% 100%)`;
  return (
    <aside className="card asset-detail">
      <div className="assets-heading"><h2>Volet actif</h2><p>{asset.name}.</p></div>
      <div className="asset-detail__donut" style={{ background: gradient }}><div><strong>{compactMoney(asset.value)}</strong><span>Valeur</span></div></div>
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
  const width = 720;
  const height = 220;
  const padding = 28;
  const values = points.flatMap((point) => [point.net, point.assets, point.liabilities, 0]);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const range = maximum - minimum || 1;
  const x = (index: number) => padding + index * ((width - padding * 2) / Math.max(1, points.length - 1));
  const y = (value: number) => padding + (maximum - value) / range * (height - padding * 2);
  const path = (selector: (point: AssetEvolutionPoint) => number) => points.map((point, index) => `${index ? "L" : "M"}${x(index)},${y(selector(point))}`).join(" ");
  return (
    <div className="assets-chart">
      <svg aria-label="Évolution des actifs, passifs et du patrimoine net" role="img" viewBox={`0 0 ${width} ${height}`}>
        {[0, 1, 2, 3].map((line) => <line className="assets-chart__grid" key={line} x1={padding} x2={width - padding} y1={padding + line * ((height - padding * 2) / 3)} y2={padding + line * ((height - padding * 2) / 3)} />)}
        <path className="assets-chart__line assets-chart__line--assets" d={path((point) => point.assets)} />
        <path className="assets-chart__line assets-chart__line--net" d={path((point) => point.net)} />
        <path className="assets-chart__line assets-chart__line--liabilities" d={path((point) => point.liabilities)} />
        {points.map((point, index) => <circle className="assets-chart__point" cx={x(index)} cy={y(point.net)} key={point.date} r="4" />)}
      </svg>
      <div className="assets-chart__dates"><span>{formatDate(points[0].date)}</span><span>{formatDate(points[points.length - 1].date)}</span></div>
    </div>
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
