import { useEffect, useRef } from "react";

import { useCanWrite } from "../permissions";

export interface ContextMenuItem {
  label: string;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
  hint?: string;
  /** Action sans écriture, proposée aussi aux profils en consultation. Par défaut, une action est une écriture. */
  readOnly?: boolean;
}

export interface ContextMenuState {
  x: number;
  y: number;
  items: ContextMenuItem[];
  /** Explication affichée sous les actions (ex. pourquoi une action est grisée). */
  note?: string;
}

/** Menu contextuel (clic droit) — CDC P4 : pas de bouton d'action permanent dans les listes. */
export function ContextMenu({ menu, onClose }: { menu: ContextMenuState; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const canWrite = useCanWrite();
  const items = canWrite ? menu.items : menu.items.filter((item) => item.readOnly);

  useEffect(() => {
    const close = () => onClose();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  // Garde le menu dans la fenêtre.
  const width = 240;
  const height = items.length * 38 + 12 + (menu.note ? 64 : 0);
  const left = Math.max(8, Math.min(menu.x, window.innerWidth - width - 8));
  const top = Math.max(8, Math.min(menu.y, window.innerHeight - height - 8));

  if (items.length === 0) return null;

  return (
    <div className="context-menu" ref={ref} role="menu" style={{ left, top, width }} onContextMenu={(event) => event.preventDefault()}>
      {items.map((item) => (
        <button
          className={item.danger ? "context-menu__item context-menu__item--danger" : "context-menu__item"}
          disabled={item.disabled}
          key={item.label}
          onClick={(event) => {
            event.stopPropagation();
            onClose();
            item.onSelect();
          }}
          role="menuitem"
          title={item.hint}
          type="button"
        >
          {item.label}
        </button>
      ))}
      {menu.note && <p className="context-menu__note">{menu.note}</p>}
    </div>
  );
}
