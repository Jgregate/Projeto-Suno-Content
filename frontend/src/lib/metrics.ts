import type { Bound, MetricResult } from "@/api/types";

export type MetricKind = "readability" | "terms" | "fidelity" | "judge";

export interface MetricInfo {
  label: string;
  short: string;
  kind: MetricKind;
  /** domínio da barra */
  domain: [number, number];
  unit?: string;
  help: string;
}

export const METRICS: Record<string, MetricInfo> = {
  flesch_pt: { label: "Legibilidade (Flesch PT)", short: "Legibilidade", kind: "readability", domain: [0, 100], help: "Quanto maior, mais fácil de ler. Fórmula de Martins et al. para o português." },
  term_density: { label: "Densidade de termos técnicos", short: "Densidade", kind: "terms", domain: [0, 12], unit: "/100 palavras", help: "Termos do glossário a cada 100 palavras." },
  term_context_pct: { label: "Termos contextualizados", short: "Contexto", kind: "terms", domain: [0, 100], unit: "%", help: "Termos acima do nível que vieram com explicação na mesma frase, na anterior ou na seguinte (\"Esse lucro...\")." },
  numeric_grounding: { label: "Números sem fonte", short: "Números", kind: "fidelity", domain: [0, 3], help: "Números do texto que não aparecem no documento nem nas âncoras." },
  claim_support: { label: "Afirmações sustentadas", short: "Fidelidade", kind: "fidelity", domain: [0, 1], help: "Fração das afirmações confirmadas por uma âncora." },
  claim_contradictions: { label: "Afirmações contraditas", short: "Contradições", kind: "fidelity", domain: [0, 3], help: "Qualquer contradição reprova." },
  judge_adequacao_publico: { label: "Judge · adequação ao público", short: "Público", kind: "judge", domain: [1, 5], help: "Nota de 1 a 5 do LLM Judge." },
  judge_tom: { label: "Judge · tom", short: "Tom", kind: "judge", domain: [1, 5], help: "Nota de 1 a 5 do LLM Judge." },
  judge_nuances: { label: "Judge · nuances", short: "Nuances", kind: "judge", domain: [1, 5], help: "Penaliza trivialização e perda de condicionantes." },
  judge_formato: { label: "Judge · formato", short: "Formato", kind: "judge", domain: [1, 5], help: "Aderência à estrutura do formato." },
};

export const metricInfo = (name: string): MetricInfo =>
  METRICS[name] ?? { label: name, short: name, kind: "fidelity", domain: [0, 1], help: "" };

/** Bound (min/max) a partir de um MetricResult. */
export function boundOf(m: MetricResult): Bound {
  if (m.direction === "min") return { min: m.threshold, max: null };
  if (m.direction === "max") return { min: null, max: m.threshold };
  if (m.direction === "range") return { min: m.threshold, max: m.threshold_max ?? null };
  return { min: null, max: null };
}

export function passes(value: number, bound: Bound): boolean {
  if (bound.min != null && value < bound.min) return false;
  if (bound.max != null && value > bound.max) return false;
  return true;
}

export function boundText(bound: Bound, unit = ""): string {
  const u = unit === "%" ? "%" : "";
  if (bound.min != null && bound.max != null) return `entre ${fmt(bound.min)}${u} e ${fmt(bound.max)}${u}`;
  if (bound.min != null) return `≥ ${fmt(bound.min)}${u}`;
  if (bound.max != null) return `≤ ${fmt(bound.max)}${u}`;
  return "sem limiar";
}

export function fmtMetric(name: string, value: number): string {
  if (name === "claim_support") return `${fmt(value * 100)}%`;
  if (name === "term_context_pct") return `${fmt(value)}%`;
  return fmt(value);
}

export function fmt(n: number): string {
  if (Math.abs(n) <= 1 && !Number.isInteger(n)) return n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  return n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

/** As 4 métricas do card da matriz: uma por família. */
export function headlineMetrics(metrics: MetricResult[]): { key: MetricKind; label: string; metric?: MetricResult; passed: boolean | null }[] {
  const pick = (names: string[]) => metrics.filter((m) => names.includes(m.name));
  const groups: [MetricKind, string, string[]][] = [
    ["readability", "Legibilidade", ["flesch_pt"]],
    ["terms", "Densidade", ["term_density", "term_context_pct"]],
    ["fidelity", "Fidelidade", ["numeric_grounding", "claim_support", "claim_contradictions"]],
    ["judge", "Judge", ["judge_adequacao_publico", "judge_tom", "judge_nuances", "judge_formato"]],
  ];
  return groups.map(([key, label, names]) => {
    const ms = pick(names);
    return { key, label, metric: ms[0], passed: ms.length ? ms.every((m) => m.passed) : null };
  });
}
