export const MIN_PASSWORD_LENGTH = 10;

export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  /** Message d'aide tant que le mot de passe n'est pas accepté, sinon chaîne vide. */
  hint: string;
  acceptable: boolean;
}

/** Reflet côté interface de la politique du moteur (app/security/auth_service.py). */
export function evaluatePassword(password: string): PasswordStrength {
  const classes = [/[a-zà-öø-ÿ]/, /[A-ZÀ-ÖØ-Þ]/, /\d/, /[^\w\s]|_/].filter((re) => re.test(password)).length;
  if (!password) return { score: 0, label: "", hint: "", acceptable: false };
  if (password.length < MIN_PASSWORD_LENGTH) {
    return { score: 1, label: "Trop court", hint: `Au moins ${MIN_PASSWORD_LENGTH} caractères (${password.length}/${MIN_PASSWORD_LENGTH}).`, acceptable: false };
  }
  if (classes < 3) {
    return { score: 1, label: "Faible", hint: "Mélangez au moins trois types : minuscules, majuscules, chiffres, symboles.", acceptable: false };
  }
  if (password.length >= 16 && classes === 4) return { score: 4, label: "Très solide", hint: "", acceptable: true };
  if (password.length >= 14) return { score: 3, label: "Solide", hint: "", acceptable: true };
  return { score: 2, label: "Correct", hint: "", acceptable: true };
}
