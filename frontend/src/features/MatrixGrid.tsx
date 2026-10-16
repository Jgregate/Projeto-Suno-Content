import { ArrowUpRight, Timer } from "lucide-react";
import { Link } from "react-router";
import type { CellResult, RunResults } from "@/api/types";
import { LevelTag } from "@/components/LevelTag";
import { PassMark, StatusBadge } from "@/components/StatusBadge";
import { asScript, headline, SCRIPT_LIMIT_S, spokenSeconds } from "@/features/content";
import { cellPath, FORMAT_LABEL, FORMATS, LEVEL_HINT, LEVEL_STYLE, LEVELS } from "@/lib/levels";
import { headlineMetrics } from "@/lib/metrics";
import { cn } from "@/lib/utils";

export function MatrixCell({ cell, docId, runId }: { cell: CellResult; docId: string; runId: string }) {
  const metrics = cell.report ? headlineMetrics(cell.report.metrics) : [];
  const attempts = cell.status?.attempts ?? cell.history.length ?? 1;
  return (
    <Link
      to={cellPath(docId, cell.audience, cell.format, runId)}
      data-testid="matrix-cell"
      className={cn(
        "group flex h-full flex-col gap-4 rounded-xl border border-line bg-surface p-5 transition-all",
        "hover:-translate-y-0.5 hover:border-line-strong hover:shadow-lg",
        "border-t-4", LEVEL_STYLE[cell.audience].borderTop,
      )}
      aria-label={`${FORMAT_LABEL[cell.format]} para o nível ${cell.audience}: abrir detalhe`}
    >
      <div className="flex items-start justify-between gap-2">
        <StatusBadge status={cell.status} size="sm" />
        {!cell.status?.status.startsWith("aprovado_apos") && (
          <span className="font-mono text-xs text-ink-3">
            {attempts} {attempts === 1 ? "tentativa" : "tentativas"}
          </span>
        )}
      </div>
      <p className="line-clamp-2 min-h-[2.75rem] font-serif text-[17px] font-semibold leading-snug">{headline(cell.content)}</p>
      <ScriptDuration cell={cell} />
      <ul className="mt-auto grid grid-cols-2 gap-x-4 gap-y-2 border-t border-line pt-3">
        {metrics.map((m) => (
          <li key={m.key} className="flex items-center justify-between gap-2 text-xs">
            <span className="text-ink-2">{m.label}</span>
            <PassMark passed={m.passed} />
          </li>
        ))}
      </ul>
      <span className="flex items-center gap-1 text-xs font-medium text-ink-3 group-hover:text-ink">
        Ver detalhe <ArrowUpRight aria-hidden className="size-3.5" />
      </span>
    </Link>
  );
}

/** Roteiros: fala estimada contra o limite de 60 s do formato. */
function ScriptDuration({ cell }: { cell: CellResult }) {
  const script = asScript(cell.content);
  if (!script) return null;
  const s = spokenSeconds(script);
  const over = s > SCRIPT_LIMIT_S;
  return (
    <span
      className={cn("inline-flex w-fit items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-bold", over ? "bg-bad-soft text-bad" : "bg-surface-2 text-ink-2")}
      title="Fala estimada a 150 palavras por minuto"
    >
      <Timer aria-hidden className="size-3" />
      fala ≈ {s} s / {SCRIPT_LIMIT_S} s
    </span>
  );
}

export function MatrixGrid({ results, docId }: { results: RunResults; docId: string }) {
  return (
    <div role="table" aria-label="Matriz de níveis por formato" className="grid grid-cols-[200px_repeat(3,minmax(0,1fr))] gap-4">
      <div role="row" className="contents">
        <span role="columnheader"><span className="sr-only">Nível</span></span>
        {FORMATS.map((f) => (
          <span key={f} role="columnheader" className="eyebrow px-1">{FORMAT_LABEL[f]}</span>
        ))}
      </div>
      {LEVELS.map((level) => (
        <div role="row" key={level} className="contents">
          <div role="rowheader" className="flex flex-col gap-2 pt-4">
            <LevelTag level={level} className="self-start" />
            <span className="text-xs leading-snug text-ink-3">{LEVEL_HINT[level]}</span>
          </div>
          {FORMATS.map((format) => {
            const cell = results.cells.find((c) => c.audience === level && c.format === format);
            return (
              <div role="cell" key={format}>
                {cell ? (
                  <MatrixCell cell={cell} docId={docId} runId={results.run_id} />
                ) : (
                  <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-line p-5 text-sm text-ink-3">
                    Sem saída para esta célula
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
