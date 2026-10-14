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
  onLock: () => void;
}

export function Sidebar({ active, onNavigate, onLock }: SidebarProps) {
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
        <span>Sans connexion bancaire permanente</span>
        <button aria-label="Verrouiller la session" onClick={onLock} title="Verrouiller la session" type="button">
          <svg aria-hidden="true" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24">
            <rect height="10" rx="2" width="14" x="5" y="10" />
            <path d="M8 10V7a4 4 0 0 1 8 0v3" />
          </svg>
        </button>
      </div>
    </aside>
  );
}

function MenuIcon({ id }: { id: NavigationId }) {
  const common = {
    "aria-hidden": true,
    className: "nav-item__icon",
    viewBox: "0 0 24 24",
  };

  switch (id) {
    case "dashboard":
      return <svg {...common} fill="currentColor"><rect height="5" rx="2" width="5" x="6" y="6" /><rect height="5" rx="2" width="5" x="14" y="6" /><rect height="5" rx="2" width="5" x="6" y="14" /><rect height="5" rx="2" width="5" x="14" y="14" /></svg>;
    case "accounts":
      return <svg {...common} fill="currentColor"><path d="m4 10 8-6 8 6H4Z" /><path d="M5 19h14v2H5z" /><path d="M7 10h2v8H7zm4 0h2v8h-2zm4 0h2v8h-2z" /></svg>;
    case "transactions":
      return <svg {...common} fill="currentColor"><path d="M5 7h11V3l5 5-5 5V9H5V7Zm14 8H8v-4l-5 5 5 5v-4h11v-2Z" /></svg>;
    case "forecast":
      return <svg {...common} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.4"><path d="M5 5v14h15" /><path d="m7 16 4-4 3 2 5-7" /><circle cx="19" cy="7" fill="currentColor" r="2" stroke="none" /></svg>;
    case "budgets":
      return <svg {...common}><circle cx="12" cy="12" fill="none" r="7" stroke="currentColor" strokeWidth="2.2" /><path d="M12 5a7 7 0 0 1 7 7h-7V5Z" fill="currentColor" /><path d="m12 12-4 6" fill="none" stroke="currentColor" strokeWidth="2" /></svg>;
    case "assets":
      return <svg {...common} fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="1.8"><path d="M12 3 21 12 12 21 3 12Z" /><path d="M7.5 12h9M12 7.5v9" strokeWidth="2" /></svg>;
    case "reconciliation":
      return <svg {...common} fill="none" stroke="currentColor" strokeWidth="2.4"><circle cx="9" cy="10" r="4" /><circle cx="15" cy="14" r="4" /><path d="M11.5 12h1" /></svg>;
    case "settings":
      return <svg {...common} fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.7"><circle cx="12" cy="12" r="3.2" /><path d="M12 3v5M12 16v5M3 12h5M16 12h5M5.6 5.6l3.5 3.5M14.9 14.9l3.5 3.5M18.4 5.6l-3.5 3.5M9.1 14.9l-3.5 3.5" /></svg>;
  }
}
