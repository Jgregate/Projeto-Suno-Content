import { ArrowLeft, History, Newspaper } from "lucide-react";
import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useAnchors, useCellTerms, useGlossary, useLatestRunId, useResults } from "@/api/hooks";
import type { Audience, Format } from "@/api/types";
import { LevelTag } from "@/components/LevelTag";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorState, LoadingBlock } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { findCell } from "@/features/content";
import { ContentView, type Annotations } from "@/features/detail/ContentViews";
import { MetricsPanel } from "@/features/detail/MetricsPanel";
import { ReflectionTab } from "@/features/detail/ReflectionTab";
import { FORMAT_LABEL, FORMATS, LEVEL_LABEL, LEVELS } from "@/lib/levels";

export function DetailPage() {
  const { docId = "", level = "", format = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const audience = level as Audience;
  const fmt = format as Format;
  const { runId, isLoading } = useLatestRunId(docId, params.get("run"));
  const results = useResults(runId);
  const anchors = useAnchors(docId);
  const glossary = useGlossary();
  const terms = useCellTerms(runId, audience, fmt);
  const tab = params.get("aba") === "reflection" ? "reflection" : "conteudo";

  const ann: Annotations | undefined = useMemo(() => {
    const cell = results.data && findCell(results.data, audience, fmt);
    if (!cell || !anchors.data || !glossary.data) return undefined;
    return {
      occurrences: terms.data?.occurrences ?? [],
      glossary: new Map(glossary.data.map((t) => [t.termo, t])),
      anchors: new Map(anchors.data.anchors.map((a) => [a.id, a])),
      claims: cell.report?.claims ?? [],
    };
  }, [results.data, anchors.data, glossary.data, terms.data, audience, fmt]);

  const matrixLink = `/docs/${encodeURIComponent(docId)}${runId ? `?run=${encodeURIComponent(runId)}` : ""}`;
  const back = (
    <Button asChild variant="ghost" size="sm">
      <Link to={matrixLink}><ArrowLeft aria-hidden /> Matriz</Link>
    </Button>
  );

  if (!LEVELS.includes(audience) || !FORMATS.includes(fmt)) return <ErrorState title="Célula inválida" error={`Nível ou formato desconhecido: ${level}/${format}.`} action={back} />;
  if (isLoading || results.isLoading) return <LoadingBlock rows={4} />;
  if (results.error || !results.data) return <ErrorState error={results.error ?? "Sem resultados para este documento."} action={back} />;
  const cell = findCell(results.data, audience, fmt);
  if (!cell) return <ErrorState title="Saída não encontrada" error="Esta execução não tem saída para esta célula." action={back} />;

  return (
    <>
      <div className="mb-4">{back}</div>
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <LevelTag level={audience} />
            <span className="eyebrow">{FORMAT_LABEL[fmt]}</span>
          </div>
          <h1 className="font-serif text-3xl font-semibold tracking-tight">{FORMAT_LABEL[fmt]} para o leitor {LEVEL_LABEL[audience].toLowerCase()}</h1>
        </div>
        <StatusBadge status={cell.status} />
      </header>

      <Tabs value={tab} onValueChange={(v) => setParams((p) => { p.set("aba", v === "reflection" ? "reflection" : "conteudo"); return p; })}>
        <TabsList aria-label="Seções do detalhe">
          <TabsTrigger value="conteudo"><Newspaper aria-hidden /> Conteúdo e métricas</TabsTrigger>
          <TabsTrigger value="reflection">
            <History aria-hidden /> Reflection
            <span className="rounded bg-surface-2 px-1.5 font-mono text-xs">{cell.history.length}</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="conteudo">
          <div className="grid items-start gap-10 xl:grid-cols-[minmax(0,1fr)_380px] lg:grid-cols-[minmax(0,1fr)_340px]">
            <div className="flex flex-col gap-6">
              <Legend />
              <div className="rounded-2xl border border-line bg-surface px-10 py-10">
                <ContentView content={cell.content} ann={ann} />
              </div>
              {cell.status && cell.status.delivered_attempt !== cell.history.at(-1)?.attempt && (
                <p className="text-sm text-ink-3">Nenhuma tentativa aprovou; esta é a de melhor nota (tentativa {cell.status.delivered_attempt}).</p>
              )}
            </div>
            {cell.report ? <MetricsPanel report={cell.report} /> : <p className="text-sm text-ink-3">Sem relatório de avaliação.</p>}
          </div>
        </TabsContent>
        <TabsContent value="reflection">
          <ReflectionTab history={cell.history} status={cell.status} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function Legend() {
  return (
    <ul aria-label="Legenda" className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-ink-2">
      <li className="flex items-center gap-1.5"><span className="underline decoration-ok decoration-dotted decoration-2 underline-offset-4">termo</span> termo técnico explicado ou esperado no nível</li>
      <li className="flex items-center gap-1.5"><span className="rounded-sm bg-bad-soft px-0.5 underline decoration-bad decoration-wavy underline-offset-4">termo</span> termo sem explicação</li>
      <li className="flex items-center gap-1.5"><sup className="font-mono text-[10px] text-ink-3">A01</sup> fonte da afirmação (clique)</li>
      <li className="flex items-center gap-1.5"><span className="rounded-sm bg-warn-soft px-1">frase</span> afirmação não sustentada</li>
      <li className="flex items-center gap-1.5"><span className="rounded-sm bg-bad-soft px-1">frase</span> contradita</li>
      <li className="text-ink-3">Passe o mouse nos termos; clique nas fontes.</li>
    </ul>
  );
}
