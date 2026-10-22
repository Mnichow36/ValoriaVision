import { useEffect, useState } from "react";

import { getThemePreference, setThemePreference, subscribeTheme, type ThemePreference } from "../theme";

const OPTIONS: { value: ThemePreference; label: string }[] = [
  { value: "light", label: "Clair" },
  { value: "dark", label: "Sombre" },
  { value: "auto", label: "Auto" },
];

export function useThemePreference(): ThemePreference {
  const [preference, setPreference] = useState<ThemePreference>(getThemePreference);
  useEffect(() => subscribeTheme(setPreference), []);
  return preference;
}

export function ThemeSwitch({ variant = "sidebar" }: { variant?: "sidebar" | "settings" }) {
  const preference = useThemePreference();
  return (
    <div aria-label="Apparence" className={`theme-switch theme-switch--${variant}`} role="radiogroup">
      {OPTIONS.map((option) => (
        <button
          aria-checked={preference === option.value}
          className={preference === option.value ? "theme-switch__item theme-switch__item--active" : "theme-switch__item"}
          key={option.value}
          onClick={() => setThemePreference(option.value)}
          role="radio"
          title={option.value === "auto" ? "Suivre le réglage du système" : `Thème ${option.label.toLowerCase()}`}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
