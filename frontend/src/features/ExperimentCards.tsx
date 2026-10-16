import type { ExperimentResponse } from "@/api/types";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { metricInfo } from "@/lib/metrics";
import { cn, fmtNumber, fmtPct, fmtUsd } from "@/lib/utils";

const AGREEMENT_LABEL: Record<string, string> = {
  "nivel (percebido x previsto)": "Nível · revisora × classificador",
  "nivel (percebido x alvo)": "Nível · revisora × nível pedido",
  "erro factual": "Erro factual",
  trivializou: "Trivialização",
  "tom (erro absoluto médio, 1-5)": "Tom · erro médio do judge (1–5)",
};

/** Variância do avaliador e concordância com a revisão humana. */
export function ReliabilityCard({ e }: { e: ExperimentResponse }) {
  if (!e.variance?.length && !e.agreement?.length) return null;
  const variance = [...(e.variance ?? [])].sort((a, b) => b.desvio_medio - a.desvio_medio);
  const max = Math.max(0.0001, ...variance.map((v) => v.desvio_medio));
  return (
    <Card>
      <CardHeader>
        <span className="eyebrow">Confiabilidade do avaliador</span>
        <CardTitle>A mesma saída recebe a mesma nota?</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-6">
        {variance.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm text-ink-2">
              Desvio padrão médio entre {e.repeats ?? "—"} avaliações das mesmas 9 saídas (release do Itaú).
            </p>
            <ul className="flex flex-col gap-1.5">
              {variance.map((v) => (
                <li key={v.metric} className="grid grid-cols-[minmax(0,190px)_1fr_64px] items-center gap-3 text-sm">
                  <span className="truncate text-ink-2" title={v.metric}>{metricInfo(v.metric).label}</span>
                  <span className="h-2 rounded-sm bg-surface-2" aria-hidden>
                    <span
                      className={cn("block h-full rounded-sm", v.tipo === "deterministica" ? "bg-ok" : "bg-warn")}
                      style={{ width: `${Math.max(v.desvio_medio > 0 ? 3 : 0, (v.desvio_medio / max) * 100)}%` }}
                    />
                  </span>
                  <span className="text-right font-mono tabular">{fmtNumber(v.desvio_medio, 3)}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-ink-3">Verde: métrica determinística. Âmbar: métrica com LLM (temperatura 0).</p>
          </div>
        )}
        {e.agreement && e.agreement.length > 0 && (
          <div className="flex flex-col gap-2 border-t border-line pt-5">
            <span className="text-sm font-medium">Revisão humana às cegas</span>
            <table className="w-full text-sm">
              <tbody>
                {e.agreement.map((a) => {
                  const tone = a.dimensao.startsWith("tom");
                  return (
                    <tr key={a.dimensao} className="border-b border-line last:border-0">
                      <td className="py-2 text-ink-2">{AGREEMENT_LABEL[a.dimensao] ?? a.dimensao}</td>
                      <td className="py-2 text-right font-mono tabular">
                        {!a.n || a.concordancia == null ? <span className="text-ink-3">não avaliado</span>
                          : tone ? fmtNumber(a.concordancia, 2) : fmtPct(a.concordancia)}
                      </td>
                      <td className="w-24 py-2 text-right font-mono text-xs text-ink-3 tabular">
                        {a.kappa != null ? `κ ${fmtNumber(a.kappa, 2)}` : a.n ? `n = ${a.n}` : ""}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

/** Modelo barato × forte na geração, com e sem reflection loop. */
export function TradeoffsCard({ e }: { e: ExperimentResponse }) {
  if (!e.tradeoffs?.length) return null;
  const best = Math.max(...e.tradeoffs.map((t) => t.aprovacao));
  return (
    <Card>
      <CardHeader>
        <span className="eyebrow">Trade-offs</span>
        <CardTitle>Quanto custa cada configuração</CardTitle>
      </CardHeader>
      <CardBody className="flex flex-col gap-4">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink-2">
                <th scope="col" className="py-2 font-medium">Configuração</th>
                <th scope="col" className="py-2 text-right font-medium">Aprovação</th>
                <th scope="col" className="py-2 text-right font-medium">Fidelidade</th>
                <th scope="col" className="py-2 text-right font-medium">Tokens</th>
                <th scope="col" className="py-2 text-right font-medium">Custo</th>
                <th scope="col" className="py-2 text-right font-medium">Tempo</th>
              </tr>
            </thead>
            <tbody>
              {e.tradeoffs.map((t) => (
                <tr key={t.config} className={cn("border-b border-line last:border-0", t.aprovacao === best && best > 0 && "bg-ok-soft/60")}>
                  <td className="py-2">
                    <span className="font-medium">{t.config}</span>
                    <span className="block text-[11px] text-ink-3">{t.modelo_geracao.split(":").at(-1)}</span>
                  </td>
                  <td className="py-2 text-right font-mono tabular">{fmtPct(t.aprovacao)}</td>
                  <td className="py-2 text-right font-mono tabular">{t.fidelidade_media != null ? fmtPct(t.fidelidade_media) : "—"}</td>
                  <td className="py-2 text-right font-mono tabular">{t.tokens.toLocaleString("pt-BR")}</td>
                  <td className="py-2 text-right font-mono tabular">{fmtUsd(t.custo_usd)}</td>
                  <td className="py-2 text-right font-mono tabular">{fmtNumber(t.latencia_s, 0)} s{t.latencia_estimada ? "*" : ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-ink-3">
          Release do Itaú. Geração barata = execução do experimento; forte = adapters, formatters e refiner no modelo maior. Sem reflection = 1ª
          tentativa da mesma execução. * tempo estimado pelo caminho crítico.
        </p>
      </CardBody>
    </Card>
  );
}
