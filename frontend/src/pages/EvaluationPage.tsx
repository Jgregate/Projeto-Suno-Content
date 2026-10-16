import { Info } from "lucide-react";
import type { ReactNode } from "react";
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, ReferenceArea, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { useExperiment, useSummary, useThresholds } from "@/api/hooks";
import { ReliabilityCard, TradeoffsCard } from "@/features/ExperimentCards";
import type { Audience, CellMetrics, SummaryResponse, ThresholdsResponse } from "@/api/types";
import { PageHeader } from "@/components/AppShell";
import { LevelTag } from "@/components/LevelTag";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/States";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { LEVEL_LABEL, LEVEL_STYLE, LEVELS } from "@/lib/levels";
import { metricInfo } from "@/lib/metrics";
import { cn, fmtMs, fmtNumber, fmtPct, fmtUsd } from "@/lib/utils";

const SYSTEM_LABEL: Record<string, string> = { pipeline: "Pipeline", baseline: "Baseline ingênuo" };
const AXIS = { fontSize: 12, fill: "var(--ink-3)" };
const GRID = "var(--line)";

export function EvaluationPage() {
  const summary = useSummary();
  const thresholds = useThresholds();
  const experiment = useExperiment();

  if (summary.isLoading || thresholds.isLoading) return <LoadingBlock rows={4} />;
  if (summary.error) return <ErrorState error={summary.error} />;
  const s = { ...summary.data!, cells: summary.data!.cells ?? [], node_costs: summary.data!.node_costs ?? [] };
  if (!s.documents.length) {
    return (
      <>
        <PageHeader eyebrow="Telemetria do avaliador" title="Avaliação" />
        <EmptyState title="Ainda não há execuções para avaliar">Gere os conteúdos de um documento e volte aqui para ver as métricas agregadas.</EmptyState>
      </>
    );
  }
  return (
    <>
      <PageHeader eyebrow="Telemetria do avaliador" title="O pipeline acerta o nível de cada leitor?">
        {s.documents.length} {s.documents.length === 1 ? "documento" : "documentos"} · {s.cells.filter((c) => c.system === "pipeline").length} saídas do pipeline
        {s.cells.some((c) => c.system === "baseline") ? ` · ${s.cells.filter((c) => c.system === "baseline").length} do baseline` : ""}
      </PageHeader>
      {s.notes.map((n) => (
        <p key={n} className="mb-6 flex items-center gap-2 rounded-lg bg-surface-2 px-4 py-3 text-sm text-ink-2"><Info aria-hidden className="size-4" />{n}</p>
      ))}
      <div className="flex flex-col gap-8">
        <Kpis s={s} />
        <div className="grid gap-8 xl:grid-cols-2">
          {Object.entries(s.confusion).sort(([a], [b]) => (a === "pipeline" ? -1 : b === "pipeline" ? 1 : 0)).map(([system, m]) => (
            <Card key={system}>
              <CardHeader>
                <span className="eyebrow">Matriz de confusão de níveis</span>
                <CardTitle>{SYSTEM_LABEL[system] ?? system}</CardTitle>
              </CardHeader>
              <CardBody><Heatmap labels={m.labels as Audience[]} matrix={m.matrix} /></CardBody>
            </Card>
          ))}
        </div>
        <Card>
          <CardHeader>
            <span className="eyebrow">Distribuição por nível</span>
            <CardTitle>Cada ponto é uma saída; a faixa sombreada é o limiar do nível</CardTitle>
          </CardHeader>
          <CardBody className="grid gap-6 xl:grid-cols-3">
            {["flesch_pt", "term_density", "term_context_pct"].map((m) => (
              <Distribution key={m} metric={m} cells={s.cells} thresholds={thresholds.data} />
            ))}
          </CardBody>
        </Card>
        <div className="grid gap-8 xl:grid-cols-[3fr_2fr]">
          <BaselineVsPipeline s={s} />
          <ReflectionCard s={s} />
        </div>
        {experiment.data && (experiment.data.variance?.length || experiment.data.tradeoffs?.length) ? (
          <div className="grid gap-8 xl:grid-cols-2">
            <ReliabilityCard e={experiment.data} />
            <TradeoffsCard e={experiment.data} />
          </div>
        ) : null}
        <NodeCosts s={s} />
      </div>
    </>
  );
}

function Kpi({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-xl border border-line bg-surface p-5">
      <span className="eyebrow">{label}</span>
      <span className="font-serif text-3xl font-semibold tabular">{value}</span>
      {sub && <span className="text-sm text-ink-2">{sub}</span>}
    </div>
  );
}

type Summary = SummaryResponse & { cells: CellMetrics[]; node_costs: NonNullable<SummaryResponse["node_costs"]> };

function Kpis({ s }: { s: Summary }) {
  const r = s.reflection;
  const avg = (f: (x: (typeof r)[number]) => number) => (r.length ? r.reduce((a, x) => a + f(x), 0) / r.length : 0);
  const accuracy = (system: string) => {
    const cs = s.cells.filter((c) => c.system === system && c.predicted_level);
    return cs.length ? cs.filter((c) => c.predicted_level === c.audience).length / cs.length : null;
  };
  const accP = accuracy("pipeline");
  const accB = accuracy("baseline");
  return (
    <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <Kpi label="Aprovação" value={fmtPct(s.pass_rate_by_system.pipeline ?? 0)} sub={s.pass_rate_by_system.baseline != null ? `baseline: ${fmtPct(s.pass_rate_by_system.baseline)}` : "pipeline"} />
      <Kpi label="Nível acertado" value={accP != null ? fmtPct(accP) : "—"} sub={accB != null ? `baseline: ${fmtPct(accB)}` : "pelas métricas determinísticas"} />
      <Kpi label="Aprovação antes → depois do loop" value={`${fmtNumber(avg((x) => x.pct_approved_first), 0)}% → ${fmtNumber(avg((x) => x.pct_approved_final), 0)}%`} sub={`${fmtNumber(avg((x) => x.mean_attempts), 2)} tentativas em média`} />
      <Kpi label="Custo extra do loop" value={`${fmtNumber(r.reduce((a, x) => a + x.extra_tokens, 0) / 1000, 1)} mil tokens`} sub={`${r.reduce((a, x) => a + x.extra_llm_calls, 0)} chamadas · ${fmtUsd(r.reduce((a, x) => a + x.extra_cost_usd, 0))}`} />
    </div>
  );
}

function Heatmap({ labels, matrix }: { labels: Audience[]; matrix: number[][] }) {
  const max = Math.max(1, ...matrix.flat());
  const total = matrix.flat().reduce((a, b) => a + b, 0);
  const hits = labels.reduce((a, _, i) => a + matrix[i][i], 0);
  return (
    <div className="flex flex-col gap-3">
      <table className="w-full border-separate border-spacing-1 text-sm" aria-label="Linhas: nível alvo. Colunas: nível previsto.">
        <thead>
          <tr>
            <th className="w-36 text-left text-xs font-normal text-ink-3">alvo ↓ · previsto →</th>
            {labels.map((l) => <th key={l} scope="col" className="pb-1 text-xs font-medium text-ink-2">{LEVEL_LABEL[l]}</th>)}
          </tr>
        </thead>
        <tbody>
          {labels.map((row, i) => (
            <tr key={row}>
              <th scope="row" className="text-left"><LevelTag level={row} /></th>
              {labels.map((col, j) => {
                const v = matrix[i][j];
                const diag = i === j;
                return (
                  <td
                    key={col}
                    className={cn("h-16 rounded-md text-center font-mono text-lg font-medium tabular", diag ? "ring-1 ring-ok/40" : "")}
                    style={{ background: v ? `color-mix(in oklab, ${diag ? "var(--ok)" : "var(--bad)"} ${18 + (v / max) * 52}%, var(--surface))` : "var(--surface-2)" }}
                    aria-label={`alvo ${LEVEL_LABEL[row]}, previsto ${LEVEL_LABEL[col]}: ${v}`}
                  >
                    {v}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-sm text-ink-2">
        <strong className="font-semibold text-ink">{hits} de {total}</strong> saídas caíram no nível certo pela legibilidade e densidade. Fora da diagonal = desvio de nível.
      </p>
    </div>
  );
}

function Distribution({ metric, cells, thresholds }: { metric: string; cells: CellMetrics[]; thresholds?: ThresholdsResponse }) {
  const info = metricInfo(metric);
  const points = (system: string) =>
    cells
      .filter((c) => c.system === system && c.metrics[metric] != null)
      .map((c, k) => ({ x: LEVELS.indexOf(c.audience) + ((k % 5) - 2) * 0.06, y: c.metrics[metric], level: c.audience }));
  const pipeline = points("pipeline");
  const baseline = points("baseline");
  const values = [...pipeline, ...baseline].map((p) => p.y);
  const step = info.domain[1] > 20 ? 20 : 3;
  const lo = Math.min(info.domain[0], Math.floor(Math.min(...values, info.domain[0]) / step) * step);
  const hi = Math.max(info.domain[1], Math.ceil(Math.max(...values, info.domain[1]) / step) * step);
  const ticks = Array.from({ length: Math.round((hi - lo) / step) + 1 }, (_, i) => lo + i * step);
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="text-sm font-medium">{info.label}</figcaption>
      <div className="h-64">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            {LEVELS.map((l, i) => {
              const b = thresholds?.levels[l]?.[metric];
              if (!b || (b.min == null && b.max == null)) return null;
              return <ReferenceArea key={l} x1={i - 0.42} x2={i + 0.42} y1={b.min ?? lo} y2={b.max ?? hi} fill={LEVEL_STYLE[l].cssVar} fillOpacity={0.1} stroke={LEVEL_STYLE[l].cssVar} strokeOpacity={0.4} strokeDasharray="3 3" />;
            })}
            <XAxis type="number" dataKey="x" domain={[-0.5, 2.5]} ticks={[0, 1, 2]} tickFormatter={(v) => LEVEL_LABEL[LEVELS[v]] ?? ""} tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
            <YAxis type="number" dataKey="y" domain={[lo, hi]} ticks={ticks} tick={AXIS} axisLine={false} tickLine={false} />
            <ZAxis range={[70, 70]} />
            <Tooltip cursor={false} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8 }} formatter={(v) => fmtNumber(Number(v), 1)} labelFormatter={() => ""} />
            <Scatter name="Pipeline" data={pipeline}>
              {pipeline.map((p, i) => <Cell key={i} fill={LEVEL_STYLE[p.level].cssVar} />)}
            </Scatter>
            {baseline.length > 0 && (
              <Scatter name="Baseline" data={baseline} shape="cross">
                {baseline.map((_, i) => <Cell key={i} fill="var(--ink-3)" />)}
              </Scatter>
            )}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-ink-3">Círculos: pipeline (cor do nível). Cruzes: baseline. {info.help}</p>
    </figure>
  );
}

function BaselineVsPipeline({ s }: { s: Summary }) {
  const data = LEVELS.map((l) => {
    const row: Record<string, number | string> = { level: LEVEL_LABEL[l] };
    for (const sys of ["pipeline", "baseline"]) {
      const ls = s.levels.find((x) => x.system === sys && x.audience === l);
      if (ls) row[sys] = Math.round(ls.pass_rate * 100);
    }
    return row;
  });
  const hasBaseline = s.levels.some((l) => l.system === "baseline");
  return (
    <Card>
      <CardHeader>
        <span className="eyebrow">Baseline × pipeline</span>
        <CardTitle>Taxa de aprovação por nível</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-6">
        <div className="h-60">
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="level" tick={AXIS} axisLine={{ stroke: GRID }} tickLine={false} />
              <YAxis domain={[0, 100]} unit="%" tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "var(--surface-2)" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8 }} formatter={(v) => `${v}%`} />
              <Legend formatter={(v) => SYSTEM_LABEL[v] ?? v} />
              <Bar dataKey="pipeline" fill="var(--brand)" radius={[4, 4, 0, 0]} />
              {hasBaseline && <Bar dataKey="baseline" fill="var(--line-strong)" radius={[4, 4, 0, 0]} />}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-2">
              <th scope="col" className="py-2 font-medium">Nível</th>
              <th scope="col" className="py-2 font-medium">Sistema</th>
              <th scope="col" className="py-2 text-right font-medium">Flesch médio</th>
              <th scope="col" className="py-2 text-right font-medium">Densidade média</th>
              <th scope="col" className="py-2 text-right font-medium">Aprovação</th>
            </tr>
          </thead>
          <tbody>
            {LEVELS.flatMap((l) =>
              s.levels.filter((x) => x.audience === l).map((x) => (
                <tr key={`${l}-${x.system}`} className="border-b border-line last:border-0">
                  <td className="py-2"><LevelTag level={l} /></td>
                  <td className="py-2">{SYSTEM_LABEL[x.system] ?? x.system}</td>
                  <td className="py-2 text-right font-mono tabular">{x.flesch_mean != null ? fmtNumber(x.flesch_mean) : "—"}</td>
                  <td className="py-2 text-right font-mono tabular">{x.density_mean != null ? fmtNumber(x.density_mean) : "—"}</td>
                  <td className="py-2 text-right font-mono tabular">{fmtPct(x.pass_rate)}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

function ReflectionCard({ s }: { s: Summary }) {
  return (
    <Card>
      <CardHeader>
        <span className="eyebrow">Reflection loop</span>
        <CardTitle>Aprovação antes e depois da correção</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-5">
        {s.reflection.map((r) => (
          <div key={r.doc_id} className="flex flex-col gap-3">
            <span className="truncate text-xs text-ink-3">{r.doc_id}</span>
            {[["1ª tentativa", r.pct_approved_first, "var(--line-strong)"], ["Depois do loop", r.pct_approved_final, "var(--ok)"]].map(([label, v, color]) => (
              <div key={label as string} className="grid grid-cols-[110px_1fr_48px] items-center gap-3 text-sm">
                <span className="text-ink-2">{label}</span>
                <div className="h-3 rounded-full bg-surface-2" aria-hidden>
                  <div className="h-full rounded-full" style={{ width: `${v}%`, background: color as string }} />
                </div>
                <span className="text-right font-mono tabular">{fmtNumber(v as number, 0)}%</span>
              </div>
            ))}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
              <dt className="text-ink-3">Células refinadas</dt><dd className="text-right font-mono tabular">{r.refined_cells} de {r.cells}</dd>
              <dt className="text-ink-3">Tentativas médias</dt><dd className="text-right font-mono tabular">{fmtNumber(r.mean_attempts, 2)}</dd>
              <dt className="text-ink-3">Pararam por estagnação</dt><dd className="text-right font-mono tabular">{r.stagnated}</dd>
              <dt className="text-ink-3">Regressões detectadas</dt><dd className="text-right font-mono tabular">{r.regressions}</dd>
              <dt className="text-ink-3">Custo extra</dt><dd className="text-right font-mono tabular">{r.extra_llm_calls} chamadas · {fmtNumber(r.extra_latency_s, 1)} s</dd>
            </dl>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

const NODE_LABEL: Record<string, string> = {
  extractor: "Extração",
  adapter: "Adaptação (3 níveis)",
  formatter: "Formatos (9)",
  refiner: "Refinamento",
  "evaluator:deterministic": "Avaliação determinística",
  "evaluator:claims": "Avaliação · afirmações (LLM)",
  "evaluator:judge": "Avaliação · judge (LLM)",
};

function NodeCosts({ s }: { s: Summary }) {
  const data = s.node_costs.map((n) => ({ ...n, label: NODE_LABEL[n.node] ?? n.node, tokens: n.input_tokens + n.output_tokens }));
  return (
    <Card>
      <CardHeader>
        <span className="eyebrow">Custo e latência por nó</span>
        <CardTitle>Onde vai o tempo e o token</CardTitle>
      </CardHeader>
      <CardBody className="grid gap-8 xl:grid-cols-2">
        <div className="h-72">
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 24 }}>
              <CartesianGrid stroke={GRID} horizontal={false} />
              <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} tickFormatter={(v) => fmtMs(Number(v))} />
              <YAxis type="category" dataKey="label" width={170} tick={AXIS} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: "var(--surface-2)" }} contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8 }} formatter={(v) => fmtMs(Number(v))} />
              <Bar dataKey="latency_ms" name="Latência somada" fill="var(--ink-2)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <table className="w-full self-start text-sm">
          <thead>
            <tr className="border-b border-line text-left text-ink-2">
              <th scope="col" className="py-2 font-medium">Nó</th>
              <th scope="col" className="py-2 text-right font-medium">Chamadas LLM</th>
              <th scope="col" className="py-2 text-right font-medium">Tokens</th>
              <th scope="col" className="py-2 text-right font-medium">Custo</th>
              <th scope="col" className="py-2 text-right font-medium">Latência</th>
            </tr>
          </thead>
          <tbody>
            {data.map((n) => (
              <tr key={n.node} className="border-b border-line last:border-0">
                <td className="py-2">{n.label}</td>
                <td className="py-2 text-right font-mono tabular">{n.llm_calls}</td>
                <td className="py-2 text-right font-mono tabular">{n.tokens.toLocaleString("pt-BR")}</td>
                <td className="py-2 text-right font-mono tabular">{fmtUsd(n.cost_usd)}</td>
                <td className="py-2 text-right font-mono tabular">{fmtMs(n.latency_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-ink-3 xl:col-span-2">Latência somada por chamada; nós em paralelo se sobrepõem no tempo real. Custo usa backend/model_prices.yaml (US$ 0 se não preenchido).</p>
      </CardBody>
    </Card>
  );
}
