import type { ArticleBody, CarouselBody, CellResult, GeneratedContent, RunResults, VideoScriptBody } from "@/api/types";
import type { Audience, Format } from "@/api/types";

export const asArticle = (c: GeneratedContent) => (c.content.kind === "texto" ? (c.content as ArticleBody) : null);
export const asCarousel = (c: GeneratedContent) => (c.content.kind === "carrossel" ? (c.content as CarouselBody) : null);
export const asScript = (c: GeneratedContent) => (c.content.kind === "roteiro" ? (c.content as VideoScriptBody) : null);

/** Título curto do conteúdo, para cards. */
export function headline(c: GeneratedContent): string {
  const a = asArticle(c);
  if (a) return a.title;
  const k = asCarousel(c);
  if (k) return k.slides[0]?.title ?? "";
  const s = asScript(c);
  return s?.blocks[0]?.speech ?? "";
}

/** Texto corrido (mesma regra do avaliador): artigo inteiro, slides concatenados, roteiro só a fala. */
export function plainText(c: GeneratedContent): string {
  const a = asArticle(c);
  if (a) return [a.title, a.subtitle, ...a.sections.map((s) => `${s.heading}\n${s.body}`)].join("\n\n");
  const k = asCarousel(c);
  if (k) return k.slides.map((s) => `${s.title}\n${s.text}`).join("\n\n");
  return asScript(c)?.blocks.map((b) => b.speech).join("\n") ?? "";
}

export const countWords = (t: string) => (t.match(/\d+(?:[.,]\d+)*%?|[\p{L}]+(?:[-'][\p{L}]+)*/gu) ?? []).length;

/** Ritmo de fala de referência (150 palavras/min): 60 s comportam ~150 palavras. */
export const WORDS_PER_SECOND = 2.5;
export const SCRIPT_LIMIT_S = 60;

/** Duração estimada da fala do roteiro, em segundos. */
export const spokenSeconds = (s: VideoScriptBody) =>
  Math.round(s.blocks.reduce((n, b) => n + countWords(b.speech), 0) / WORDS_PER_SECOND);

export const findCell = (r: RunResults, audience: Audience, format: Format): CellResult | undefined =>
  r.cells.find((c) => c.audience === audience && c.format === format);
