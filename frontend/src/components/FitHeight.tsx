import type { ReactNode } from "react";

import { useFitHeight } from "../useFitHeight";

/** Bloc qui se cale sur la hauteur restante de la fenêtre (voir useFitHeight). */
export function FitHeight({ as = "div", children, className, minHeight, mode = "max" }: { as?: "div" | "section"; children: ReactNode; className?: string; minHeight?: number; mode?: "max" | "box" }) {
  const ref = useFitHeight<HTMLDivElement>(mode, minHeight);
  const Tag = as as "div";
  return <Tag className={className} ref={ref}>{children}</Tag>;
}
