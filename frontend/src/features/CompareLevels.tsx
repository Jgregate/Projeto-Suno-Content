import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router";
import type { Format, RunResults } from "@/api/types";
import { LevelTag } from "@/components/LevelTag";
import { MetricBar } from "@/components/MetricBar";
import { StatusBadge } from "@/components/StatusBadge";
import { countWords, plainText } from "@/features/content";
import { ContentView } from "@/features/detail/ContentViews";
import { cellPath, LEVEL_STYLE, LEVELS } from "@/lib/levels";
import { boundOf, metricInfo } from "@/lib/metrics";
import { cn } from "@/lib/utils";

const ORDER = ["flesch_pt", "term_density", "term_context_pct", "numeric_grounding", "claim_support", "claim_contradictions",
  "judge_adequacao_publico", "judge_tom", "judge_nuances", "judge_formato"];

/** Mesmo formato, três níveis lado a lado; métricas alinhadas linha a linha. */
export function CompareLevels({ results, docId, format }: { results: RunResults; docId: string; format: Format }) {
  const cells = LEVELS.map((l) => results.cells.find((c) => c.audience === l && c.format === format));
  const names = ORDER.filter((n) => cells.some((c) => c?.report?.metrics.some((m) => m.name === n)));
  return (
    <div className="grid grid-cols-3 gap-x-6">
      {cells.map((cell, i) => (
        <div key={LEVELS[i]} className={cn("flex flex-col gap-3 rounded-t-xl border-x border-t border-line bg-surface p-5 border-t-4", LEVEL_STYLE[LEVELS[i]].borderTop)}>
          <div className="flex items-center justify-between gap-2">
            <LevelTag level={LEVELS[i]} />
            {cell && <StatusBadge status={cell.status} size="sm" />}
          </div>
          {cell && (
            <span className="font-mono text-xs text-ink-3">
              {countWords(plainText(cell.content))} palavras · {cell.status?.attempts ?? 1} {cell.status?.attempts === 1 ? "tentativa" : "tentativas"}
            </span>
          )}
        </div>
      ))}
      {cells.map((cell, i) => (
        <div key={`c-${LEVELS[i]}`} className="flex min-h-[340px] flex-col gap-4 border-x border-line bg-surface px-5 pb-5">
          {cell ? <ContentView content={cell.content} compact /> : <p className="text-sm text-ink-3">Sem saída.</p>}
          {cell && (
            <Link to={cellPath(docId, cell.audience, cell.format, results.run_id)} className="mt-auto inline-flex items-center gap-1 self-start text-sm font-medium text-ink-2 hover:text-ink">
              Abrir detalhe <ArrowUpRight aria-hidden className="size-4" />
            </Link>
          )}
        </div>
      ))}
      <div className="col-span-3 grid grid-cols-3 gap-x-6">
        <div className="col-span-3 grid grid-cols-3 gap-x-6">
          {LEVELS.map((l) => (
            <div key={l} className="border-x border-t border-line bg-surface-2/60 px-5 py-2">
              <span className="eyebrow">Métricas</span>
            </div>
          ))}
        </div>
        {names.map((name, row) => (
          <div key={name} className="col-span-3 grid grid-cols-3 gap-x-6" aria-label={metricInfo(name).label}>
            {cells.map((cell, i) => {
              const m = cell?.report?.metrics.find((x) => x.name === name);
              return (
                <div
                  key={LEVELS[i]}
                  className={cn("border-x border-line bg-surface px-5 py-3", row === names.length - 1 && "rounded-b-xl border-b", row % 2 === 1 && "bg-surface-2/40")}
                >
                  {m ? <MetricBar name={name} value={m.score} bound={boundOf(m)} passed={m.direction === "info" ? null : m.passed} compact /> : <span className="text-xs text-ink-3">—</span>}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
