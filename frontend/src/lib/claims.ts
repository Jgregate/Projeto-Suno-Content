import type { ClaimVerdict } from "@/api/types";

export const SENTENCE_RE = /[^.!?…]+(?:[.!?…]+(?=\s|$)|$)/g;
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\p{L}\p{N}%,]+/gu, " ").trim();
const words = (s: string) => new Set(norm(s).split(" ").filter((w) => w.length > 3));

/** Afirmação do checker que corresponde à frase (igualdade, inclusão ou ≥ 60% das palavras). */
export function matchClaim(sentence: string, claims: ClaimVerdict[]): ClaimVerdict | undefined {
  const ns = norm(sentence);
  if (ns.length < 12) return undefined;
  return claims.find((c) => {
    const nc = norm(c.claim);
    if (!nc) return false;
    if (ns.includes(nc) || nc.includes(ns)) return true;
    const a = words(sentence);
    const b = words(c.claim);
    const inter = [...a].filter((w) => b.has(w)).length;
    return b.size > 0 && inter / Math.min(a.size, b.size) >= 0.6;
  });
}

