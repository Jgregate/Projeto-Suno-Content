import { ArrowRight, CheckCircle2, ChevronDown, FileUp, Loader2, Play, XCircle } from "lucide-react";
import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { Link, useNavigate } from "react-router";
import { useDocuments, useRunStatus, useStartRun, useUpload } from "@/api/hooks";
import type { Audience, DocumentInfo, RunStatus } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { LEVEL_LABEL, LEVELS } from "@/lib/levels";
import { cn } from "@/lib/utils";

const DOC_TYPE: Record<string, string> = {
  ata_copom: "Ata do Copom",
  fato_relevante: "Fato relevante",
  release_resultados: "Release de resultados",
  outro: "Documento",
};

export function DocumentsPage() {
  const docs = useDocuments();
  return (
    <>
      <PageHeader eyebrow="Documentos-fonte" title="Do documento denso ao conteúdo certo para cada leitor">
        Envie uma ata do Copom, um fato relevante ou um release. O pipeline extrai os fatos, escreve para três níveis em três
        formatos e só entrega o que passa no avaliador.
      </PageHeader>
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_360px]">
        <section aria-labelledby="lista" className="flex flex-col gap-4">
          <h2 id="lista" className="eyebrow">Documentos processados</h2>
          {docs.isLoading && <LoadingBlock rows={2} />}
          {docs.error && <ErrorState error={docs.error} action={<Button variant="secondary" onClick={() => docs.refetch()}>Tentar de novo</Button>} />}
          {docs.data?.length === 0 && (
            <EmptyState title="Nenhum documento ainda">
              Envie um PDF ao lado. Depois da leitura, ele aparece aqui pronto para gerar os conteúdos.
            </EmptyState>
          )}
          {docs.data?.map((d) => <DocumentRow key={d.id} doc={d} />)}
        </section>
        <UploadBox />
      </div>
    </>
  );
}

function UploadBox() {
  const upload = useUpload();
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const send = (file?: File | null) => {
    if (file) upload.mutate(file);
  };
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    send(e.dataTransfer.files?.[0]);
  };

  return (
    <section aria-labelledby="enviar" className="flex flex-col gap-4">
      <h2 id="enviar" className="eyebrow">Enviar PDF</h2>
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging ? "border-focus bg-surface" : "border-line-strong bg-surface hover:border-ink-3",
        )}
      >
        {upload.isPending ? <Loader2 aria-hidden className="size-7 animate-spin text-ink-2" /> : <FileUp aria-hidden className="size-7 text-ink-2" />}
        <span className="font-medium">{upload.isPending ? "Lendo o PDF…" : "Arraste o PDF aqui ou clique para escolher"}</span>
        <span className="text-xs text-ink-3">Atas do Copom, fatos relevantes e releases em PDF com texto (não escaneado).</span>
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          onChange={(e) => {
            send(e.target.files?.[0]);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </label>
      <div aria-live="polite" className="text-sm">
        {upload.isSuccess && (
          <p className="flex items-center gap-2 text-ok">
            <CheckCircle2 aria-hidden className="size-4" /> “{upload.data.title}” lido: {upload.data.pages} páginas.
          </p>
        )}
        {upload.error && (
          <p className="flex items-start gap-2 text-bad">
            <XCircle aria-hidden className="mt-0.5 size-4 shrink-0" /> {upload.error.message}
          </p>
        )}
      </div>
    </section>
  );
}

function DocumentRow({ doc }: { doc: DocumentInfo }) {
  const start = useStartRun();
  const [runId, setRunId] = useState<string | null>(null);
  const [drift, setDrift] = useState(false);
  const [driftLevel, setDriftLevel] = useState<Audience>("iniciante");
  const [force, setForce] = useState(false);
  const status = useRunStatus(runId);
  const navigate = useNavigate();
  const ids = { drift: useId(), level: useId(), force: useId() };

  useEffect(() => {
    if (status.data?.status === "completed" && runId) navigate(`/docs/${encodeURIComponent(doc.id)}?run=${encodeURIComponent(runId)}`);
  }, [status.data?.status, runId, doc.id, navigate]);

  const generate = () =>
    start.mutate(
      { doc_id: doc.id, force, force_drift: drift ? driftLevel : null },
      { onSuccess: (r) => setRunId(r.run_id) },
    );
  const running = start.isPending || (!!runId && !["completed", "failed"].includes(status.data?.status ?? ""));

  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <span className="eyebrow">
            {DOC_TYPE[doc.doc_type] ?? "Documento"}
            {doc.date && ` · ${new Date(`${doc.date}T12:00:00`).toLocaleDateString("pt-BR")}`} · {doc.pages} páginas
          </span>
          <h3 className="font-serif text-xl font-semibold leading-snug">{doc.title}</h3>
          <span className="text-sm text-ink-3">
            {doc.runs ? `${doc.runs} ${doc.runs === 1 ? "execução salva" : "execuções salvas"}` : "Ainda sem conteúdos gerados"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {doc.runs > 0 && (
            <Button asChild variant="secondary">
              <Link to={`/docs/${encodeURIComponent(doc.id)}`}>
                Abrir matriz <ArrowRight aria-hidden />
              </Link>
            </Button>
          )}
          <Button onClick={generate} disabled={running}>
            {running ? <Loader2 aria-hidden className="animate-spin" /> : <Play aria-hidden />}
            {running ? "Gerando…" : "Gerar conteúdos"}
          </Button>
        </div>
      </div>

      <details className="group rounded-lg border border-line bg-surface-2/50 px-4 py-3">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-ink-2">
          <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          Opções avançadas
        </summary>
        <div className="mt-4 flex flex-col gap-4 text-sm">
          <div className="flex flex-wrap items-center gap-3">
            <Switch id={ids.drift} checked={drift} onCheckedChange={setDrift} />
            <label htmlFor={ids.drift} className="font-medium">Forçar desvio de nível</label>
            <label htmlFor={ids.level} className="sr-only">Nível que recebe o desvio</label>
            <select
              id={ids.level}
              value={driftLevel}
              disabled={!drift}
              onChange={(e) => setDriftLevel(e.target.value as Audience)}
              className="h-8 rounded-md border border-line-strong bg-surface px-2 disabled:opacity-50"
            >
              {LEVELS.filter((l) => l !== "avancado").map((l) => (
                <option key={l} value={l}>{LEVEL_LABEL[l]}</option>
              ))}
            </select>
            <span className="text-ink-3">Gera o nível escolhido com as regras do Avançado na 1ª tentativa, para mostrar o loop corrigindo.</span>
          </div>
          <div className="flex items-center gap-3">
            <Switch id={ids.force} checked={force} onCheckedChange={setForce} />
            <label htmlFor={ids.force} className="font-medium">Gerar de novo, ignorando o cache</label>
            <span className="text-ink-3">Chama o LLM e tem custo. Sem isso, a última execução salva é reaproveitada.</span>
          </div>
        </div>
      </details>

      {(runId || start.error) && <RunProgress status={status.data} error={start.error ?? status.error} />}
    </Card>
  );
}

const STAGES: { key: string; label: string }[] = [
  { key: "extractor", label: "Extração" },
  { key: "adapters", label: "Adaptação" },
  { key: "formatters", label: "Formatos" },
  { key: "evaluator", label: "Avaliação" },
  { key: "refiner", label: "Refinamento" },
];

export function RunProgress({ status, error }: { status?: RunStatus; error?: Error | null }) {
  if (error) return <p role="alert" className="text-sm text-bad">{error.message}</p>;
  if (!status) return <p className="text-sm text-ink-3">Iniciando…</p>;
  const done = status.status === "completed";
  return (
    <div className="flex flex-col gap-3" aria-live="polite">
      <ol className="grid grid-cols-5 gap-2">
        {STAGES.map(({ key, label }) => {
          const p = status.progress[key] ?? { done: 0, total: null };
          const complete = done || (p.total != null ? p.done >= p.total : false);
          const active = !complete && p.done > 0;
          return (
            <li key={key} className="flex flex-col gap-1.5">
              <div className={cn("h-1.5 rounded-full", complete ? "bg-ok" : active ? "animate-pulse bg-ink-2" : "bg-surface-2")} />
              <span className={cn("text-xs", complete ? "text-ink" : "text-ink-3")}>
                {label}
                <span className="ml-1 font-mono tabular">
                  {p.total != null ? `${p.done}/${p.total}` : p.done ? `${p.done}×` : ""}
                </span>
              </span>
            </li>
          );
        })}
      </ol>
      <p className="text-sm text-ink-2">
        {status.status === "failed" && <span className="text-bad">A execução falhou: {status.error}</span>}
        {status.status === "completed" && (status.cached ? "Execução em cache carregada, sem custo de LLM. Abrindo a matriz…" : "Concluído. Abrindo a matriz…")}
        {(status.status === "queued" || status.status === "running") && "Gerando e avaliando os 9 conteúdos…"}
      </p>
    </div>
  );
}
