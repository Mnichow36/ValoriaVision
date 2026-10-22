import { useEffect } from "react";
import type { ReactNode } from "react";

interface SideDrawerProps {
  children: ReactNode;
  eyebrow: string;
  footer?: ReactNode;
  onClose: () => void;
  title: string;
}

/** Volet latéral : toute modification ou information détaillée s'affiche ici (règle UX). */
export function SideDrawer({ children, eyebrow, footer, onClose, title }: SideDrawerProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="account-editor-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <aside aria-label={title} aria-modal="true" className="account-editor side-drawer" role="dialog">
        <header>
          <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2></div>
          <button aria-label="Fermer" onClick={onClose} type="button">×</button>
        </header>
        <div className="side-drawer__body">{children}</div>
        {footer && <footer className="side-drawer__footer">{footer}</footer>}
      </aside>
    </div>
  );
}
