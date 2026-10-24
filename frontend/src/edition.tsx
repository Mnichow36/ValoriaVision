import { createContext, useContext } from "react";

import type { EditionInfo } from "./api/contracts";

export type PremiumFeature = "accounts" | "multi_currency" | "profiles" | "scenario_builder";

interface EditionContextValue {
  edition: EditionInfo | null;
  /** Ouvre le volet « Fonction Premium » pour la fonction demandée. */
  openPremium: (feature: PremiumFeature) => void;
}

const EditionContext = createContext<EditionContextValue>({ edition: null, openPremium: () => undefined });

export const EditionProvider = EditionContext.Provider;

/** Édition du profil connecté. Sans information (démarrage), rien n'est bloqué : le serveur décide. */
export function useEdition(): EditionContextValue {
  return useContext(EditionContext);
}
