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
            <span className="nav-item__icon-box"><MenuIcon id={id} /></span>
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

function MenuIcon({ id }: { id: NavigationId }) {
  const common = {
    "aria-hidden": true,
    className: "nav-item__icon",
    fill: "none",
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 2,
    viewBox: "0 0 24 24",
  };

  switch (id) {
    case "dashboard":
      return <svg {...common}><rect x="4" y="4" width="6" height="6" rx="1.5" /><rect x="14" y="4" width="6" height="6" rx="1.5" /><rect x="4" y="14" width="6" height="6" rx="1.5" /><rect x="14" y="14" width="6" height="6" rx="1.5" /></svg>;
    case "accounts":
      return <svg {...common}><path d="M4 10 12 5l8 5" /><path d="M6 10v8" /><path d="M10 10v8" /><path d="M14 10v8" /><path d="M18 10v8" /><path d="M4 18h16" /></svg>;
    case "transactions":
      return <svg {...common}><path d="M5 8h13" /><path d="m15 5 3 3-3 3" /><path d="M19 16H6" /><path d="m9 13-3 3 3 3" /></svg>;
    case "forecast":
      return <svg {...common}><path d="M4 19V5" /><path d="M4 19h16" /><path d="m6 15 4-4 4 2 5-7" /><circle cx="19" cy="6" r="1.5" /></svg>;
    case "budgets":
      return <svg {...common}><circle cx="12" cy="12" r="7" /><path d="M12 5v7h7" /><path d="M12 12 8 18" /></svg>;
    case "assets":
      return <svg {...common}><path d="M12 4 20 12 12 20 4 12Z" /><path d="M8 12h8" /><path d="M12 8v8" /></svg>;
    case "reconciliation":
      return <svg {...common}><circle cx="9" cy="10" r="4" /><circle cx="15" cy="14" r="4" /><path d="M12 12h1" /></svg>;
    case "settings":
      return <svg {...common}><circle cx="12" cy="12" r="3.2" /><path d="M12 3v3" /><path d="M12 18v3" /><path d="M3 12h3" /><path d="M18 12h3" /><path d="m5.6 5.6 2.1 2.1" /><path d="m16.3 16.3 2.1 2.1" /><path d="m18.4 5.6-2.1 2.1" /><path d="m7.7 16.3-2.1 2.1" /></svg>;
  }
}
