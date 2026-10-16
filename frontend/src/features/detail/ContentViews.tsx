import { AlertTriangle, ChevronLeft, ChevronRight, CircleX, Clapperboard, Eye, Timer } from "lucide-react";
import { useState } from "react";
import type { AnchorOut, ArticleBody, CarouselBody, ClaimVerdict, GlossaryTerm, TermOccurrence, VideoScriptBody } from "@/api/types";
import { AnchorPopover, SourceChips } from "@/components/AnchorPopover";
import { TermHighlight } from "@/components/TermHighlight";
import { Button } from "@/components/ui/button";
import { countWords } from "@/features/content";
import { matchClaim, SENTENCE_RE } from "@/lib/claims";
import { cn } from "@/lib/utils";

/** Contexto opcional para anotar o texto (termos, afirmações e fontes). Sem ele, o texto sai limpo. */
export interface Annotations {
  occurrences: TermOccurrence[];
  glossary: Map<string, GlossaryTerm>;
  anchors: Map<string, AnchorOut>;
  claims: ClaimVerdict[];
}

function Sentence({ text, ann }: { text: string; ann: Annotations }) {
  const claim = matchClaim(text, ann.claims);
  const body = <TermHighlight text={text} occurrences={ann.occurrences} glossary={ann.glossary} />;
  if (!claim) return body;
  const bad = claim.verdict !== "sustentada";
  const anchor = claim.anchor_id ? ann.anchors.get(claim.anchor_id) : undefined;
  return (
    <>
      <span
        data-claim={claim.verdict}
        className={cn(
          "rounded-sm box-decoration-clone",
          claim.verdict === "nao_sustentada" && "bg-warn-soft px-0.5",
          claim.verdict === "contradita" && "bg-bad-soft px-0.5",
        )}
      >
        {body}
      </span>
      <AnchorPopover
        anchors={anchor ? [anchor] : []}
        verdict={claim}
        label={bad ? `Afirmação ${claim.verdict === "contradita" ? "contradita" : "não sustentada"}: ver detalhes` : `Fonte da afirmação: ${claim.anchor_id ?? "sem âncora"}`}
      >
        <sup
          className={cn(
            "ml-0.5 inline-flex items-center gap-0.5 rounded px-1 font-mono text-[10px] font-medium not-italic",
            claim.verdict === "sustentada" && "text-ink-3 hover:bg-surface-2 hover:text-ink",
            claim.verdict === "nao_sustentada" && "bg-warn-soft text-warn",
            claim.verdict === "contradita" && "bg-bad-soft text-bad",
          )}
        >
          {claim.verdict === "nao_sustentada" && <AlertTriangle aria-hidden className="size-2.5" />}
          {claim.verdict === "contradita" && <CircleX aria-hidden className="size-2.5" />}
          {claim.anchor_id ?? "?"}
        </sup>
      </AnchorPopover>
    </>
  );
}

/** Texto anotado frase a frase. */
export function AnnotatedText({ text, ann }: { text: string; ann?: Annotations }) {
  if (!ann) return <>{text}</>;
  const parts = text.match(SENTENCE_RE) ?? [text];
  return (
    <>
      {parts.map((p, i) => {
        const lead = p.match(/^\s*/)?.[0] ?? "";
        return (
          <span key={i}>
            {lead}
            <Sentence text={p.slice(lead.length)} ann={ann} />
          </span>
        );
      })}
    </>
  );
}

export function ArticleView({ body, ann, compact }: { body: ArticleBody; ann?: Annotations; compact?: boolean }) {
  const sections = compact ? body.sections.slice(0, 1) : body.sections;
  return (
    <article className={cn("mx-auto flex flex-col", compact ? "gap-3" : "max-w-[68ch] gap-6")}>
      <header className="flex flex-col gap-3">
        <h2 className={cn("font-serif font-semibold leading-tight tracking-tight", compact ? "text-xl" : "text-[2.25rem]")}>
          <AnnotatedText text={body.title} ann={ann} />
        </h2>
        <p className={cn("font-serif text-ink-2", compact ? "text-sm" : "text-xl leading-relaxed")}>
          <AnnotatedText text={body.subtitle} ann={ann} />
        </p>
      </header>
      {!compact && <hr className="border-line" />}
      {sections.map((s, i) => (
        <section key={i} className="flex flex-col gap-2">
          <h3 className={cn("font-sans font-semibold", compact ? "text-sm" : "text-lg")}>
            <AnnotatedText text={s.heading} ann={ann} />
          </h3>
          <p className={cn("font-serif text-ink", compact ? "line-clamp-6 text-sm leading-relaxed" : "text-[1.1875rem] leading-[1.75]")}>
            <AnnotatedText text={s.body} ann={ann} />
          </p>
          {ann && !compact && (
            <div className="flex items-center gap-2 text-xs text-ink-3">
              Fontes da seção: <SourceChips ids={s.anchor_ids ?? []} anchors={ann.anchors} />
            </div>
          )}
        </section>
      ))}
    </article>
  );
}

const ROLE = { gancho: "Gancho", corpo: "Corpo", conclusao: "Conclusão" } as const;

export function CarouselView({ body, ann, compact }: { body: CarouselBody; ann?: Annotations; compact?: boolean }) {
  const [i, setI] = useState(0);
  const slide = body.slides[i];
  const n = body.slides.length;
  return (
    <div className={cn("flex flex-col items-center gap-4", compact && "items-stretch")}>
      <div
        role="group"
        aria-roledescription="slide"
        aria-label={`Slide ${i + 1} de ${n}: ${ROLE[slide.role]}`}
        className={cn(
          "relative flex aspect-[4/5] flex-col justify-between overflow-hidden rounded-2xl border border-line-strong bg-surface p-8 shadow-sm",
          compact ? "w-full p-5" : "w-[440px]",
          slide.role === "gancho" && "bg-ink text-paper",
        )}
      >
        <div className="flex items-center justify-between">
          <span className={cn("eyebrow", slide.role === "gancho" && "text-paper/70")}>{ROLE[slide.role]}</span>
          <span className={cn("font-mono text-xs", slide.role === "gancho" ? "text-paper/70" : "text-ink-3")}>
            {i + 1}/{n}
          </span>
        </div>
        <div className="flex flex-col gap-4">
          <h3 className={cn("font-serif font-semibold leading-tight", compact ? "text-xl" : "text-3xl")}>
            <AnnotatedText text={slide.title} ann={ann} />
          </h3>
          <p className={cn("leading-relaxed", compact ? "text-sm" : "text-lg", slide.role === "gancho" ? "text-paper/85" : "text-ink-2")}>
            <AnnotatedText text={slide.text} ann={ann} />
          </p>
        </div>
        <div className="flex items-end justify-between">
          {ann && !compact ? <SourceChips ids={slide.anchor_ids ?? []} anchors={ann.anchors} /> : <span />}
          {slide.role === "conclusao" && <span className="text-xs font-semibold uppercase tracking-wider">Salve e compartilhe</span>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Button variant="secondary" size="icon" onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0} aria-label="Slide anterior">
          <ChevronLeft aria-hidden />
        </Button>
        <div className="flex gap-1.5" role="tablist" aria-label="Ir para o slide">
          {body.slides.map((s, k) => (
            <button
              key={k}
              role="tab"
              aria-selected={k === i}
              aria-label={`Slide ${k + 1}: ${ROLE[s.role]}`}
              onClick={() => setI(k)}
              className={cn("h-2 rounded-full transition-all cursor-pointer", k === i ? "w-6 bg-ink" : "w-2 bg-line-strong")}
            />
          ))}
        </div>
        <Button variant="secondary" size="icon" onClick={() => setI((v) => Math.min(n - 1, v + 1))} disabled={i === n - 1} aria-label="Próximo slide">
          <ChevronRight aria-hidden />
        </Button>
      </div>
    </div>
  );
}

const WORDS_PER_SECOND = 2.5;

export function ScriptView({ body, ann, compact }: { body: VideoScriptBody; ann?: Annotations; compact?: boolean }) {
  const total = body.blocks.at(-1)?.end_s ?? 0;
  const words = body.blocks.reduce((n, b) => n + countWords(b.speech), 0);
  const spoken = Math.round(words / WORDS_PER_SECOND);
  const over = spoken > 60 || total > 60;
  const blocks = compact ? body.blocks.slice(0, 3) : body.blocks;
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
        <span className={cn("inline-flex items-center gap-1.5 font-medium", over ? "text-bad" : "text-ink")}>
          <Timer aria-hidden className="size-4" />
          ≈ {spoken} s de fala · {words} palavras
        </span>
        <span className="text-ink-3">Roteiro marcado até {total} s · limite 60 s</span>
        {over && <span className="font-medium text-bad">Passa de 60 s</span>}
      </div>
      {!compact && (
        <div className="relative h-8 rounded-md bg-surface-2" aria-hidden>
          {body.blocks.map((b, i) => (
            <div
              key={i}
              className={cn("absolute inset-y-1 rounded border border-surface", i === 0 ? "bg-ink" : "bg-line-strong")}
              style={{ left: `${(b.start_s / 60) * 100}%`, width: `${((b.end_s - b.start_s) / 60) * 100}%` }}
            />
          ))}
          {[0, 15, 30, 45, 60].map((t) => (
            <span key={t} className="absolute -bottom-5 -translate-x-1/2 font-mono text-[10px] text-ink-3" style={{ left: `${(t / 60) * 100}%` }}>
              {t}s
            </span>
          ))}
        </div>
      )}
      <ol className={cn("flex flex-col", compact ? "gap-3" : "mt-4 gap-0")}>
        {blocks.map((b, i) => (
          <li key={i} className={cn("grid gap-4", compact ? "grid-cols-[56px_1fr]" : "grid-cols-[88px_1fr] border-b border-line py-5 last:border-0")}>
            <div className="flex flex-col gap-1">
              <span className="font-mono text-sm font-medium tabular">
                {fmtT(b.start_s)}–{fmtT(b.end_s)}
              </span>
              {i === 0 && <span className="eyebrow">Gancho</span>}
            </div>
            <div className="flex flex-col gap-2">
              <span className="inline-flex items-center gap-1.5 self-start rounded-md bg-surface-2 px-2 py-1 text-xs text-ink-2">
                {i === 0 ? <Clapperboard aria-hidden className="size-3.5" /> : <Eye aria-hidden className="size-3.5" />}
                {b.visual_hook}
              </span>
              <p className={cn("leading-relaxed", compact ? "text-sm" : "font-serif text-lg")}>
                <AnnotatedText text={b.speech} ann={ann} />
              </p>
              {ann && !compact && <SourceChips ids={b.anchor_ids ?? []} anchors={ann.anchors} />}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

const fmtT = (s: number) => `0:${String(Math.round(s)).padStart(2, "0")}`;

export function ContentView({ content, ann, compact }: { content: import("@/api/types").GeneratedContent; ann?: Annotations; compact?: boolean }) {
  const c = content.content;
  if (c.kind === "texto") return <ArticleView body={c as ArticleBody} ann={ann} compact={compact} />;
  if (c.kind === "carrossel") return <CarouselView body={c as CarouselBody} ann={ann} compact={compact} />;
  return <ScriptView body={c as VideoScriptBody} ann={ann} compact={compact} />;
}
