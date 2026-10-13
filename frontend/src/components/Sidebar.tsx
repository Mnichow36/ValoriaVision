import accountsIcon from "../assets/icons/accounts.svg";
import assetsIcon from "../assets/icons/assets.svg";
import budgetsIcon from "../assets/icons/budgets.svg";
import dashboardIcon from "../assets/icons/dashboard.svg";
import forecastIcon from "../assets/icons/forecast.svg";
import reconciliationIcon from "../assets/icons/reconciliation.svg";
import settingsIcon from "../assets/icons/settings.svg";
import transactionsIcon from "../assets/icons/transactions.svg";

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

const icons: Record<NavigationId, string> = {
  dashboard: dashboardIcon,
  accounts: accountsIcon,
  transactions: transactionsIcon,
  forecast: forecastIcon,
  budgets: budgetsIcon,
  assets: assetsIcon,
  reconciliation: reconciliationIcon,
  settings: settingsIcon,
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
            <span
              aria-hidden="true"
              className="nav-item__icon"
              style={{
                maskImage: `url(${icons[id]})`,
                WebkitMaskImage: `url(${icons[id]})`,
              }}
            />
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
