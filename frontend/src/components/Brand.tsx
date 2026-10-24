export const BRAND_SLOGAN = "Voir venir. Décider juste.";
export const STUDIO_NAME = "DeltaOne Studio";

/** Logo Valoria Vision : un cadran de cockpit, un V comme aiguille, un point ambre pour ce qui arrive. */
export function BrandMark({ size = 40, variant = "navy" }: { size?: number; variant?: "navy" | "blue" }) {
  const tile = variant === "blue" ? "#2563eb" : "#0b1b3a";
  return (
    <svg aria-hidden="true" className="brand-logo" height={size} viewBox="0 0 64 64" width={size}>
      <rect fill={tile} height="64" rx="16" width="64" />
      {variant === "navy" && <rect fill="none" height="61" rx="14.5" stroke="#7fa8ff" strokeOpacity="0.3" strokeWidth="1.5" width="61" x="1.5" y="1.5" />}
      <path d="M32 10 A22 22 0 1 0 54 32" fill="none" stroke="#ffffff" strokeLinecap="round" strokeOpacity="0.6" strokeWidth="4.5" />
      <path d="M22 25 L32 41 L42 25" fill="none" stroke="#ffffff" strokeLinecap="round" strokeLinejoin="round" strokeWidth="5.5" />
      <circle cx="50.5" cy="17" fill="#f5a524" r="4.5" />
    </svg>
  );
}

/** Signe du studio : un delta, avec un petit delta ambre à l'intérieur. */
export function DeltaGlyph({ size = 16, filled = false }: { size?: number; filled?: boolean }) {
  return (
    <svg aria-hidden="true" height={size} viewBox="0 0 24 24" width={size}>
      <path d="M12 3 L22 21 H2 Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth="2.6" />
      {filled && <path d="M12 11 L16 18 H8 Z" fill="#f5a524" />}
    </svg>
  );
}

export function StudioSignature() {
  return (
    <div aria-label={`Un produit ${STUDIO_NAME}`} className="studio-signature">
      <span>UN PRODUIT</span>
      <DeltaGlyph size={14} />
      <strong>DELTAONE STUDIO</strong>
    </div>
  );
}
