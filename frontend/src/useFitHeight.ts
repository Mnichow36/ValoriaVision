import { useLayoutEffect, useRef } from "react";

const BOTTOM_MARGIN = 24;

/**
 * Règle UX « jamais de défilement de page » : cale l'élément sur la hauteur encore
 * disponible dans la fenêtre, quel que soit ce qui le précède (bandeaux, filtres, onglets).
 * - "max" : plafonne la hauteur d'une liste (le tableau défile dans son cadre) ;
 * - "box" : fixe la hauteur d'un bloc entier (poste de travail à colonnes).
 * Le calcul est refait à chaque affichage et au redimensionnement de la fenêtre.
 */
export function useFitHeight<T extends HTMLElement>(mode: "max" | "box" = "max", minHeight = 140) {
  const ref = useRef<T>(null);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;

    function apply() {
      if (!element) return;
      element.style.maxHeight = "none";
      if (mode === "box") element.style.height = "auto";
      const top = element.getBoundingClientRect().top + window.scrollY;
      const card = element.closest(".card");
      const below = card && card !== element ? Math.max(0, card.getBoundingClientRect().bottom - element.getBoundingClientRect().bottom) : 0;
      const available = Math.max(minHeight, Math.floor(window.innerHeight - top - below - BOTTOM_MARGIN));
      const set = (value: number) => {
        if (mode === "box") element.style.height = `${value}px`;
        else element.style.maxHeight = `${value}px`;
      };
      set(available);
      // Correction : ce qui reste sous la carte (pied, bandeau…) peut encore faire dépasser la page.
      const overflow = document.documentElement.scrollHeight - window.innerHeight;
      if (overflow > 0) set(Math.max(minHeight, available - overflow));
    }

    apply();
    window.addEventListener("resize", apply);
    return () => window.removeEventListener("resize", apply);
  });

  return ref;
}
