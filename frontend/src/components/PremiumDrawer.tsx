import { SideDrawer } from "./SideDrawer";
import type { EditionInfo } from "../api/contracts";
import type { PremiumFeature } from "../edition";

interface PremiumText {
  title: string;
  lead: string;
  points: string[];
}

function textFor(feature: PremiumFeature, edition: EditionInfo | null): PremiumText {
  const limit = edition?.accountLimit ?? 3;
  switch (feature) {
    case "accounts":
      return {
        title: "Nouveau compte",
        lead: `L’édition Standard comprend ${limit} comptes actifs. Vous en avez ${edition?.activeAccounts ?? limit} : la création ou la réactivation d’un compte supplémentaire est réservée à l’édition Premium.`,
        points: [
          "Vos comptes restent consultables et utilisables, rien n’est supprimé.",
          "Vous pouvez archiver un compte pour libérer une place.",
          "Premium supprime cette limite.",
        ],
      };
    case "multi_currency":
      return {
        title: "Multi-devises",
        lead: "L’édition Standard gère les comptes en euros. Les comptes dans une autre devise sont réservés à l’édition Premium.",
        points: ["Vos comptes en euros ne changent pas.", "Premium ouvre les devises USD, GBP et CHF."],
      };
    case "profiles":
      return {
        title: "Profils et accès",
        lead: "L’édition Standard comprend un seul profil actif. Les profils supplémentaires et leurs accès sont réservés à l’édition Premium.",
        points: [
          "Les profils existants sont conservés avec leurs données, verrouillés par un cadenas.",
          "Mot de passe, code PIN et protection des données restent disponibles pour tous.",
        ],
      };
    default:
      return {
        title: "Scénarios personnalisés",
        lead: "Créez et comparez vos propres scénarios : réglez vos hypothèses puis comparez plusieurs avenirs côte à côte avant de décider.",
        points: [
          "Les scénarios standard (Réaliste, Prudent, Optimiste) restent disponibles sur la courbe de prévision.",
          "Premium débloque la création, la modification et la duplication de scénarios.",
        ],
      };
  }
}

/** Volet latéral commun à toutes les fonctions réservées à Premium. */
export function PremiumDrawer({ feature, edition, onClose, onDiscover }: { feature: PremiumFeature; edition: EditionInfo | null; onClose: () => void; onDiscover: () => void }) {
  const text = textFor(feature, edition);
  return (
    <SideDrawer
      eyebrow="Fonction Premium"
      footer={<>
        <button className="secondary-button" onClick={onClose} type="button">Fermer</button>
        <button className="primary-button" onClick={onDiscover} type="button">Découvrir Premium</button>
      </>}
      onClose={onClose}
      title={text.title}
    >
      <div className="premium-lock" aria-hidden="true">
        <svg fill="none" height="26" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width="26"><rect height="9" rx="2" width="14" x="5" y="11" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
      </div>
      <p className="premium-lead">{text.lead}</p>
      <ul className="premium-points">{text.points.map((point) => <li key={point}>{point}</li>)}</ul>
    </SideDrawer>
  );
}

export function PadlockIcon({ size = 14 }: { size?: number }) {
  return (
    <svg aria-hidden="true" fill="none" height={size} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" viewBox="0 0 24 24" width={size}><rect height="9" rx="2" width="14" x="5" y="11" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
  );
}
