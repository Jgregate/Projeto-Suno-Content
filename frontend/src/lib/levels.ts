import type { Audience, Format } from "@/api/types";

export const LEVELS: Audience[] = ["iniciante", "intermediario", "avancado"];
export const FORMATS: Format[] = ["texto", "carrossel", "roteiro"];

export const LEVEL_LABEL: Record<Audience, string> = {
  iniciante: "Iniciante",
  intermediario: "Intermediário",
  avancado: "Avançado",
};

export const LEVEL_HINT: Record<Audience, string> = {
  iniciante: "Zero jargão sem analogia; impacto no bolso",
  intermediario: "Vocabulário de mercado; alocação e tendências",
  avancado: "Jargão pleno; foco analítico",
};

/** Classes Tailwind por nível: texto, fundo suave, borda e cor sólida (para gráficos via CSS var). */
export const LEVEL_STYLE: Record<Audience, { text: string; soft: string; border: string; borderTop: string; bg: string; cssVar: string }> = {
  iniciante: { text: "text-lvl-ini", soft: "bg-lvl-ini-soft", border: "border-lvl-ini", borderTop: "border-t-lvl-ini", bg: "bg-lvl-ini", cssVar: "var(--lvl-ini)" },
  intermediario: { text: "text-lvl-int", soft: "bg-lvl-int-soft", border: "border-lvl-int", borderTop: "border-t-lvl-int", bg: "bg-lvl-int", cssVar: "var(--lvl-int)" },
  avancado: { text: "text-lvl-adv", soft: "bg-lvl-adv-soft", border: "border-lvl-adv", borderTop: "border-t-lvl-adv", bg: "bg-lvl-adv", cssVar: "var(--lvl-adv)" },
};

export const FORMAT_LABEL: Record<Format, string> = {
  texto: "Texto analítico",
  carrossel: "Carrossel",
  roteiro: "Roteiro de vídeo",
};

export const cellPath = (docId: string, audience: Audience, format: Format, runId?: string | null) =>
  `/docs/${encodeURIComponent(docId)}/${audience}/${format}${runId ? `?run=${encodeURIComponent(runId)}` : ""}`;
