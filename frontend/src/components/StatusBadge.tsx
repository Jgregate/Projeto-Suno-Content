import { CheckCircle2, CircleDashed, RotateCcw, XCircle } from "lucide-react";
import type { CellStatus } from "@/api/types";
import { statusText } from "@/lib/status";
import { cn } from "@/lib/utils";

/** Status com ícone e texto, sem depender só da cor. */
export function StatusBadge({ status, size = "md", className }: { status: CellStatus | null | undefined; size?: "sm" | "md"; className?: string }) {
  const approved = status?.status.startsWith("aprovado");
  const retried = status?.status.startsWith("aprovado_apos");
  const Icon = !status ? CircleDashed : approved ? (retried ? RotateCcw : CheckCircle2) : XCircle;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        !status && "border-line bg-surface-2 text-ink-2",
        approved && "border-ok/30 bg-ok-soft text-ok",
        status && !approved && "border-bad/30 bg-bad-soft text-bad",
        className,
      )}
    >
      <Icon aria-hidden className={size === "sm" ? "size-3.5" : "size-4"} />
      {statusText(status)}
    </span>
  );
}

export function PassMark({ passed, className }: { passed: boolean | null; className?: string }) {
  if (passed === null) return <span className={cn("text-xs text-ink-3", className)}>—</span>;
  const Icon = passed ? CheckCircle2 : XCircle;
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs font-medium", passed ? "text-ok" : "text-bad", className)}>
      <Icon aria-hidden className="size-3.5" />
      {passed ? "Passou" : "Falhou"}
    </span>
  );
}
