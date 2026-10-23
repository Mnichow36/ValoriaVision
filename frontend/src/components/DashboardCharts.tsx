import { SideDrawer } from "./SideDrawer";

export interface ChartItem {
  label: string;
  value: number;
  color?: string;
}

interface Placed extends ChartItem {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Treemap « squarified » (Bruls et al.) : rectangles proches du carré, aire proportionnelle à la valeur. */
export function layoutTreemap(items: ChartItem[], width = 100, height = 62): Placed[] {
  const sorted = items.filter((item) => item.value > 0).sort((a, b) => b.value - a.value);
  const total = sorted.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) return [];
  const scale = (width * height) / total;
  const areas = sorted.map((item) => item.value * scale);
  const placed: Placed[] = [];
  let x = 0;
  let y = 0;
  let w = width;
  let h = height;
  let index = 0;

  const worst = (row: number[], side: number) => {
    const sum = row.reduce((a, b) => a + b, 0);
    const max = Math.max(...row);
    const min = Math.min(...row);
    return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
  };

  while (index < sorted.length) {
    const side = Math.min(w, h);
    const row: number[] = [areas[index]];
    let end = index + 1;
    while (end < sorted.length && worst([...row, areas[end]], side) <= worst(row, side)) {
      row.push(areas[end]);
      end += 1;
    }
    const sum = row.reduce((a, b) => a + b, 0);
    const horizontal = w >= h; // la rangée longe le côté le plus court : colonne à gauche si le rectangle est large
    const thickness = sum / side;
    let offset = 0;
    row.forEach((area, i) => {
      const length = area / thickness;
      placed.push(horizontal
        ? { ...sorted[index + i], x, y: y + offset, w: thickness, h: length }
        : { ...sorted[index + i], x: x + offset, y, w: length, h: thickness });
      offset += length;
    });
    if (horizontal) { x += thickness; w -= thickness; } else { y += thickness; h -= thickness; }
    index = end;
  }
  return placed;
}

const GAP = 0.35;

/** Les tuiles gardent la place : le montant sans devise (la devise est dans le titre de la carte). */
function tileNumber(value: number): string {
  return Math.round(value).toLocaleString("fr-FR");
}

export function TreemapChart({ ariaLabel, format, items, onSelect, total }: { ariaLabel: string; format: (value: number) => string; items: ChartItem[]; onSelect?: (label: string) => void; total: number }) {
  const placed = layoutTreemap(items);
  if (placed.length === 0) return <p className="dash-chart-empty">Aucune valeur à représenter.</p>;
  return (
    <div aria-label={ariaLabel} className="dash-treemap" role="group">
      {placed.map((tile) => {
        const share = total > 0 ? (tile.value / total) * 100 : 0;
        const big = tile.w > 22 && tile.h > 20;
        const medium = tile.w > 12 && tile.h > 11;
        return (
          <button
            className={big ? "dash-tile dash-tile--big" : medium ? "dash-tile" : "dash-tile dash-tile--small"}
            key={tile.label}
            onClick={() => onSelect?.(tile.label)}
            style={{ background: tile.color, height: `calc(${(tile.h / 62) * 100}% - ${GAP * 2}%)`, left: `${tile.x}%`, top: `${(tile.y / 62) * 100}%`, width: `calc(${tile.w}% - ${GAP * 2}%)`, margin: `${GAP}%` }}
            title={`${tile.label} · ${format(tile.value)} · ${share.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`}
            type="button"
          >
            <span>{tile.label}</span>
            {medium && <strong>{tileNumber(tile.value)}</strong>}
            {big && <small>{share.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %</small>}
          </button>
        );
      })}
    </div>
  );
}

export function RankedBars({ format, items, total }: { format: (value: number) => string; items: ChartItem[]; total: number }) {
  const sorted = [...items].sort((a, b) => b.value - a.value);
  const max = sorted[0]?.value ?? 0;
  if (sorted.length === 0 || max <= 0) return <p className="dash-chart-empty">Aucune dépense ce mois-ci.</p>;
  return (
    <ul className="dash-bars" aria-label="Dépenses par catégorie, classées par montant">
      {sorted.map((item) => (
        <li key={item.label}>
          <span title={item.label}>{item.label}</span>
          <i aria-hidden="true"><b style={{ width: `${Math.max(2, (item.value / max) * 100)}%`, background: item.color }} /></i>
          <strong>{format(item.value)} · {total > 0 ? Math.round((item.value / total) * 100) : 0} %</strong>
        </li>
      ))}
    </ul>
  );
}

const MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

export function FlowHistoryChart({ format, history }: { format: (value: number) => string; history: { month: string; income: number; expenses: number }[] }) {
  const max = Math.max(1, ...history.flatMap((row) => [row.income, row.expenses]));
  const last = history.length - 1;
  return (
    <div className="dash-flow-chart">
      <div className="dash-flow-legend"><span><i className="dash-flow-key dash-flow-key--income" />Revenus</span><span><i className="dash-flow-key dash-flow-key--expense" />Dépenses</span></div>
      <div className="dash-flow-bars" role="img" aria-label={`Revenus et dépenses sur ${history.length} mois`}>
        {history.map((row, index) => {
          const net = row.income - row.expenses;
          return (
            <div className={index === last ? "dash-flow-month dash-flow-month--current" : "dash-flow-month"} key={row.month} title={`${row.month} · revenus ${format(row.income)} · dépenses ${format(row.expenses)}`}>
              <div className="dash-flow-pair">
                <i className="dash-flow-bar dash-flow-bar--income" style={{ height: `${(row.income / max) * 100}%` }} />
                <i className="dash-flow-bar dash-flow-bar--expense" style={{ height: `${(row.expenses / max) * 100}%` }} />
              </div>
              <small>{MONTHS[Number(row.month.slice(5, 7)) - 1]}</small>
              <b className={net >= 0 ? "bgt-good" : "bgt-bad"}>{net > 0 ? "+" : ""}{Math.round(net).toLocaleString("fr-FR")}</b>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AssetFamilyDrawer({ color, family, format, items, onClose, onOpenAssets, share, total }: { color?: string; family: string; format: (value: number) => string; items: { name: string; value: number }[]; onClose: () => void; onOpenAssets: () => void; share: number; total: number }) {
  return (
    <SideDrawer eyebrow="Patrimoine" onClose={onClose} title={`${family} · ${format(total)}`}
      footer={<><button className="settings-secondary" onClick={onClose} type="button">Fermer</button><button className="settings-primary" onClick={onOpenAssets} type="button">Ouvrir Patrimoine</button></>}>
      <p className="backup-lead"><span className="dash-swatch" style={{ background: color }} />{share.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % du total des actifs.</p>
      <table className="settings-table backup-table">
        <thead><tr><th>Élément</th><th>Valeur</th><th>Part</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.name}><td>{item.name}</td><td><strong>{format(item.value)}</strong></td><td>{total > 0 ? ((item.value / total) * 100).toLocaleString("fr-FR", { maximumFractionDigits: 1 }) : 0} %</td></tr>
          ))}
          {items.length === 0 && <tr><td colSpan={3}>Détail indisponible pour cette famille.</td></tr>}
        </tbody>
      </table>
    </SideDrawer>
  );
}
