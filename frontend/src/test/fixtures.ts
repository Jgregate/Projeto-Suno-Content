import type { CellResult, MetricResult, RunResults, TermOccurrence } from "@/api/types";
import { FORMATS, LEVELS } from "@/lib/levels";

export const metric = (name: string, score: number, threshold: number, direction: MetricResult["direction"] = "min", threshold_max: number | null = null): MetricResult => ({
  name, score, threshold, threshold_max, direction, details: "",
  passed: direction === "min" ? score >= threshold : direction === "max" ? score <= threshold : direction === "range" ? score >= threshold && score <= (threshold_max ?? Infinity) : true,
});

const cell = (audience: CellResult["audience"], format: CellResult["format"], passed: boolean): CellResult => ({
  audience,
  format,
  status: { status: passed ? "aprovado" : "reprovado_final", attempts: passed ? 1 : 3, delivered_attempt: 1, best_score: passed ? 1 : 0.5, stop_reason: passed ? "aprovado" : "max_tentativas", regressions: [] },
  content: {
    audience, format, attempt: 1, anchor_ids: ["A01"], warnings: [],
    content:
      format === "texto"
        ? { kind: "texto", title: `Título ${audience}`, subtitle: "Linha fina", sections: [{ heading: "Seção", body: "Texto.", anchor_ids: ["A01"] }] }
        : format === "carrossel"
          ? { kind: "carrossel", slides: [{ role: "gancho", title: `Gancho ${audience}`, text: "t", anchor_ids: [] }] }
          : { kind: "roteiro", blocks: [{ start_s: 0, end_s: 3, visual_hook: "v", speech: `Fala ${audience}`, anchor_ids: [] }] },
  } as CellResult["content"],
  report: {
    audience, format, attempt: 1, passed, flags: [], feedback: "", claims: [], judge: [],
    metrics: [metric("flesch_pt", passed ? 70 : 30, 60), metric("term_density", 1, 2, "max"), metric("numeric_grounding", 0, 0, "max")],
  },
  history: [],
});

export const results: RunResults = {
  run_id: "doc__1", doc_id: "doc", created_at: "2026-10-09T12:00:00", prompts_hash: "abc", models: {}, force_drift: null,
  cells: LEVELS.flatMap((l, i) => FORMATS.map((f, j) => cell(l, f, (i + j) % 2 === 0))),
  adapted: {}, generation: null, evaluation: null, warnings: [], node_costs: [],
};

export const occurrence = (termo: string, surface: string, sentence: string, contextualized: boolean, needs = true): TermOccurrence => ({
  termo, surface, sentence, sentence_index: 0, needs_context: needs, marker: contextualized && needs ? "ou seja" : null, contextualized,
});
