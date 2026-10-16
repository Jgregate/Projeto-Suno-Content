import type { Bound } from "@/api/types";
import { PassMark } from "@/components/StatusBadge";
import { boundText, fmt, metricInfo, passes } from "@/lib/metrics";
import { cn } from "@/lib/utils";

interface Props {
  name: string;
  value: number;
  bound: Bound;
  /** sobrepõe o cálculo (ex.: métrica informativa) */
  passed?: boolean | null;
  compact?: boolean;
  delta?: number | null;
  className?: string;
}

const clamp = (v: number, [a, b]: [number, number]) => Math.min(1, Math.max(0, (v - a) / (b - a)));

/** Barra com o valor, a faixa aceita do nível sombreada e o(s) limiar(es) marcados. */
export function MetricBar({ name, value, bound, passed, compact, delta, className }: Props) {
  const info = metricInfo(name);
  const informative = bound.min == null && bound.max == null;
  const ok = passed !== undefined ? passed : informative ? null : passes(value, bound);
  const lo = bound.min != null ? clamp(bound.min, info.domain) : 0;
  const hi = bound.max != null ? clamp(bound.max, info.domain) : 1;
  const pos = clamp(value, info.domain);
  const shown = info.unit === "%" ? `${fmt(value)}%` : name === "claim_support" ? `${fmt(value * 100)}%` : fmt(value);
  const label = `${info.label}: ${shown}. Limiar ${boundText(bound, info.unit)}. ${ok === null ? "Informativa." : ok ? "Passou." : "Falhou."}`;

  return (
    <div className={cn("flex flex-col gap-1.5", className)} role="group" aria-label={label} data-passed={ok === null ? "info" : String(ok)}>
      <div className="flex items-baseline justify-between gap-2">
        <span className={cn("text-ink-2", compact ? "text-xs" : "text-sm")}>{compact ? info.short : info.label}</span>
        <span className="flex items-baseline gap-2">
          <span className={cn("font-mono tabular font-medium", compact ? "text-sm" : "text-base")}>{shown}</span>
          {delta != null && delta !== 0 && (
            <span className={cn("font-mono text-xs tabular", delta > 0 ? "text-ink-2" : "text-ink-3")}>
              {delta > 0 ? "▲" : "▼"} {fmt(Math.abs(delta))}
            </span>
          )}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-surface-2" aria-hidden>
        {!informative && (
          <div
            className="absolute inset-y-0 rounded-full bg-ok/15 ring-1 ring-ok/25 ring-inset"
            style={{ left: `${lo * 100}%`, width: `${Math.max(0, hi - lo) * 100}%` }}
          />
        )}
        {bound.min != null && <span className="absolute -inset-y-1 w-px bg-ink-2" style={{ left: `${lo * 100}%` }} />}
        {bound.max != null && <span className="absolute -inset-y-1 w-px bg-ink-2" style={{ left: `${hi * 100}%` }} />}
        <span
          className={cn(
            "absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface",
            ok === null ? "bg-ink-3" : ok ? "bg-ok" : "bg-bad",
          )}
          style={{ left: `${pos * 100}%` }}
        />
      </div>
      {!compact && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-ink-3">Limiar do nível: {boundText(bound, info.unit)}</span>
          <PassMark passed={ok} />
        </div>
      )}
      {compact && <PassMark passed={ok} className="self-end" />}
    </div>
  );
}
