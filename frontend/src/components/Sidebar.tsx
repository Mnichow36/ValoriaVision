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

const glyphs: Record<(typeof entries)[number][0], string> = {
  dashboard: "▦",
  accounts: "▤",
  transactions: "⇄",
  forecast: "⌁",
  budgets: "◫",
  assets: "◇",
  reconciliation: "⇆",
  settings: "⚙",
};

export function Sidebar() {
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
        {entries.map(([id, label], index) => (
          <button
            className={`nav-item ${index === 0 ? "nav-item--active" : ""}`}
            disabled={index !== 0}
            key={id}
            title={index === 0 ? label : `${label} — prochain incrément`}
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
