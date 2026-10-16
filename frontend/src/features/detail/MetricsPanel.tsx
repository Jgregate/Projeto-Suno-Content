import { AlertTriangle, Gavel, MessageSquareWarning } from "lucide-react";
import type { EvaluationReport, JudgeScore } from "@/api/types";
import { MetricBar } from "@/components/MetricBar";
import { boundOf, metricInfo } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const CRITERION: Record<JudgeScore["criterion"], string> = {
  adequacao_publico: "Adequação ao público",
  tom: "Tom",
  nuances: "Nuances",
  formato: "Formato",
};

const GROUPS: [string, string[]][] = [
  ["Legibilidade", ["flesch_pt"]],
  ["Termos técnicos", ["term_density", "term_context_pct"]],
  ["Fidelidade", ["numeric_grounding", "claim_support", "claim_contradictions"]],
];

export function FeedbackBox({ feedback, title = "Feedback do avaliador" }: { feedback: string; title?: string }) {
  const lines = feedback.split("\n").map((l) => l.replace(/^- /, "")).filter(Boolean);
  if (!lines.length) return null;
  return (
    <div className="rounded-lg border border-warn/30 bg-warn-soft p-4">
      <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-warn">
        <MessageSquareWarning aria-hidden className="size-4" /> {title}
      </p>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-relaxed text-ink">
        {lines.map((l, i) => <li key={i}>{l}</li>)}
      </ul>
    </div>
  );
}

export function MetricsPanel({ report }: { report: EvaluationReport }) {
  return (
    <aside aria-label="Métricas do avaliador" className="flex flex-col gap-6">
      {(report.flags ?? []).filter((f) => f === "baixa_confiabilidade").length > 0 && (
        <p className="flex items-start gap-2 rounded-lg bg-surface-2 p-3 text-xs text-ink-2">
          <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" />
          Texto com menos de 100 palavras: legibilidade e densidade têm baixa confiabilidade.
        </p>
      )}
      {GROUPS.map(([title, names]) => {
        const ms = report.metrics.filter((m) => names.includes(m.name));
        if (!ms.length) return null;
        return (
          <section key={title} className="flex flex-col gap-4">
            <h3 className="eyebrow">{title}</h3>
            {ms.map((m) => (
              <div key={m.name} className="flex flex-col gap-1">
                <MetricBar name={m.name} value={m.score} bound={boundOf(m)} passed={m.direction === "info" ? null : m.passed} />
                {m.details && m.name !== "flesch_pt" && !m.passed && <p className="text-xs text-ink-3">{m.details}</p>}
                {m.name === "flesch_pt" && <p className="text-xs text-ink-3">{m.details}</p>}
              </div>
            ))}
          </section>
        );
      })}
      {report.feedback && <FeedbackBox feedback={report.feedback} />}
      <JudgeScores scores={report.judge ?? []} threshold={report.metrics.find((m) => m.name.startsWith("judge_"))?.threshold ?? 4} />
    </aside>
  );
}

export function JudgeScores({ scores, threshold }: { scores: JudgeScore[]; threshold: number }) {
  if (!scores.length) return null;
  return (
    <section className="flex flex-col gap-3">
      <h3 className="eyebrow flex items-center gap-1.5"><Gavel aria-hidden className="size-3.5" /> LLM Judge · nota por critério</h3>
      {scores.map((s) => {
        const ok = s.score >= threshold;
        return (
          <div key={s.criterion} className="rounded-lg border border-line p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium">{CRITERION[s.criterion]}</span>
              <span className={cn("flex items-center gap-1.5 font-mono text-sm font-medium", ok ? "text-ok" : "text-bad")}>
                <span aria-hidden className="flex gap-0.5">
                  {[1, 2, 3, 4, 5].map((i) => <span key={i} className={cn("h-2.5 w-1.5 rounded-sm", i <= s.score ? (ok ? "bg-ok" : "bg-bad") : "bg-surface-2")} />)}
                </span>
                {s.score}/5 <span className="sr-only">{ok ? "passou" : "falhou"}</span>
              </span>
            </div>
            <blockquote className="mt-2 border-l-2 border-line-strong pl-2 font-serif text-sm italic text-ink-2">“{s.evidence}”</blockquote>
            <p className="mt-1 text-xs text-ink-3">{s.rationale}</p>
          </div>
        );
      })}
      <p className="text-xs text-ink-3">{metricInfo("judge_tom").help} Mínimo {threshold} em cada critério.</p>
    </section>
  );
}
