import { ArrowRight, CheckCircle2, MessageSquareWarning, XCircle } from "lucide-react";
import { Fragment } from "react";
import type { AttemptRecord, CellStatus } from "@/api/types";
import { PassMark, StatusBadge } from "@/components/StatusBadge";
import { plainText } from "@/features/content";
import { FeedbackBox } from "@/features/detail/MetricsPanel";
import { diffUnits, toUnits } from "@/lib/diff";
import { boundOf, boundText, fmt, fmtMetric, metricInfo } from "@/lib/metrics";
import { cn, fmtMs } from "@/lib/utils";

const failedCount = (a: AttemptRecord) => a.report.metrics.filter((m) => !m.passed).length;

/** Histórico do reflection loop da célula: tentativas, feedback injetado e diff. */
export function ReflectionTab({ history, status }: { history: AttemptRecord[]; status?: CellStatus | null }) {
  if (history.length <= 1) {
    const only = history[0];
    return (
      <div className="flex flex-col items-start gap-3 rounded-xl border border-line bg-surface p-8">
        <StatusBadge status={status} />
        <p className="max-w-xl text-ink-2">
          {only?.report.passed
            ? "Esta saída passou em todas as métricas na primeira tentativa, então o loop de correção não precisou agir."
            : "Esta saída tem uma única tentativa registrada."}{" "}
          Para ver o loop em ação, gere o documento com “Forçar desvio de nível” ligado.
        </p>
      </div>
    );
  }

  const first = history[0];
  const last = history[history.length - 1];
  const delivered = history.find((h) => h.attempt === status?.delivered_attempt) ?? last;
  const metricNames = first.report.metrics.map((m) => m.name);

  return (
    <div className="flex flex-col gap-10">
      {/* resumo em uma linha: o que aconteceu */}
      <section aria-label="Resumo da correção" className="grid grid-cols-[1fr_auto_1fr_auto_1fr] items-stretch gap-3">
        <StoryCard tone="bad" title={`Tentativa 1 reprovou`} big={`${failedCount(first)} de ${first.report.metrics.length}`} caption="métricas fora do limiar do nível" />
        <ArrowRight aria-hidden className="self-center text-ink-3" />
        <StoryCard tone="warn" title="Feedback numérico" big={`${history.length - 1}×`} caption="relatório do avaliador injetado no refinamento" />
        <ArrowRight aria-hidden className="self-center text-ink-3" />
        <StoryCard
          tone={delivered.report.passed ? "ok" : "bad"}
          title={`Tentativa ${delivered.attempt} ${delivered.report.passed ? "aprovou" : "foi a melhor"}`}
          big={`${fmt(first.aggregate_score * 100)} → ${fmt(delivered.aggregate_score * 100)}`}
          caption="nota agregada (0 a 100)"
        />
      </section>

      {/* linha do tempo */}
      <section aria-label="Linha do tempo das tentativas" className="flex flex-col gap-3">
        <h3 className="eyebrow">Linha do tempo</h3>
        <ol className="flex items-stretch gap-3">
          {history.map((h, i) => (
            <Fragment key={h.attempt}>
              {i > 0 && <li aria-hidden className="self-center text-ink-3"><ArrowRight className="size-4" /></li>}
              <li className={cn("flex flex-1 flex-col gap-2 rounded-xl border bg-surface p-4", h.report.passed ? "border-ok/40" : "border-bad/40")}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold">Tentativa {h.attempt}</span>
                  {h.report.passed ? (
                    <span className="inline-flex items-center gap-1 text-sm font-medium text-ok"><CheckCircle2 aria-hidden className="size-4" /> Aprovada</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-sm font-medium text-bad"><XCircle aria-hidden className="size-4" /> {failedCount(h)} falha(s)</span>
                  )}
                </div>
                <div className="h-1.5 rounded-full bg-surface-2" aria-hidden>
                  <div className={cn("h-full rounded-full", h.report.passed ? "bg-ok" : "bg-bad")} style={{ width: `${h.aggregate_score * 100}%` }} />
                </div>
                <span className="font-mono text-xs text-ink-3 tabular">
                  nota {fmt(h.aggregate_score * 100)} · {h.input_tokens + h.output_tokens} tokens · {fmtMs(h.latency_ms)}
                </span>
                {(h.regressions?.length ?? 0) > 0 && <span className="text-xs text-bad">Regressão: {h.regressions?.join(", ")}</span>}
              </li>
            </Fragment>
          ))}
        </ol>
      </section>

      {/* métricas por tentativa */}
      <section aria-label="Métricas por tentativa" className="flex flex-col gap-3">
        <h3 className="eyebrow">Métricas por tentativa</h3>
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left">
                <th scope="col" className="px-4 py-3 font-medium text-ink-2">Métrica</th>
                <th scope="col" className="px-4 py-3 font-medium text-ink-2">Limiar</th>
                {history.map((h) => <th key={h.attempt} scope="col" className="px-4 py-3 font-medium text-ink-2">Tentativa {h.attempt}</th>)}
              </tr>
            </thead>
            <tbody>
              {metricNames.map((name) => {
                const base = first.report.metrics.find((m) => m.name === name)!;
                return (
                  <tr key={name} className="border-b border-line last:border-0">
                    <th scope="row" className="px-4 py-3 text-left font-normal">{metricInfo(name).label}</th>
                    <td className="px-4 py-3 text-ink-3">{boundText(boundOf(base), metricInfo(name).unit)}</td>
                    {history.map((h, i) => {
                      const m = h.report.metrics.find((x) => x.name === name);
                      const prev = i > 0 ? history[i - 1].report.metrics.find((x) => x.name === name) : undefined;
                      const delta = m && prev ? m.score - prev.score : null;
                      return (
                        <td key={h.attempt} className={cn("px-4 py-3", m && !m.passed && "bg-bad-soft/60")}>
                          {m ? (
                            <span className="flex items-center gap-3">
                              <span className="font-mono tabular">{fmtMetric(name, m.score)}</span>
                              {delta != null && Math.abs(delta) > 1e-9 && (
                                <span className="font-mono text-xs text-ink-3 tabular">{delta > 0 ? "▲" : "▼"} {fmt(Math.abs(delta))}</span>
                              )}
                              <PassMark passed={m.direction === "info" ? null : m.passed} className="ml-auto" />
                            </span>
                          ) : "—"}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* cada iteração: feedback injetado + diff */}
      {history.slice(1).map((h, i) => {
        const before = history[i];
        const ops = diffUnits(toUnits(plainText(before.content)), toUnits(plainText(h.content)));
        return (
          <section key={h.attempt} aria-label={`Da tentativa ${before.attempt} para a ${h.attempt}`} className="flex flex-col gap-4">
            <h3 className="font-serif text-xl font-semibold">
              Tentativa {before.attempt} <ArrowRight aria-hidden className="inline size-4 align-middle text-ink-3" /> Tentativa {h.attempt}
            </h3>
            <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
              <FeedbackBox feedback={h.injected_feedback} title="Feedback injetado no refinamento" />
              <div className="rounded-xl border border-line bg-surface p-5">
                <p className="mb-3 flex items-center gap-4 text-xs text-ink-3">
                  <span className="inline-flex items-center gap-1"><span className="inline-block size-2.5 rounded-sm bg-bad-soft ring-1 ring-bad/40" /> removido</span>
                  <span className="inline-flex items-center gap-1"><span className="inline-block size-2.5 rounded-sm bg-ok-soft ring-1 ring-ok/40" /> adicionado</span>
                </p>
                <div className="flex flex-col gap-1 font-serif text-[15px] leading-relaxed">
                  {ops.map((op, k) => (
                    <p
                      key={k}
                      className={cn(
                        "rounded px-2 py-0.5",
                        op.type === "removed" && "bg-bad-soft text-ink-2 line-through decoration-bad/50",
                        op.type === "added" && "bg-ok-soft",
                        op.type === "equal" && "text-ink-3",
                      )}
                    >
                      <span className="sr-only">{op.type === "removed" ? "Removido: " : op.type === "added" ? "Adicionado: " : ""}</span>
                      {op.text}
                    </p>
                  ))}
                </div>
              </div>
            </div>
          </section>
        );
      })}
      {!history.some((h) => h.injected_feedback) && (
        <p className="flex items-center gap-2 text-sm text-ink-3"><MessageSquareWarning aria-hidden className="size-4" /> Nenhum feedback registrado.</p>
      )}
    </div>
  );
}

function StoryCard({ tone, title, big, caption }: { tone: "ok" | "bad" | "warn"; title: string; big: string; caption: string }) {
  const Icon = tone === "ok" ? CheckCircle2 : tone === "bad" ? XCircle : MessageSquareWarning;
  return (
    <div className={cn("flex flex-col gap-2 rounded-xl border p-5", tone === "ok" && "border-ok/30 bg-ok-soft", tone === "bad" && "border-bad/30 bg-bad-soft", tone === "warn" && "border-warn/30 bg-warn-soft")}>
      <span className={cn("flex items-center gap-2 text-sm font-semibold", tone === "ok" ? "text-ok" : tone === "bad" ? "text-bad" : "text-warn")}>
        <Icon aria-hidden className="size-4" /> {title}
      </span>
      <span className="font-serif text-3xl font-semibold tabular">{big}</span>
      <span className="text-sm text-ink-2">{caption}</span>
    </div>
  );
}
