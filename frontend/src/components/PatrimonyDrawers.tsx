import type { AssetCategoryInsight, AssetDebtInsight, AssetSeriesPoint, PatrimonialAsset } from "../api/contracts";
import { categoryColor, formatDay } from "./PatrimonyOverview";
import { SideDrawer } from "./SideDrawer";

const money = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR", currencyDisplay: "code", maximumFractionDigits: 0 });

function pct(value: number | null): string {
  return value === null ? "—" : `${value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`;
}

function signedMoney(value: number): string {
  return `${value > 0 ? "+ " : value < 0 ? "- " : ""}${money.format(Math.abs(value))}`;
}

function Stat({ hint, label, tone, value }: { hint?: string; label: string; tone?: "good" | "bad"; value: string }) {
  return (
    <div className="pat-stat">
      <small>{label}</small>
      <strong className={tone ? `pat-${tone}` : ""}>{value}</strong>
      {hint && <span>{hint}</span>}
    </div>
  );
}

function MiniSeries({ color, label, points }: { color: string; label: string; points: AssetSeriesPoint[] }) {
  if (points.length < 2) return null;
  const values = points.map((point) => point.value);
  let min = Math.min(...values);
  let max = Math.max(...values);
  if (max === min) { max += 1; min -= 1; }
  const x = (index: number) => (index / (points.length - 1)) * 396 + 2;
  const y = (value: number) => 108 - ((value - min) / (max - min)) * 92;
  const line = points.map((point, index) => `${index === 0 ? "M" : "L"}${x(index).toFixed(1)} ${y(point.value).toFixed(1)}`).join(" ");
  return (
    <svg aria-label={label} className="pat-mini" role="img" viewBox="0 0 400 120">
      <line stroke="var(--s-e3e9f3)" x1="0" x2="400" y1="30" y2="30" />
      <line stroke="var(--s-e3e9f3)" x1="0" x2="400" y1="80" y2="80" />
      <path d={`${line} L398 116 L2 116 Z`} fill={color} opacity="0.12" />
      <path d={line} fill="none" stroke={color} strokeLinejoin="round" strokeWidth="2.4" />
      <circle cx={x(points.length - 1)} cy={y(points[points.length - 1].value)} fill="#fff" r="4.5" stroke={color} strokeWidth="2.4" />
    </svg>
  );
}

export function CategoryDrawer({ assets, category, colorIndex, onClose, onOpenAsset }: {
  assets: PatrimonialAsset[];
  category: AssetCategoryInsight;
  colorIndex: number;
  onClose: () => void;
  onOpenAsset: (asset: PatrimonialAsset) => void;
}) {
  const color = categoryColor(category.name, colorIndex);
  const members = assets.filter((asset) => category.assetIds.includes(asset.id));
  const change = category.change;
  const footer = (
    <>
      <button className="secondary-button" onClick={onClose} type="button">Fermer</button>
      {members.length === 1 && <button onClick={() => onOpenAsset(members[0])} type="button">Ouvrir la fiche de l’actif</button>}
    </>
  );
  return (
    <SideDrawer eyebrow="Patrimoine · catégorie" footer={footer} onClose={onClose} title={category.name}>
      <div className="pat-stats">
        <Stat hint={`${category.weight.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % des actifs`} label="Valeur actuelle" value={money.format(category.value)} />
        {category.isCash ? (
          <Stat hint="Calculé en direct depuis tes comptes" label="Variation" tone={change && change.amount < 0 ? "bad" : "good"} value={change ? signedMoney(change.amount) : "—"} />
        ) : (
          <Stat hint={change?.percent !== null && change ? `${change.percent! > 0 ? "+ " : ""}${pct(change.percent)} sur la période` : "Aucun actif présent au départ"} label="Plus-value" tone={change ? (change.amount < 0 ? "bad" : "good") : undefined} value={change ? signedMoney(change.amount) : "—"} />
        )}
        <Stat hint={category.tri === null ? category.triReason : undefined} label="TRI" value={category.tri === null ? "non disponible" : pct(category.tri)} />
        <Stat hint={category.volatility === null ? category.volatilityReason : undefined} label="Volatilité" value={category.volatility === null ? "non disponible" : pct(category.volatility)} />
      </div>
      <h3 className="pat-drawer-title">Valeur sur la période</h3>
      <MiniSeries color={color} label={`Valeur de ${category.name}`} points={category.series} />
      {!category.isCash && (
        <>
          <h3 className="pat-drawer-title">Actifs de la catégorie</h3>
          <div className="pat-asset-list">
            {members.map((asset) => (
              <button key={asset.id} onClick={() => onOpenAsset(asset)} type="button">
                <span><b>{asset.name}</b><small>Valorisé le {formatDay(asset.valuationDate)}</small></span>
                <strong>{money.format(Math.abs(asset.value))}</strong>
              </button>
            ))}
          </div>
        </>
      )}
      <p className="pat-note">Le TRI exige les versements et la volatilité au moins 7 valorisations saisies. Sans ces données, ils affichent « non disponible » plutôt qu’un chiffre estimé.</p>
    </SideDrawer>
  );
}

export function DebtDrawer({ debt, liability, onClose, onOpenAsset }: {
  debt: AssetDebtInsight;
  liability?: PatrimonialAsset;
  onClose: () => void;
  onOpenAsset: (asset: PatrimonialAsset) => void;
}) {
  const repaid = debt.repaidPercent;
  const footer = (
    <>
      <button className="secondary-button" onClick={onClose} type="button">Fermer</button>
      {liability && <button onClick={() => onOpenAsset(liability)} type="button">Ouvrir la fiche du passif</button>}
    </>
  );
  return (
    <SideDrawer eyebrow="Patrimoine · passif" footer={footer} onClose={onClose} title={debt.name}>
      <div className="pat-debt-hero">
        <small>Capital restant dû</small>
        <strong>{money.format(debt.balance)}</strong>
        {repaid !== null && debt.initialAmount !== null ? (
          <>
            <div aria-label={`${repaid} % du capital déjà remboursé`} className="pat-debt-hero__bar" role="img"><i style={{ flex: repaid }} /><b style={{ flex: 100 - repaid }} /></div>
            <div className="pat-debt-hero__legend"><span>{pct(repaid)} remboursé</span><span>Capital initial {money.format(debt.initialAmount)}</span></div>
          </>
        ) : (
          <p>Renseigne le capital emprunté dans la fiche pour suivre la part remboursée.</p>
        )}
      </div>
      <div className="pat-stats">
        <Stat label="Taux" value={debt.rate === null ? "non renseigné" : pct(debt.rate)} />
        <Stat label="Mensualité" value={debt.monthlyPayment === null ? "non renseignée" : money.format(debt.monthlyPayment)} />
        <Stat hint={debt.monthsLeft !== null ? `${debt.monthsLeft} mois restants` : undefined} label="Échéance finale" value={debt.endDate ? formatDay(debt.endDate) : "non renseignée"} />
        <Stat hint={debt.interestLeft === null ? "Mensualité et échéance requises" : "Estimation : mensualités restantes − capital"} label="Intérêts restants" value={debt.interestLeft === null ? "non disponible" : `≈ ${money.format(debt.interestLeft)}`} />
      </div>
      <h3 className="pat-drawer-title">Capital restant dû dans le temps</h3>
      <MiniSeries color="#dc2626" label="Capital restant dû" points={debt.series} />
      <p className="pat-note">Cette dette représente {debt.shareOfAssets.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % de tes actifs. Elle est déjà comptée dans le patrimoine net.</p>
    </SideDrawer>
  );
}
