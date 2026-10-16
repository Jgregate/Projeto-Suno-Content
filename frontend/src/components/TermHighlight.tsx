import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { GlossaryTerm, TermOccurrence } from "@/api/types";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import { LEVEL_LABEL } from "@/lib/levels";
import { segmentTerms } from "@/lib/terms";
import { cn } from "@/lib/utils";

export function TermMark({ occurrence, term, children }: { occurrence: TermOccurrence; term?: GlossaryTerm; children: string }) {
  const missing = occurrence.needs_context && !occurrence.contextualized;
  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <span
          tabIndex={0}
          data-term-status={missing ? "sem-contexto" : occurrence.needs_context ? "contextualizado" : "permitido"}
          className={cn(
            "cursor-help rounded-sm underline underline-offset-4",
            missing ? "bg-bad-soft shadow-[0_0_0_2px_var(--bad-soft)] decoration-bad decoration-wavy" : "decoration-ok decoration-dotted decoration-2",
          )}
        >
          {children}
          <span className="sr-only">{missing ? " (termo técnico sem explicação)" : " (termo técnico)"}</span>
        </span>
      </HoverCardTrigger>
      <HoverCardContent>
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-serif text-base font-semibold">{occurrence.termo}</span>
            {term && <span className="text-xs text-ink-3">sem explicação a partir de: {LEVEL_LABEL[term.nivel_minimo]}</span>}
          </div>
          {missing ? (
            <p className="flex items-start gap-1.5 text-bad">
              <AlertTriangle aria-hidden className="mt-0.5 size-4 shrink-0" /> Sem explicação na mesma frase nem na anterior.
            </p>
          ) : occurrence.needs_context ? (
            <p className="flex items-start gap-1.5 text-ok">
              <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0" /> Contextualizado (marcador: “{occurrence.marker}”).
            </p>
          ) : (
            <p className="flex items-start gap-1.5 text-ok">
              <CheckCircle2 aria-hidden className="mt-0.5 size-4 shrink-0" /> Vocabulário esperado para este nível.
            </p>
          )}
          {term && (
            <p className="text-ink-2">
              <span className="eyebrow mb-1 block">Analogia de referência</span>
              {term.analogia_iniciante}
            </p>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}

/** Texto com os termos do glossário destacados. */
export function TermHighlight({ text, occurrences, glossary }: { text: string; occurrences: TermOccurrence[]; glossary: Map<string, GlossaryTerm> }) {
  return (
    <>
      {segmentTerms(text, occurrences).map((s, i) =>
        s.occurrence ? (
          <TermMark key={i} occurrence={s.occurrence} term={glossary.get(s.occurrence.termo)}>
            {s.text}
          </TermMark>
        ) : (
          <span key={i}>{s.text}</span>
        ),
      )}
    </>
  );
}
