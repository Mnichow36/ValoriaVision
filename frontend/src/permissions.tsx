import { createContext, useContext } from "react";
import type { ReactNode } from "react";

/** Droit d'écriture du profil connecté (faux pour un Lecteur). Le serveur reste le garde-fou. */
const CanWriteContext = createContext(true);

export const CanWriteProvider = CanWriteContext.Provider;

export function useCanWrite(): boolean {
  return useContext(CanWriteContext);
}

/** N'affiche son contenu que si le profil peut modifier les données. */
export function WriteOnly({ children }: { children: ReactNode }) {
  return useCanWrite() ? <>{children}</> : null;
}
