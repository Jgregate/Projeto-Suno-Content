import { ArrowRight, ArrowUpRight } from "lucide-react";
import { type CSSProperties, type ReactNode, useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { useExperiment, useSummary } from "@/api/hooks";
import { Logo } from "@/components/AppShell";
import { SiteFooter } from "@/components/SiteFooter";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { FORMAT_LABEL, FORMATS, LEVEL_HINT, LEVEL_LABEL, LEVEL_STYLE, LEVELS } from "@/lib/levels";
import { cn, fmtPct, fmtUsd } from "@/lib/utils";

/** Rótulo pequeno em caixa-alta, no padrão do restante do painel. */
const LABEL = "text-[11px] font-extrabold uppercase tracking-[0.1em]";

const SPEC: [string, string][] = [
  ["entrada", "PDF público · BCB, CVM, RI"],
  ["saída", "3 níveis × 3 formatos = 9 conteúdos"],
  ["grafo", "LangGraph · 1 → 3 → 9, com estado"],
  ["avaliador", "4 métricas determinísticas + 2 com LLM"],
  ["correção", "até 3 tentativas · parada por estagnação"],
  ["rastreio", "toda afirmação cita uma âncora da fonte"],
];

const STAGES = [
  { id: "01", name: "Extractor & Anchor", out: "âncoras A01…An", text: "Lê o documento e extrai números-chave e declarações factuais. Cada âncora é validada contra o texto da fonte." },
  { id: "02", name: "Audience adapters", out: "× 3 em paralelo", text: "Reescrevem as âncoras para Iniciante, Intermediário e Avançado, com o glossário e as regras de cada nível." },
  { id: "03", name: "Format synthesizers", out: "× 9 em paralelo", text: "Montam o artigo, o carrossel (gancho, corpo, conclusão) e o roteiro de até 60 s, com schema validado." },
  { id: "04", name: "Avaliador híbrido", out: "relatório por saída", text: "Mede legibilidade, densidade de jargão, contextualização e números; depois afirmações e rubrica com LLM." },
  { id: "05", name: "Refiner", out: "só as reprovadas", text: "Recebe o relatório de falha com os números e reescreve. A nova versão volta para o avaliador." },
];

const METRICS: [string, string, string][] = [
  ["Flesch PT-BR", "determinística", "248,835 − 1,015 · palavras/frase − 84,6 · sílabas/palavra"],
  ["Densidade de termos", "determinística", "termos do glossário por 100 palavras, por lema (spaCy)"],
  ["Contextualização", "determinística", "% do jargão explicado na frase, na anterior ou na seguinte"],
  ["Grounding numérico", "determinística", "números sem correspondência na fonte, com arredondamento e unidade"],
  ["Fidelidade por afirmações", "LLM · temp. 0", "cada afirmação contra as âncoras; contradição reprova"],
  ["Judge com rubrica", "LLM · temp. 0", "4 critérios de 1 a 5, cada nota com trecho literal como evidência"],
];

const FORMAT_SPEC: Record<string, string> = {
  texto: "título, subtítulo, seções",
  carrossel: "gancho → corpo → conclusão",
  roteiro: "blocos com tempo · fala ≤ 60 s",
};

// --- movimento ---

/** true quando o elemento entra na tela (uma vez só). */
function useInView<T extends Element>(threshold = 0.15) {
  const ref = useRef<T>(null);
  // sem IntersectionObserver (navegadores antigos), tudo já começa visível
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === "undefined");
  useEffect(() => {
    const el = ref.current;
    if (!el || visible) return;
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true);
        io.disconnect();
      }
    }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold, visible]);
  return { ref, visible };
}

const delay = (ms: number) => ({ "--d": `${ms}ms` }) as CSSProperties;

/** Sobe e aparece ao entrar na tela; `delay` escalona itens vizinhos. */
function Reveal({ children, className, delayMs = 0 }: { children: ReactNode; className?: string; delayMs?: number }) {
  const { ref, visible } = useInView<HTMLDivElement>();
  return (
    <div ref={ref} className={cn("reveal", visible && "is-visible", className)} style={delay(delayMs)}>
      {children}
    </div>
  );
}

/** Conta de 0 até o número do texto (mantém prefixo, sufixo e casas decimais no formato pt-BR). */
function CountUp({ value }: { value: string }) {
  const { ref, visible } = useInView<HTMLSpanElement>(0.4);
  const match = value.match(/^(\D*)([\d.]*\d(?:,\d+)?)(.*)$/);
  const target = match ? Number(match[2].replace(/\./g, "").replace(",", ".")) : NaN;
  const decimals = match?.[2].includes(",") ? match[2].split(",")[1].length : 0;
  const [shown, setShown] = useState(Number.isNaN(target) ? value : `${match![1]}0${match![3]}`);
  useEffect(() => {
    if (!visible || Number.isNaN(target)) return;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / 1100);
      const eased = 1 - (1 - t) ** 3;
      const n = (target * eased).toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
      setShown(`${match![1]}${n}${match![3]}`);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, value]);
  return <span ref={ref}>{shown}</span>;
}

/** Linha vermelha no topo da página indicando o quanto já foi rolado. */
function ScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setP(max > 0 ? window.scrollY / max : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
  return <div aria-hidden className="fixed inset-x-0 top-0 z-40 h-[3px] origin-left bg-brand" style={{ transform: `scaleX(${p})` }} />;
}

// --- seções ---

function Section({ id, index, title, children, className }: { id?: string; index: string; title: string; children: ReactNode; className?: string }) {
  return (
    <section id={id} className={cn("scroll-mt-16 border-t border-line", className)}>
      <div className="mx-auto grid max-w-[1320px] gap-10 px-8 py-20 lg:grid-cols-[220px_1fr]">
        <Reveal className="flex flex-col gap-2 lg:sticky lg:top-24 lg:self-start">
          <span className={cn(LABEL, "text-brand")}>{index}</span>
          <h2 className="text-2xl font-bold leading-tight tracking-tight">{title}</h2>
        </Reveal>
        <div>{children}</div>
      </div>
    </section>
  );
}

function LiveNumbers() {
  const summary = useSummary();
  const experiment = useExperiment();
  const s = summary.data;
  if (!s || !s.documents.length) return null;
  const cells = s.cells ?? [];
  const acc = (system: string) => {
    const cs = cells.filter((c) => c.system === system && c.predicted_level);
    return cs.length ? cs.filter((c) => c.predicted_level === c.audience).length / cs.length : null;
  };
  const pipeline = cells.filter((c) => c.system === "pipeline").length;
  const target = experiment.data?.agreement?.find((a) => a.dimensao === "nivel (percebido x alvo)");
  const costs = (s.node_costs ?? []).reduce((a, n) => a + n.cost_usd, 0);
  const items: [string, string, string][] = [
    ["fontes", String(s.documents.length), "Copom, fato relevante, release"],
    ["saídas avaliadas", String(pipeline), "pipeline, mais o mesmo tanto do baseline"],
    ["aprovação", fmtPct(s.pass_rate_by_system.pipeline ?? 0), `baseline ${fmtPct(s.pass_rate_by_system.baseline ?? 0)}`],
    ["nível pelo classificador", acc("pipeline") != null ? fmtPct(acc("pipeline")!) : "—", `baseline ${acc("baseline") != null ? fmtPct(acc("baseline")!) : "—"}`],
    ["nível pela revisora", target?.concordancia != null ? fmtPct(target.concordancia) : "—", "revisão humana às cegas"],
    ["custo por fonte", fmtUsd(costs / s.documents.length), "geração + avaliação + loop"],
  ];
  return (
    <div className="border-t border-line bg-surface">
      <div className="mx-auto max-w-[1320px] px-8 py-6">
        <div className={cn(LABEL, "mb-4 flex items-center justify-between text-ink-3")}>
          <span>experimento {experiment.data?.date ?? ""} · dados reais da API</span>
          <Link to="/avaliacao" className="nudge inline-flex items-center gap-1 hover:text-brand">telemetria completa <ArrowUpRight className="size-3.5" /></Link>
        </div>
        <dl className="grid grid-cols-2 border-l border-line md:grid-cols-3 xl:grid-cols-6">
          {items.map(([label, value, sub], i) => (
            <Reveal key={label} delayMs={i * 80} className="lift flex flex-col gap-1 border-r border-b border-line bg-surface px-4 py-4 xl:border-b-0">
              <dt className={cn(LABEL, "text-ink-3")}>{label}</dt>
              <dd className="text-2xl font-bold tabular"><CountUp value={value} /></dd>
              <dd className="text-xs text-ink-3">{sub}</dd>
            </Reveal>
          ))}
        </dl>
      </div>
    </div>
  );
}

function Pipeline() {
  const { ref, visible } = useInView<HTMLDivElement>(0.25);
  return (
    <div ref={ref} className={cn("flex flex-col gap-6", visible && "is-visible")}>
      <ol className="grid gap-px rounded-lg border border-line bg-line md:grid-cols-5">
        {STAGES.map((s, i) => (
          <li
            key={s.id}
            className={cn("stage-bar reveal lift relative flex flex-col gap-3 bg-surface p-5", visible && "is-visible", i >= 3 && "bg-surface-2")}
            style={delay(i * 140)}
          >
            <div className={cn(LABEL, "flex items-center justify-between text-ink-3")}>
              <span className="text-brand">{s.id}</span>
              <span className="normal-case tracking-normal">{s.out}</span>
            </div>
            <span className="text-[15px] font-bold leading-snug">{s.name}</span>
            <p className="text-sm leading-relaxed text-ink-2">{s.text}</p>
            {i < STAGES.length - 1 && (
              <ArrowRight aria-hidden className="absolute -right-2.5 top-1/2 z-10 hidden size-5 -translate-y-1/2 rounded-full border border-line bg-surface p-0.5 text-brand md:block" />
            )}
          </li>
        ))}
      </ol>
      {/* laço de correção entre o avaliador (04) e o refiner (05) */}
      <div className="grid md:grid-cols-5">
        <div className="md:col-span-3" />
        <div className={cn("reveal md:col-span-2", visible && "is-visible")} style={delay(800)}>
          <svg viewBox="0 0 200 28" preserveAspectRatio="none" className="h-7 w-full" aria-hidden>
            <path d="M20 0 V18 Q20 24 26 24 H174 Q180 24 180 18 V0" fill="none" stroke="var(--brand)" strokeWidth="1.5"
                  strokeDasharray="6 6" vectorEffect="non-scaling-stroke" className="flow-dash" />
          </svg>
          <p className="mt-2 text-xs leading-relaxed text-ink-2">
            <strong className="text-ink">reprovou</strong> → relatório com os números da falha → nova tentativa
            <br />
            <span className="text-ink-3">máx. 3 · para se a nota agregada subir menos de 0,01 · entrega a melhor versão</span>
          </p>
        </div>
      </div>
    </div>
  );
}

function Matrix() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr>
            <th className={cn(LABEL, "w-56 border-b border-line py-3 text-left text-ink-3")}>nível ↓ formato →</th>
            {FORMATS.map((f) => (
              <th key={f} scope="col" className="border-b border-line px-4 py-3 text-left">
                <span className="block font-bold">{FORMAT_LABEL[f]}</span>
                <span className="text-xs font-normal text-ink-3">{FORMAT_SPEC[f]}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {LEVELS.map((l, r) => (
            <tr key={l}>
              <th scope="row" className="border-b border-line py-4 pr-4 text-left align-top">
                <span className={cn("block font-bold", LEVEL_STYLE[l].text)}>{LEVEL_LABEL[l]}</span>
                <span className="text-xs font-normal text-ink-3">{LEVEL_HINT[l]}</span>
              </th>
              {FORMATS.map((f, c) => (
                <td key={f} className="border-b border-l border-line p-0 align-top">
                  <Reveal delayMs={(r * 3 + c) * 70} className="px-4 py-4 transition-colors hover:bg-surface">
                    <span className={cn("inline-block size-2 rounded-full align-middle", LEVEL_STYLE[l].bg)} aria-hidden />
                    <span className="ml-2 text-xs text-ink-2">{LEVEL_LABEL[l]} · {FORMAT_LABEL[f]}</span>
                  </Reveal>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PrimaryCta({ children, pulse = false }: { children: ReactNode; pulse?: boolean }) {
  return (
    <Button asChild className={cn("btn-shine nudge", pulse && "btn-pulse")}>
      <Link to="/documentos">{children} <ArrowRight /></Link>
    </Button>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-dvh bg-paper">
      <ScrollProgress />
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1320px] items-center gap-8 px-8">
          <Logo />
          <nav aria-label="Seções" className={cn(LABEL, "hidden items-center gap-6 text-ink-3 md:flex")}>
            <a href="#como-funciona" className="transition-colors hover:text-brand">Como funciona</a>
            <a href="#metricas" className="transition-colors hover:text-brand">Métricas</a>
            <Link to="/avaliacao" className="transition-colors hover:text-brand">Avaliação</Link>
          </nav>
          <div className="ml-auto flex items-center gap-3">
            <ThemeToggle />
            <Button asChild size="sm" className="btn-shine nudge"><Link to="/documentos">Abrir painel <ArrowRight /></Link></Button>
          </div>
        </div>
      </header>

      <main id="conteudo">
        <section
          className="grid-drift relative"
          style={{
            backgroundImage: "linear-gradient(var(--line) 1px, transparent 1px), linear-gradient(90deg, var(--line) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            backgroundPosition: "-1px -1px",
          }}
        >
          <div className="absolute inset-0 bg-gradient-to-b from-paper/40 via-paper/80 to-paper" aria-hidden />
          <div className="relative mx-auto grid max-w-[1320px] gap-12 px-8 pb-20 pt-20 lg:grid-cols-[1.25fr_1fr] lg:items-end">
            <div className="flex flex-col gap-7">
              <span className={cn(LABEL, "rise text-brand")}>Suno Content · case Inteli Academy × Finance</span>
              <h1 className="max-w-[16ch] text-5xl font-bold leading-[1.05] tracking-tight md:text-6xl">
                {["Um comunicado técnico,", "nove leituras", "medidas."].map((line, i) => (
                  <span key={line} className="rise block" style={delay(120 + i * 140)}>
                    {i === 2 ? <span className="text-brand">{line}</span> : line}
                  </span>
                ))}
              </h1>
              <p className="rise max-w-[58ch] text-lg leading-relaxed text-ink-2" style={delay(560)}>
                Atas do Copom, fatos relevantes e releases de resultados viram conteúdo para três níveis de investidor em três formatos.
                Antes de ser entregue, cada versão passa por um avaliador que mede legibilidade, jargão e fidelidade aos números da fonte,
                e volta para reescrita quando não atinge o nível pedido.
              </p>
              <div className="rise flex flex-wrap gap-3" style={delay(700)}>
                <PrimaryCta pulse>Abrir documentos</PrimaryCta>
                <Button asChild variant="secondary" className="nudge"><a href="#como-funciona">Como funciona <ArrowRight /></a></Button>
              </div>
            </div>
            <div className="rise rounded-lg border border-line bg-surface text-[13px] shadow-sm" style={delay(300)}>
              <div className={cn(LABEL, "flex items-center justify-between border-b border-line px-4 py-2.5 text-ink-3")}>
                <span className="caret">especificação</span>
                <span>v1.0</span>
              </div>
              <dl className="divide-y divide-line">
                {SPEC.map(([k, v], i) => (
                  <div key={k} className="rise grid grid-cols-[96px_1fr] gap-4 px-4 py-2.5 transition-colors hover:bg-surface-2" style={delay(450 + i * 110)}>
                    <dt className="text-ink-3">{k}</dt>
                    <dd className="font-medium text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>
        </section>

        <LiveNumbers />

        <Section index="01" title="O problema">
          <div className="grid gap-px rounded-lg border border-line bg-line md:grid-cols-2">
            {[
              ["Resumir não é adaptar", "Encurtar frases e trocar palavras difíceis perde as nuances que importam (o porquê da decisão do Copom, o que muda no balanço) ou infantiliza o leitor."],
              ["Nota de LLM não é medida", "Um único prompt avaliando outro tende a aprovar o que soa bem, premia textos longos e não conta quanto jargão ficou sem explicação."],
            ].map(([t, d], i) => (
              <Reveal key={t} delayMs={i * 150} className="lift flex flex-col gap-2 bg-surface p-6">
                <span className="font-bold">{t}</span>
                <p className="text-sm leading-relaxed text-ink-2">{d}</p>
              </Reveal>
            ))}
          </div>
          <Reveal delayMs={300}>
            <p className="mt-6 max-w-[70ch] text-ink-2">
              Por isso o sistema mede primeiro com regras que dão sempre o mesmo resultado, e usa LLM só onde regra não resolve, com temperatura 0
              e evidência literal para cada nota.
            </p>
          </Reveal>
        </Section>

        <Section id="como-funciona" index="02" title="Como funciona">
          <Pipeline />
        </Section>

        <Section index="03" title="A matriz de saída">
          <Matrix />
        </Section>

        <Section id="metricas" index="04" title="O que é medido">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className={cn(LABEL, "border-b border-line text-left text-ink-3")}>
                  <th scope="col" className="py-3">métrica</th>
                  <th scope="col" className="py-3">tipo</th>
                  <th scope="col" className="py-3">regra</th>
                </tr>
              </thead>
              <tbody>
                {METRICS.map(([m, t, r], i) => (
                  <tr key={m} className="border-b border-line transition-colors hover:bg-surface">
                    <td className="py-3 pr-4"><Reveal delayMs={i * 70} className="font-bold">{m}</Reveal></td>
                    <td className="py-3 pr-4">
                      <Reveal delayMs={i * 70 + 40}>
                        <span className={cn("rounded px-2 py-0.5 text-xs font-bold", t.startsWith("LLM") ? "bg-warn-soft text-warn" : "bg-ok-soft text-ok")}>{t}</span>
                      </Reveal>
                    </td>
                    <td className="py-3 text-ink-2"><Reveal delayMs={i * 70 + 80}>{r}</Reveal></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs text-ink-3">Limiares por nível versionados em thresholds.yaml · glossário com 93 termos.</p>
        </Section>

        <Section index="05" title="Como usar o painel">
          <ol className="grid gap-px rounded-lg border border-line bg-line md:grid-cols-3">
            {[
              ["Escolha ou envie um documento", "Os documentos coletados de fontes oficiais já estão processados. Um PDF novo é lido na hora."],
              ["Gere os conteúdos", "Com o cache, a matriz abre na hora. Ignorando o cache, o grafo roda de novo e mostra o progresso por etapa."],
              ["Inspecione", "Abra uma célula para ver o texto, as âncoras citadas, as métricas e o histórico de tentativas do loop."],
            ].map(([t, d], i) => (
              <Reveal key={t} delayMs={i * 140} className="lift flex flex-col gap-2 bg-surface p-6">
                <span className={cn(LABEL, "text-brand")}>passo {i + 1}</span>
                <span className="font-bold">{t}</span>
                <p className="text-sm leading-relaxed text-ink-2">{d}</p>
              </Reveal>
            ))}
          </ol>
          <Reveal delayMs={420} className="mt-8 flex flex-wrap gap-3">
            <PrimaryCta pulse>Abrir documentos</PrimaryCta>
            <Button asChild variant="secondary" className="nudge"><Link to="/avaliacao">Ver avaliação <ArrowRight /></Link></Button>
          </Reveal>
        </Section>
      </main>

      <SiteFooter />
    </div>
  );
}
