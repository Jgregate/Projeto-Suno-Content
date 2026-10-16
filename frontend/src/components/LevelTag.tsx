import type { Audience } from "@/api/types";
import { LEVEL_LABEL, LEVEL_STYLE } from "@/lib/levels";
import { cn } from "@/lib/utils";

const DOTS: Record<Audience, number> = { iniciante: 1, intermediario: 2, avancado: 3 };

/** Nível com cor própria + marcador de 1 a 3 pontos (não depende só da cor). */
export function LevelTag({ level, className }: { level: Audience; className?: string }) {
  const s = LEVEL_STYLE[level];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold", s.soft, s.text, className)}>
      <span aria-hidden className="flex gap-0.5">
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("size-1.5 rounded-full", i <= DOTS[level] ? s.bg : "bg-current opacity-20")} />
        ))}
      </span>
      {LEVEL_LABEL[level]}
    </span>
  );
}
