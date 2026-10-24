import { useCallback, useEffect, useRef, useState } from "react";

export const PIN_LENGTH = 6;

interface PinPadProps {
  busy: boolean;
  /** Message d'erreur affiché sous les points ; un nouveau message efface la saisie. */
  error?: string;
  onComplete: (pin: string) => void;
}

const KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9"];

/** Pavé numérique à 6 points : se valide tout seul au sixième chiffre ; le clavier du PC fonctionne aussi. */
export function PinPad({ busy, error, onComplete }: PinPadProps) {
  const [digits, setDigitsState] = useState("");
  // Les chiffres vivent aussi dans une référence : l'envoi ne doit jamais se faire dans un
  // updater React (rejoué en mode strict, il enverrait le PIN deux fois et doublerait les erreurs).
  const digitsRef = useRef("");
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const completeRef = useRef(onComplete);
  completeRef.current = onComplete;

  const setDigits = useCallback((value: string) => {
    digitsRef.current = value;
    setDigitsState(value);
  }, []);

  useEffect(() => { setDigits(""); }, [error, setDigits]);

  const press = useCallback((digit: string) => {
    if (busyRef.current || digitsRef.current.length >= PIN_LENGTH) return;
    const next = digitsRef.current + digit;
    setDigits(next);
    if (next.length === PIN_LENGTH) {
      window.setTimeout(() => {
        if (digitsRef.current !== next) return;
        setDigits("");
        completeRef.current(next);
      }, 120);
    }
  }, [setDigits]);

  const erase = useCallback(() => {
    if (!busyRef.current) setDigits(digitsRef.current.slice(0, -1));
  }, [setDigits]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (/^[0-9]$/.test(event.key)) { event.preventDefault(); press(event.key); }
      else if (event.key === "Backspace") { event.preventDefault(); erase(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [press, erase]);

  return (
    <div className="pin-pad">
      <div aria-label={`${digits.length} chiffre${digits.length > 1 ? "s" : ""} saisi${digits.length > 1 ? "s" : ""} sur ${PIN_LENGTH}`} className={`pin-dots${error ? " is-error" : ""}`} role="img">
        {Array.from({ length: PIN_LENGTH }, (_, index) => <span className={index < digits.length ? "is-filled" : ""} key={index} />)}
      </div>
      {error ? <p className="pin-error" role="alert">{error}</p> : <p className="pin-hint" role="status">{busy ? "Vérification…" : "Saisissez votre code PIN"}</p>}
      <div className="pin-keys">
        {KEYS.map((key) => <button className="pin-key" disabled={busy} key={key} onClick={() => press(key)} type="button">{key}</button>)}
        <span />
        <button className="pin-key" disabled={busy} onClick={() => press("0")} type="button">0</button>
        <button aria-label="Effacer le dernier chiffre" className="pin-key pin-key--erase" disabled={busy} onClick={erase} type="button">
          <svg aria-hidden="true" fill="none" height="22" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="22"><path d="M21 5H9l-6 7 6 7h12z" /><path d="M13 9l4 6M17 9l-4 6" /></svg>
        </button>
      </div>
    </div>
  );
}
