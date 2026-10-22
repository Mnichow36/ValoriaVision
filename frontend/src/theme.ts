// Gestion du thème : « light », « dark » ou « auto » (suit le système).
// Le choix est mémorisé localement ; l'attribut data-theme est posé sur <html>.
export type ThemePreference = "light" | "dark" | "auto";

const STORAGE_KEY = "valoria.theme";
const listeners = new Set<(preference: ThemePreference) => void>();

export function getThemePreference(): ThemePreference {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "auto") return value;
  } catch {
    // stockage indisponible : thème automatique
  }
  return "auto";
}

function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(preference: ThemePreference = getThemePreference()): void {
  const dark = preference === "dark" || (preference === "auto" && systemPrefersDark());
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function setThemePreference(preference: ThemePreference): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // le choix reste valable pour la session
  }
  applyTheme(preference);
  listeners.forEach((listener) => listener(preference));
}

export function subscribeTheme(listener: (preference: ThemePreference) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function initTheme(): void {
  applyTheme();
  if (typeof window.matchMedia === "function") {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (getThemePreference() === "auto") applyTheme("auto");
    });
  }
}
