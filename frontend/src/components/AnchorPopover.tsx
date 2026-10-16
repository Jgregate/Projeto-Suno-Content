import { AlertTriangle, BookOpenText, CircleCheck, CircleHelp, CircleX } from "lucide-react";
import type { ReactNode } from "react";
import type { AnchorOut, ClaimVerdict } from "@/api/types";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

const VERDICT = {
  sustentada: { label: "Afirmação sustentada", icon: CircleCheck, cls: "text-ok" },
  nao_sustentada: { label: "Afirmação não sustentada", icon: CircleHelp, cls: "text-warn" },
  contradita: { label: "Afirmação contradita pela fonte", icon: CircleX, cls: "text-bad" },
} as const;

export function AnchorCard({ anchor }: { anchor: AnchorOut }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-xs font-medium text-ink-2">{anchor.id}</span>
        <span className="text-xs text-ink-3">
          p. {anchor.page}
          {anchor.source_doc_id ? ` · ${anchor.source_doc_id}` : ""}
        </span>
      </div>
      <p className="font-medium leading-snug">{anchor.claim}</p>
      <blockquote className="border-l-2 border-line-strong pl-3 font-serif text-sm italic leading-relaxed text-ink-2">
        “{anchor.source_excerpt}”
      </blockquote>
      {!anchor.valid && (
        <p className="flex items-center gap-1.5 text-xs text-bad">
          <AlertTriangle aria-hidden className="size-3.5" /> Âncora inválida: número(s) {anchor.invalid_numbers.join(", ")} fora da fonte
        </p>
      )}
    </div>
  );
}

/** Mostra a(s) âncora(s) que sustentam um trecho; com `verdict`, também o veredito do checker. */
export function AnchorPopover({
  anchors, verdict, children, label,
}: { anchors: AnchorOut[]; verdict?: ClaimVerdict; children: ReactNode; label: string }) {
  const v = verdict ? VERDICT[verdict.verdict] : null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" aria-label={label} className="cursor-pointer text-left">
          {children}
        </button>
      </PopoverTrigger>
      <PopoverContent>
        <div className="flex flex-col gap-4">
          {v && verdict && (
            <div className={cn("flex items-start gap-2", v.cls)}>
              <v.icon aria-hidden className="mt-0.5 size-4 shrink-0" />
              <div>
                <p className="font-medium">{v.label}</p>
                {verdict.justification && <p className="text-xs text-ink-2">{verdict.justification}</p>}
              </div>
            </div>
          )}
          {anchors.length === 0 && <p className="text-ink-2">Nenhuma âncora associada a este trecho.</p>}
          {anchors.map((a) => (
            <AnchorCard key={a.id} anchor={a} />
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

export function SourceChips({ ids, anchors }: { ids: string[]; anchors: Map<string, AnchorOut> }) {
  if (!ids.length) return null;
  const list = ids.map((id) => anchors.get(id)).filter((a): a is AnchorOut => !!a);
  return (
    <AnchorPopover anchors={list} label={`Fontes deste trecho: ${ids.join(", ")}`}>
      <span className="inline-flex items-center gap-1 rounded-md border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2 hover:border-line-strong hover:text-ink">
        <BookOpenText aria-hidden className="size-3" />
        {ids.join(" · ")}
      </span>
    </AnchorPopover>
  );
}
