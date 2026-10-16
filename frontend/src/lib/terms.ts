import type { TermOccurrence } from "@/api/types";

export type Segment = { text: string; occurrence?: TermOccurrence };

/** Divide o texto em trechos, marcando cada ocorrência de termo (pelo `surface` exato, em ordem). */
export function segmentTerms(text: string, occurrences: TermOccurrence[]): Segment[] {
  const found: { start: number; end: number; occurrence: TermOccurrence }[] = [];
  const surfaces = [...new Map(occurrences.map((o) => [o.surface, o])).values()].sort((a, b) => b.surface.length - a.surface.length);
  for (const occ of surfaces) {
    let from = 0;
    while (occ.surface) {
      const i = text.indexOf(occ.surface, from);
      if (i < 0) break;
      const end = i + occ.surface.length;
      if (!found.some((f) => i < f.end && end > f.start)) {
        // escolhe a ocorrência cuja frase contém este ponto do texto (o status pode variar por frase)
        const own = occurrences.find((o) => o.surface === occ.surface && text.slice(Math.max(0, i - 200), end + 200).includes(o.sentence)) ?? occ;
        found.push({ start: i, end, occurrence: own });
      }
      from = end;
    }
  }
  found.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let cursor = 0;
  for (const f of found) {
    if (f.start > cursor) out.push({ text: text.slice(cursor, f.start) });
    out.push({ text: text.slice(f.start, f.end), occurrence: f.occurrence });
    cursor = f.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor) });
  return out;
}

