import { ArrowLeft, Columns3, Grid3x3, Shuffle } from "lucide-react";
import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { useDocuments, useLatestRunId, useResults } from "@/api/hooks";
import type { Format } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CompareLevels } from "@/features/CompareLevels";
import { MatrixGrid } from "@/features/MatrixGrid";
import { FORMAT_LABEL, FORMATS, LEVEL_LABEL } from "@/lib/levels";
import { fmtMs } from "@/lib/utils";

export function MatrixPage() {
  const { docId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const view = params.get("view") === "comparar" ? "comparar" : "matriz";
  const [format, setFormat] = useState<Format>((params.get("formato") as Format) || "texto");
  const { runId, isLoading, error } = useLatestRunId(docId, params.get("run"));
  const results = useResults(runId);
  const doc = useDocuments().data?.find((d) => d.id === docId);

  const back = (
    <Button asChild variant="ghost" size="sm">
      <Link to="/documentos"><ArrowLeft aria-hidden /> Documentos</Link>
    </Button>
  );

  if (isLoading || results.isLoading) return <LoadingBlock rows={4} />;
  if (error) {
    return (
      <EmptyState title="Este documento ainda não tem conteúdos" action={back}>
        Volte à lista de documentos e clique em “Gerar conteúdos”.
      </EmptyState>
    );
  }
  if (results.error || !results.data) return <ErrorState error={results.error ?? "Sem resultados."} action={back} />;

  const r = results.data;
  const approved = r.cells.filter((c) => c.status?.status.startsWith("aprovado")).length;
  const totalCost = (r.generation?.wall_ms ?? 0) + (r.evaluation?.wall_ms ?? 0);

  return (
    <>
      <div className="mb-4">{back}</div>
      <PageHeader eyebrow="Matriz de saídas" title={doc?.title ?? r.doc_id}>
        <span className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
          <span><strong className="font-semibold text-ink">{approved} de {r.cells.length}</strong> saídas aprovadas</span>
          <span>gerado em {new Date(r.created_at).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}</span>
          <span>tempo total {fmtMs(totalCost)}</span>
          {r.force_drift && (
            <span className="inline-flex items-center gap-1 rounded-full bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">
              <Shuffle aria-hidden className="size-3.5" /> Desvio forçado em {LEVEL_LABEL[r.force_drift as keyof typeof LEVEL_LABEL]}
            </span>
          )}
        </span>
      </PageHeader>

      <Tabs value={view} onValueChange={(v) => setParams((p) => { p.set("view", v); return p; })}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <TabsList aria-label="Modo de visualização">
            <TabsTrigger value="matriz"><Grid3x3 aria-hidden /> Matriz 3×3</TabsTrigger>
            <TabsTrigger value="comparar"><Columns3 aria-hidden /> Comparar níveis</TabsTrigger>
          </TabsList>
          {view === "comparar" && (
            <Tabs value={format} onValueChange={(v) => { setFormat(v as Format); setParams((p) => { p.set("formato", v); return p; }); }}>
              <TabsList aria-label="Formato a comparar">
                {FORMATS.map((f) => <TabsTrigger key={f} value={f}>{FORMAT_LABEL[f]}</TabsTrigger>)}
              </TabsList>
            </Tabs>
          )}
        </div>
        <TabsContent value="matriz"><MatrixGrid results={r} docId={docId} /></TabsContent>
        <TabsContent value="comparar"><CompareLevels results={r} docId={docId} format={format} /></TabsContent>
      </Tabs>
    </>
  );
}
