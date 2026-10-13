const entries = [
  ["dashboard", "Tableau de bord"],
  ["accounts", "Comptes"],
  ["transactions", "Transactions"],
  ["forecast", "Prévisionnel"],
  ["budgets", "Budgets"],
  ["assets", "Patrimoine"],
  ["reconciliation", "Rapprochements"],
  ["settings", "Paramètres"],
] as const;

export type NavigationId = (typeof entries)[number][0];

const glyphs: Record<NavigationId, string> = {
  dashboard: "▦",
  accounts: "▤",
  transactions: "⇄",
  forecast: "⌁",
  budgets: "◫",
  assets: "◇",
  reconciliation: "⇆",
  settings: "⚙",
};

interface SidebarProps {
  active: NavigationId;
  onNavigate: (destination: NavigationId) => void;
}

export function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="sidebar" aria-label="Navigation principale">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">V</span>
        <span>
          <strong>Valoria Vision</strong>
          <small>Finance locale</small>
        </span>
      </div>

      <nav>
        {entries.map(([id, label]) => (
          <button
            aria-current={active === id ? "page" : undefined}
            className={`nav-item ${active === id ? "nav-item--active" : ""}`}
            key={id}
            onClick={() => onNavigate(id)}
            title={label}
            type="button"
          >
            <span aria-hidden="true">{glyphs[id]}</span>
            {label}
          </button>
        ))}
      </nav>

      <div className="local-card">
        <strong>Données locales</strong>
        <span>Sans connexion bancaire imposée</span>
      </div>
    </aside>
  );
}
