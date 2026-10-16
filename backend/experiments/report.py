"""Figuras (PNG + CSV) e relatório do experimento, gerados a partir dos CSVs do diretório."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backend.evaluator.thresholds import load_thresholds
from backend.schemas import Audience

LEVELS = ["iniciante", "intermediario", "avancado"]
LABEL = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}
COLOR = {"iniciante": "#1d5fd1", "intermediario": "#6b34c9", "avancado": "#b8480c"}
SYSTEM = {"pipeline": "Pipeline", "baseline": "Baseline ingênuo"}
HUMAN_START, HUMAN_END = "<!-- concordancia:inicio -->", "<!-- concordancia:fim -->"

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})


def _csv(exp: Path, name: str) -> pd.DataFrame | None:
    path = exp / "csv" / name
    return pd.read_csv(path) if path.exists() else None


def confusion(df: pd.DataFrame, system: str) -> pd.DataFrame:
    sub = df[df.system == system]
    return pd.crosstab(pd.Categorical(sub.audience, LEVELS), pd.Categorical(sub.predicted_level, LEVELS),
                       rownames=["alvo"], colnames=["previsto"], dropna=False)


def accuracy(df: pd.DataFrame, system: str) -> float:
    sub = df[df.system == system]
    return float((sub.audience == sub.predicted_level).mean()) if len(sub) else float("nan")


# --- figuras ---

def fig_confusion(df: pd.DataFrame, out: Path) -> None:
    systems = [s for s in ("pipeline", "baseline") if s in set(df.system)]
    fig, axes = plt.subplots(1, len(systems), figsize=(5 * len(systems), 4.2))
    axes = [axes] if len(systems) == 1 else axes
    for ax, system in zip(axes, systems, strict=True):
        m = confusion(df, system)
        m.to_csv(out.parent / "csv" / f"confusao_{system}.csv")
        ax.imshow(m.values, cmap="Greens", vmin=0)
        ax.set_xticks(range(3), [LABEL[lvl] for lvl in LEVELS])
        ax.set_yticks(range(3), [LABEL[lvl] for lvl in LEVELS])
        ax.set_xlabel("nível previsto pelas métricas")
        ax.set_ylabel("nível alvo")
        ax.set_title(f"{SYSTEM[system]}: {accuracy(df, system):.0%} no nível certo (n={int(m.values.sum())})")
        for i in range(3):
            for j in range(3):
                v = int(m.values[i, j])
                ax.text(j, i, v, ha="center", va="center", fontsize=12,
                        color="white" if v > m.values.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(out / "confusao_niveis.png")
    plt.close(fig)


def fig_distribution(df: pd.DataFrame, out: Path) -> None:
    th = load_thresholds()
    metrics = [("flesch_pt", "Legibilidade (Flesch PT)"), ("term_density", "Termos técnicos / 100 palavras"), ("term_context_pct", "Termos contextualizados (%)")]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    for ax, (metric, title) in zip(axes, metrics, strict=True):
        for i, level in enumerate(LEVELS):
            bound = th.level_bound(Audience(level), metric)
            if bound.min is not None or bound.max is not None:
                ymin = bound.min if bound.min is not None else min(df[metric].min(), 0)
                ymax = bound.max if bound.max is not None else max(df[metric].max(), 100 if metric != "term_density" else 15)
                ax.fill_between([i - 0.4, i + 0.4], ymin, ymax, color=COLOR[level], alpha=0.1, linewidth=0)
            for k, system in enumerate(("pipeline", "baseline")):
                vals = df[(df.audience == level) & (df.system == system)][metric].dropna()
                x = [i + (k - 0.5) * 0.3] * len(vals)
                ax.scatter(x, vals, s=36, color=COLOR[level] if system == "pipeline" else "#888888",
                           marker="o" if system == "pipeline" else "x", label=SYSTEM[system] if i == 0 else None)
        ax.set_xticks(range(3), [LABEL[lvl] for lvl in LEVELS])
        ax.set_title(title)
    axes[0].legend(loc="lower left", frameon=False)
    fig.suptitle("Distribuição por nível (faixa sombreada = limiar do nível)")
    fig.tight_layout()
    fig.savefig(out / "distribuicao_metricas.png")
    plt.close(fig)


def table_baseline_vs_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ("flesch_pt", "term_density", "term_context_pct", "claim_support", "judge_adequacao_publico", "judge_nuances") if c in df]
    agg = df.groupby(["system", "audience"]).agg(saidas=("passed", "size"), aprovacao=("passed", "mean"), **{c: (c, "mean") for c in cols})
    return agg.reset_index().round(3)


def fig_baseline(df: pd.DataFrame, out: Path) -> None:
    t = table_baseline_vs_pipeline(df)
    t.to_csv(out.parent / "csv" / "baseline_vs_pipeline.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4))
    width = 0.38
    for k, system in enumerate(("pipeline", "baseline")):
        vals = [float(t[(t.system == system) & (t.audience == lvl)].aprovacao.iloc[0]) * 100 if len(t[(t.system == system) & (t.audience == lvl)]) else 0 for lvl in LEVELS]
        ax.bar([i + (k - 0.5) * width for i in range(3)], vals, width, label=SYSTEM[system], color="#17181b" if system == "pipeline" else "#c9c2b3")
    ax.set_xticks(range(3), [LABEL[lvl] for lvl in LEVELS])
    ax.set_ylim(0, 100)
    ax.set_ylabel("aprovação (%)")
    ax.set_title("Aprovação por nível: baseline × pipeline")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out / "baseline_vs_pipeline.png")
    plt.close(fig)


def fig_reflection(loop: pd.DataFrame, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 0.6 + 0.8 * len(loop)))
    y = range(len(loop))
    ax.barh([i + 0.2 for i in y], loop.pct_approved_first, height=0.4, color="#c9c2b3", label="1ª tentativa")
    ax.barh([i - 0.2 for i in y], loop.pct_approved_final, height=0.4, color="#14724a", label="depois do loop")
    ax.set_yticks(list(y), loop.doc_id)
    ax.set_xlim(0, 100)
    ax.set_xlabel("saídas aprovadas (%)")
    ax.set_title("Reflection loop: aprovação antes × depois")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(out / "reflection_antes_depois.png")
    plt.close(fig)


def fig_costs(nodes: pd.DataFrame | None, trade: pd.DataFrame | None, out: Path) -> None:
    panels = [p for p in (nodes, trade) if p is not None]
    if not panels:
        return
    fig, axes = plt.subplots(1, len(panels), figsize=(7 * len(panels), 4.2))
    axes = [axes] if len(panels) == 1 else axes
    i = 0
    if nodes is not None:
        n = nodes.sort_values("latency_s")
        axes[i].barh(n.node, n.latency_s, color="#4a4c52")
        axes[i].set_xlabel("latência somada (s)")
        axes[i].set_title("Latência por nó (todos os documentos)")
        i += 1
    if trade is not None:
        ax = axes[i]
        loop = trade.max_tentativas > 1
        ax.scatter(trade.tokens[loop], trade.aprovacao[loop] * 100, s=80, color="#17181b", label="com reflection")
        ax.scatter(trade.tokens[~loop], trade.aprovacao[~loop] * 100, s=80, facecolors="white", edgecolors="#17181b",
                   label="sem reflection")
        placed: list[tuple[float, float]] = []
        for _, r in trade.iterrows():
            x, y = r.tokens, r.aprovacao * 100
            # rótulos de pontos próximos alternam acima/abaixo para não se sobrepor
            near = sum(abs(x - px) < 0.08 * trade.tokens.max() and abs(y - py) < 1 for px, py in placed)
            ax.annotate(r.config, (x, y), textcoords="offset points", xytext=(8, 6 if near % 2 == 0 else -14), fontsize=9)
            placed.append((x, y))
        ax.set_ylim(bottom=-2)
        ax.legend(frameon=False, loc="center right")
        ax.set_xlabel("tokens totais")
        ax.set_ylabel("aprovação (%)")
        ax.set_title("Trade-off por configuração (1 documento)")
    fig.tight_layout()
    fig.savefig(out / "custo_latencia.png")
    plt.close(fig)


def fig_variance(var: pd.DataFrame, out: Path) -> None:
    v = var.sort_values("desvio_medio_entre_repeticoes")
    fig, ax = plt.subplots(figsize=(7, 0.5 + 0.35 * len(v)))
    ax.barh(v.metric, v.desvio_medio_entre_repeticoes, color=["#14724a" if t == "deterministica" else "#b8480c" for t in v.tipo])
    reps = int(v.repeticoes.max()) if "repeticoes" in v else 3
    ax.set_xlabel(f"desvio padrão médio entre {reps} repetições")
    ax.set_title("Variância do avaliador (verde = determinística)")
    fig.tight_layout()
    fig.savefig(out / "variancia.png")
    plt.close(fig)


def write_figures(exp: Path) -> None:
    out = exp / "figuras"
    df = _csv(exp, "metricas.csv")
    if df is not None:
        main = df[df.split == "principal"] if "split" in df else df
        fig_confusion(main, out)
        fig_distribution(main, out)
        fig_baseline(main, out)
    if (loop := _csv(exp, "reflection_stats.csv")) is not None:
        fig_reflection(loop, out)
    fig_costs(_csv(exp, "custo_por_no.csv"), _csv(exp, "tradeoffs.csv"), out)
    if (var := _csv(exp, "variancia.csv")) is not None:
        fig_variance(var, out)


# --- relatório ---

def pct(x: float) -> str:
    return f"{x * 100:.0f}%" if pd.notna(x) else "—"


def md_table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join("" if pd.isna(r[c]) else str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def _pending_terms() -> int:
    import yaml

    from backend.config import GLOSSARY_PATH
    terms = yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8"))["termos"]
    return sum(1 for t in terms if t.get("status") == "pendente_revisao")


def write_report(exp: Path, man: dict) -> None:
    df = _csv(exp, "metricas.csv")
    loop = _csv(exp, "reflection_stats.csv")
    costs = _csv(exp, "custo_por_documento.csv")
    var = _csv(exp, "variancia.csv")
    trade = _csv(exp, "tradeoffs.csv")
    th = load_thresholds().raw
    sim = any("simulado" in m or "fake" in m or "sim:" in m for m in man["models"].values())

    s: list[str] = [f"# Relatório experimental · {man['date']}", ""]
    if sim:
        s += ["> **ATENÇÃO: execução de SIMULAÇÃO (LLM falso).** Os números abaixo validam o processo, não o sistema. "
              "Rode `backend.experiments.experiment` com os modelos reais antes de usar qualquer número.", ""]
    if man.get("comparacao") == "deterministica":
        s += ["> **Comparação pipeline × baseline só nas métricas determinísticas** (legibilidade, densidade, contextualização "
              "e grounding numérico), recalculadas para os dois sistemas sobre os mesmos textos. O pipeline foi gerado com o "
              "avaliador completo (LLM incluído) no reflection loop, mas a aprovação nas tabelas abaixo usa só as métricas "
              "determinísticas, para os dois sistemas serem medidos com a mesma régua.", ""]
    s += [
        "## 1. Configuração e reprodutibilidade", "",
        f"- Commit: `{man['git_commit']}`",
        "- Modelos: " + ", ".join(f"{k} = `{v}`" for k, v in man["models"].items()),
        f"- Temperatura: geração {man['temperature']['geracao']}, avaliação {man['temperature']['avaliacao']}",
        f"- Reflection: até {man['max_attempts']} tentativas por saída; parada se a nota agregada subir menos que {man['reflection_epsilon']}",
        "- Hashes: " + ", ".join(f"{k} `{v}`" for k, v in man["hashes"].items()),
        "- Documentos: " + ", ".join(f"`{d['id']}` ({d['split']})" for d in man["documents"]),
        "", "Tudo foi gerado por `uv run python -m backend.experiments` a partir de `manifest.json`; as tabelas abaixo saem de `csv/`.", "",
        "## 2. Metodologia de avaliação", "",
        "Cada saída passa pelo Avaliador Híbrido. As métricas determinísticas vêm primeiro e o LLM só entra onde regra não resolve:", "",
        "| Métrica | Tipo | Regra |", "|---|---|---|",
        "| `flesch_pt` | determinística | Flesch de Martins et al. (248,835 − 1,015·palavras/frase − 84,6·sílabas/palavra), sílabas por pyphen pt_BR |",
        "| `term_density` | determinística | termos do glossário (lema spaCy + variações) por 100 palavras |",
        "| `term_context_pct` | determinística | % dos termos acima do nível com explicação na mesma frase, na anterior ou na seguinte por anáfora |",
        "| `numeric_grounding` | determinística | números sem correspondência na fonte (aceita arredondamento e mudança de unidade) |",
        "| `claim_support`, `claim_contradictions` | LLM, temp. 0 | afirmações atômicas contra as âncoras; contradição reprova |",
        "| `judge_*` | LLM, temp. 0 | 4 critérios de 1 a 5 com trecho literal como evidência; tamanho do texto não é critério |",
        "", "O nível previsto de cada saída vem só de Flesch e densidade (as métricas que não dependem do nível pedido). "
        "O baseline é um prompt único (“resuma para um investidor X no formato Y”), sem extractor, âncoras ou glossário, avaliado com a mesma suíte.", "",
        "## 3. Calibração dos limiares", "",
        "Limiares usados (`thresholds.yaml`):", "",
        md_table(pd.DataFrame([{"nível": lvl, **{m: json.dumps(v, ensure_ascii=False) for m, v in th["levels"][lvl].items()}} for lvl in LEVELS])), "",
        "Os limiares são os do briefing. A calibração rodou em 7 textos golden escritos à mão, não nas saídas avaliadas aqui. "
        "Por isso não há vazamento entre calibração e avaliação; a contrapartida é que os limiares não foram ajustados com dados reais (ver Limitações).", "",
    ]

    if df is not None:
        main = df[df.split == "principal"] if "split" in df else df
        rate = main.groupby("system").passed.mean()
        s += ["## 4. Resultados", "", "### 4.1 Baseline × pipeline", "",
              f"Aprovação geral: **pipeline {pct(rate.get('pipeline'))}** × baseline {pct(rate.get('baseline'))} "
              f"({int((main.system == 'pipeline').sum())} e {int((main.system == 'baseline').sum())} saídas).", "",
              md_table(table_baseline_vs_pipeline(main)), "", "![Baseline × pipeline](figuras/baseline_vs_pipeline.png)", "",
              "### 4.2 Matriz de confusão de níveis", "",
              f"Acurácia de nível: **pipeline {pct(accuracy(main, 'pipeline'))}** × baseline {pct(accuracy(main, 'baseline'))}.", "",
              "![Matriz de confusão](figuras/confusao_niveis.png)", "",
              "### 4.3 Distribuição das métricas por nível", "", "![Distribuição](figuras/distribuicao_metricas.png)", ""]
        if "split" in df and (df.split == "holdout").any():
            hold = df[df.split == "holdout"]
            hr = hold.groupby("system").passed.mean()
            s += ["### 4.4 Documento hold-out (nunca usado antes)", "",
                  f"Aprovação: pipeline {pct(hr.get('pipeline'))} × baseline {pct(hr.get('baseline'))}; "
                  f"acurácia de nível: pipeline {pct(accuracy(hold, 'pipeline'))} × baseline {pct(accuracy(hold, 'baseline'))}.", ""]
    if loop is not None:
        s += ["### Reflection loop", "", md_table(loop), "", "![Reflection](figuras/reflection_antes_depois.png)", "",
              f"Média: aprovação na 1ª tentativa {loop.pct_approved_first.mean():.1f}% → depois do loop {loop.pct_approved_final.mean():.1f}%, "
              f"{loop.mean_attempts.mean():.2f} tentativas por saída, {int(loop.regressions.sum())} regressão(ões) detectada(s).", ""]
    if var is not None:
        det = var[var.tipo == "deterministica"]
        reps = int(var.repeticoes.max()) if "repeticoes" in var else 3
        s += [f"### Variância do avaliador ({reps} repetições sobre as mesmas saídas)", "",
              "A 1ª repetição é a avaliação feita durante a execução principal; as demais reavaliam as mesmas saídas.", "",
              f"Métricas determinísticas: desvio máximo **{det.desvio_max.max():g}** (devem ser 0).", "",
              md_table(var), "", "![Variância](figuras/variancia.png)", ""]
    s += ["## 5. Concordância humano × avaliador", "", HUMAN_START,
          "_A preencher: complete `revisao_humana.csv` e rode `uv run python -m backend.experiments.human_agreement " + str(exp) + "`. "
          "O script substitui esta seção._", HUMAN_END, ""]
    if costs is not None or trade is not None:
        s += ["## 6. Trade-offs de custo e latência", ""]
        if costs is not None:
            s += ["Custo por documento:", "", md_table(costs), ""]
        if trade is not None:
            s += ["Configurações no mesmo documento. A geração barata é a execução principal; a forte troca o modelo de "
                  "adapters, formatters e refiner. A variante sem reflection é a 1ª tentativa de cada execução (com uma "
                  "tentativa só, o grafo termina nessa avaliação); a latência dela é estimada pelo caminho crítico.", "",
                  md_table(trade), "", "![Custo e latência](figuras/custo_latencia.png)", ""]
    s += [
        "## 7. Limitações", "",
        "- **Limiares não calibrados com dados reais.** Vêm do briefing; a calibração usou só textos golden. Sem vazamento, mas sem ajuste empírico.",
        "- **Amostra pequena.** Poucos documentos e 9 saídas por documento: as taxas têm intervalo de confiança largo.",
        "- **O nível previsto usa só duas métricas** (Flesch e densidade); textos curtos (< 100 palavras) têm baixa confiabilidade e são sinalizados.",
        "- **Sílabas por hifenização** (pyphen) erram alguns hiatos (\"monetária\" = 4), deixando o Flesch levemente otimista.",
        "- **Grounding numérico tolerante** a inteiros pequenos, por comparar em várias escalas; a checagem semântica fica com o LLM.",
        "- **Judge e checker de afirmações dependem de LLM** (ver variância); a concordância humana é a validação externa.",
        "- **Custo em US$** depende de `backend/model_prices.yaml`; se vazio, só tokens e latência valem.", "",
        "## 8. Próximos passos", "",
        "- Calibrar os limiares com textos de referência por nível e validar no hold-out.",
        "- Ampliar o corpus (mais tipos de documento) e repetir a revisão humana com mais de um avaliador.",
        f"- Revisar os {_pending_terms()} termos do glossário marcados como pendentes.", "",
    ]
    (exp / "relatorio_experimental.md").write_text("\n".join(s), encoding="utf-8")
