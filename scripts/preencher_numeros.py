"""Preenche README e material de apresentação com os números do experimento.

    uv run python scripts/preencher_numeros.py [outputs/experiment/<data>]

Lê os CSVs de outputs/experiment/<data>/ (padrão: o de manifesto mais recente), o manifest.json,
o thresholds.yaml e o exemplo de reflection (<exp>/demo/ ou outputs/demo/). Troca o conteúdo entre marcadores:

    inline:  <!--n:chave-->valor<!--/n-->
    bloco:   <!--t:chave--> ... <!--/t:chave-->

Copia também relatorio_experimental.md e figuras/ para docs/resultados/, para o README ter caminhos fixos.
Chave sem dado (ex.: concordância ainda não calculada) vira "a calcular". Rodar de novo é seguro.
"""

import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.evaluator.thresholds import load_thresholds  # noqa: E402
from backend.experiments.report import LABEL, LEVELS, accuracy, md_table  # noqa: E402

TARGETS = [ROOT / "README.md", ROOT / "docs" / "apresentacao" / "roteiro_video.md", ROOT / "docs" / "apresentacao" / "teleprompter.md",
           ROOT / "docs" / "apresentacao" / "slides_apoio.html"]
RESULTS_DIR = ROOT / "docs" / "resultados"
MISSING = "a calcular"
INLINE = re.compile(r"<!--n:([\w.]+)-->(.*?)<!--/n-->", re.S)
BLOCK = re.compile(r"<!--t:([\w.]+)-->\n(.*?)<!--/t:\1-->", re.S)


# --- formatação pt-BR ---

def num(x: float, dec: int = 1) -> str:
    return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, dec: int = 0) -> str:
    """x em fração (0–1)."""
    return f"{num(100 * x, dec)}%"


def usd(x: float) -> str:
    if not x:
        return "sem preço"  # model_prices.yaml vazio
    return f"US$ {num(x, 4 if x < 0.1 else 2)}"


def secs(x: float) -> str:
    return f"{num(x, 1 if x < 10 else 0)} s"


def _csv(exp: Path, name: str) -> pd.DataFrame | None:
    p = exp / "csv" / name
    return pd.read_csv(p) if p.exists() else None


# --- valores ---

def compute(exp: Path, demo_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    v: dict[str, str] = {}
    t: dict[str, str] = {}
    man = json.loads((exp / "manifest.json").read_text(encoding="utf-8"))
    v["data"] = man["date"]
    v["commit"] = man["git_commit"]
    for role, model in man["models"].items():
        v[f"modelo_{role}"] = f"`{model}`"
    main_docs = [d["id"] for d in man["documents"] if d["split"] == "principal"]
    v["n_docs"] = str(len(main_docs))
    v["docs"] = ", ".join(f"`{d}`" for d in main_docs)

    df = _csv(exp, "metricas.csv")
    if df is not None:
        main = df[df.split == "principal"] if "split" in df else df
        rate = main.groupby("system").passed.mean()
        v["aprov_pipeline"], v["aprov_baseline"] = pct(rate.get("pipeline")), pct(rate.get("baseline"))
        v["acc_pipeline"], v["acc_baseline"] = pct(accuracy(main, "pipeline")), pct(accuracy(main, "baseline"))
        v["n_saidas"] = str(int((main.system == "pipeline").sum()))
        rows = []
        for lvl in LEVELS:
            r = {"Nível": LABEL[lvl]}
            for system, name in (("pipeline", "Pipeline"), ("baseline", "Baseline")):
                sub = main[(main.system == system) & (main.audience == lvl)]
                r[f"Aprovação {name}"] = pct(sub.passed.mean()) if len(sub) else "—"
                r[f"Nível certo {name}"] = pct((sub.audience == sub.predicted_level).mean()) if len(sub) else "—"
            rows.append(r)
        t["tabela_baseline"] = md_table(pd.DataFrame(rows))
        if "split" in df and (df.split == "holdout").any():
            hold = df[df.split == "holdout"]
            hr = hold.groupby("system").passed.mean()
            v["holdout"] = (f"aprovação {pct(hr.get('pipeline'))} (pipeline) × "
                            f"{pct(hr.get('baseline'))} (baseline) e nível certo {pct(accuracy(hold, 'pipeline'))} × "
                            f"{pct(accuracy(hold, 'baseline'))}")
        else:
            v["holdout"] = "não houve nesta execução"

    loop = _csv(exp, "reflection_stats.csv")
    if loop is not None:
        loop = loop[loop.split == "principal"] if "split" in loop else loop
        v["refl_antes"] = pct(loop.pct_approved_first.mean() / 100)
        v["refl_depois"] = pct(loop.pct_approved_final.mean() / 100)
        v["refl_ganho_pp"] = num(loop.pct_approved_final.mean() - loop.pct_approved_first.mean(), 0) + " p.p."
        v["refl_tentativas"] = num(loop.mean_attempts.mean(), 2)
        v["refl_regressoes"] = str(int(loop.regressions.sum()))

    costs = _csv(exp, "custo_por_documento.csv")
    if costs is not None:
        pipe = costs[(costs.system == "pipeline") & (costs.split == "principal")]
        v["custo_doc"] = usd(pipe.cost_usd.mean())
        v["tokens_doc"] = num(pipe.input_tokens.mean() + pipe.output_tokens.mean(), 0)
        v["chamadas_doc"] = num(pipe.llm_calls.mean(), 0)
        v["latencia_doc"] = secs(pipe.wall_s.mean())
        trade = _csv(exp, "tradeoffs.csv")
        # nos trade-offs, só a execução forte com reflection é nova: a barata é a execução principal e as
        # variantes sem reflection são a 1ª tentativa dessas mesmas execuções
        extra = trade[trade.config.str.startswith("forte") & (trade.max_tentativas > 1)] if trade is not None else None
        total = costs.cost_usd.sum() + (extra.custo_usd.sum() if extra is not None else 0)
        v["custo_experimento"] = usd(total)
        out = pd.DataFrame({
            "Documento": costs.doc_id.map(lambda d: f"`{d}`"),
            "Sistema": costs.system,
            "Chamadas LLM": costs.llm_calls,
            "Tokens": (costs.input_tokens + costs.output_tokens).map(lambda x: num(x, 0)),
            "Custo": costs.cost_usd.map(usd),
            "Tempo": costs.wall_s.map(secs),
        })
        t["tabela_custo_doc"] = md_table(out)

    trade = _csv(exp, "tradeoffs.csv")
    if trade is not None:
        tt = pd.DataFrame({
            "Configuração": trade.config,
            "Aprovação": trade.aprovacao.map(pct),
            "Flesch médio": trade.flesch_medio.map(lambda x: num(x, 1)),
            "Fidelidade": trade.fidelidade_media.map(pct),
            "Tentativas/saída": trade.tentativas_medias.map(lambda x: num(x, 2)),
            "Chamadas LLM": trade.chamadas_llm,
            "Tokens": trade.tokens.map(lambda x: num(x, 0)),
            "Custo": trade.custo_usd.map(usd),
            "Latência": [secs(s) + ("*" if str(k).startswith("estimada") else "")
                         for s, k in zip(trade.latencia_s, trade.get("latencia", [""] * len(trade)), strict=True)],
        })
        t["tabela_tradeoffs"] = md_table(tt)
        best = trade.aprovacao.max()
        good = trade[trade.aprovacao >= best - 0.05].sort_values(["custo_usd", "tokens", "latencia_s"])
        pick = good.iloc[0]
        top = trade.sort_values(["aprovacao", "custo_usd"], ascending=[False, True]).iloc[0]
        v["recomendacao"] = (
            f"**{pick.config}** é a configuração mais barata com aprovação a até 5 p.p. da melhor "
            f"({pct(pick.aprovacao)}, {usd(pick.custo_usd)}, {secs(pick.latencia_s)}). "
            + ("Ela também tem a maior aprovação." if pick.config == top.config else
               f"A maior aprovação é de **{top.config}** ({pct(top.aprovacao)}, {usd(top.custo_usd)}, "
               f"{secs(top.latencia_s)}).")
        )

    var = _csv(exp, "variancia.csv")
    if var is not None:
        judge = var[var.metric.str.startswith("judge_")]
        claims = var[var.metric == "claim_support"]
        det = var[var.tipo == "deterministica"]
        v["var_reps"] = str(int(var.repeticoes.max())) if "repeticoes" in var else "3"
        v["var_det_max"] = num(det.desvio_max.max(), 3)
        v["var_judge_std"] = num(judge.desvio_medio_entre_repeticoes.mean(), 3)
        v["var_judge_max"] = num(judge.desvio_max.max(), 3)
        v["var_claims_std"] = num(claims.desvio_medio_entre_repeticoes.mean(), 3) if len(claims) else MISSING
        tv = pd.DataFrame({
            "Métrica": var.metric.map(lambda m: f"`{m}`"),
            "Tipo": var.tipo.map({"deterministica": "determinística", "llm": "LLM"}).fillna(var.tipo),
            "Média": var.media.map(lambda x: num(x, 3)),
            "Desvio médio": var.desvio_medio_entre_repeticoes.map(lambda x: num(x, 3)),
            "Desvio máx.": var.desvio_max.map(lambda x: num(x, 3)),
        })
        t["tabela_variancia"] = md_table(tv)

    conc = _csv(exp, "concordancia.csv")
    if conc is not None:
        c = conc.set_index("dimensao")
        for key, dim in (("nivel", "nivel (percebido x previsto)"), ("fato", "erro factual"), ("triv", "trivializou")):
            r = c.loc[dim]
            if not r.n:  # dimensão opcional deixada em branco na revisão
                v[f"conc_{key}"] = v[f"conc_{key}_ic"] = v[f"kappa_{key}"] = "não avaliado"
                continue
            v[f"conc_{key}"] = pct(r.concordancia)
            v[f"conc_{key}_ic"] = f"{pct(r.ic95_inf)}–{pct(r.ic95_sup)}"
            v[f"kappa_{key}"] = "indefinido" if pd.isna(r.kappa_cohen) else num(r.kappa_cohen, 2)
        target = c.loc["nivel (percebido x alvo)"]
        v["conc_alvo"] = (f"{round(target.concordancia * target.n)} de {int(target.n)} ({pct(target.concordancia)})"
                          if target.n else "não avaliado")
        v["conc_tom_mae"] = num(c.loc["tom (erro absoluto médio, 1-5)"].concordancia, 2)
        v["conc_n"] = str(int(c.loc["nivel (percebido x previsto)"].n))
        v["conc_peso"] = num(100 / int(c.loc["nivel (percebido x previsto)"].n), 0) + " p.p."
        names = {"nivel (percebido x previsto)": "Nível: revisora × classificador",
                 "nivel (percebido x alvo)": "Nível: revisora × nível pedido",
                 "erro factual": "Erro factual", "trivializou": "Trivialização",
                 "tom (erro absoluto médio, 1-5)": "Tom: erro absoluto médio do judge (1 a 5)"}
        rows = []
        for _, r in conc.iterrows():
            tone = r.dimensao.startswith("tom")
            done = bool(r.n)
            rows.append({
                "Dimensão": names.get(r.dimensao, r.dimensao),
                "n": int(r.n) if done else "—",
                "Resultado": (num(r.concordancia, 2) if tone else pct(r.concordancia)) if done else "não avaliado",
                "IC 95%": f"{pct(r.ic95_inf)}–{pct(r.ic95_sup)}" if done and not tone else "—",
                "Kappa": num(r.kappa_cohen, 2) if done and pd.notna(r.kappa_cohen) else "—",
            })
        t["tabela_concordancia"] = md_table(pd.DataFrame(rows))

    gloss = yaml.safe_load((ROOT / "data" / "glossary" / "glossario.yaml").read_text(encoding="utf-8"))
    terms = gloss["termos"] if isinstance(gloss, dict) else gloss
    v["glossario_total"] = str(len(terms))
    v["glossario_pendentes"] = str(sum(1 for x in terms if x.get("status") == "pendente_revisao"))

    raw = load_thresholds().raw
    th, common = raw["levels"], raw.get("common", {})
    rows = [{"Métrica": f"`{m}`", **{LABEL[lvl]: _bound(th[lvl].get(m)) for lvl in LEVELS}} for m in th[LEVELS[0]]]
    rows += [{"Métrica": f"`{m}`" + (" (cada critério)" if m == "judge" else ""), **{LABEL[lvl]: _bound(b) for lvl in LEVELS}}
             for m, b in common.items()]
    t["tabela_limiares"] = md_table(pd.DataFrame(rows))

    demo = sorted(demo_dir.glob("reflection_*.json"), key=lambda p: p.stat().st_mtime)
    if demo:  # arquivo de demo mais recente
        t["exemplo_reflection"], v["exemplo_celula"] = _reflection_example(json.loads(demo[-1].read_text(encoding="utf-8")))
    return v, t


def _short(x: float) -> str:
    return num(x, 0) if float(x).is_integer() else num(x, 2)


def _bound(b) -> str:
    if b is None:
        return "—"
    if isinstance(b, dict):
        if "min" in b and "max" in b:
            return f"{_short(b['min'])} a {_short(b['max'])}"
        if "min" in b:
            return f"≥ {_short(b['min'])}"
        if "max" in b:
            return f"≤ {_short(b['max'])}"
        return "só reporta"
    return str(b)


def _reflection_example(payload: dict) -> tuple[str, str]:
    cells = payload["cells"]
    focus = payload.get("focus_cell")
    if focus in cells:
        key = focus
    else:
        key = "iniciante:texto" if "iniciante:texto" in cells else max(cells, key=lambda k: len(cells[k]["attempts"]))
    attempts = cells[key]["attempts"]
    names = [m["name"] for m in attempts[0]["metrics"]]
    rows = []
    for a in attempts:
        scores = {m["name"]: m for m in a["metrics"]}
        rows.append({"Tentativa": a["attempt"], "Nota agregada": num(a["aggregate_score"], 3),
                     "Aprovada": "sim" if a["passed"] else "não",
                     **{n: f"{num(scores[n]['score'], 2)} {'✓' if scores[n]['passed'] else '✗'}" for n in names if n in scores}})
    status = cells[key]["status"] or {}
    first, last = attempts[0]["text"], attempts[-1]["text"]
    clip = lambda s: (s[:600] + "…") if len(s) > 600 else s
    origin = (f"gerada com as regras do Avançado na 1ª tentativa (`--force-drift {payload['drift_level']}`)"
              if payload.get("forced", True) else "reflection real de uma execução normal do experimento (sem desvio forçado)")
    block = "\n".join([
        f"Documento `{payload['doc_id']}`, célula **{key}**, {origin}. Status final: `{status.get('status', '—')}` "
        f"(parada: `{status.get('stop_reason', '—')}`; entregue a tentativa {status.get('delivered_attempt', '—')}).", "",
        md_table(pd.DataFrame(rows)), "",
        "Feedback injetado na 2ª tentativa:", "",
        "```text", clip(attempts[1]["injected_feedback"].strip()) if len(attempts) > 1 else "(sem 2ª tentativa)", "```", "",
        "<details><summary>Texto antes (1ª tentativa) e depois (última)</summary>", "",
        "**Antes**", "", "```text", clip(first), "```", "",
        "**Depois**", "", "```text", clip(last), "```", "", "</details>",
    ])
    return block, key


# --- substituição ---

def fill(text: str, values: dict[str, str], tables: dict[str, str]) -> tuple[str, set[str]]:
    missing: set[str] = set()

    def inline(m: re.Match) -> str:
        key = m.group(1)
        if key not in values:
            missing.add(key)
        return f"<!--n:{key}-->{values.get(key, MISSING)}<!--/n-->"

    def block(m: re.Match) -> str:
        key = m.group(1)
        if key not in tables:
            missing.add(key)
        body = tables.get(key, f"_{MISSING}_")
        return f"<!--t:{key}-->\n{body}\n<!--/t:{key}-->"

    return BLOCK.sub(block, INLINE.sub(inline, text)), missing


def copy_results(exp: Path) -> None:
    if RESULTS_DIR.exists():
        shutil.rmtree(RESULTS_DIR)
    (RESULTS_DIR / "figuras").mkdir(parents=True)
    for png in (exp / "figuras").glob("*.png"):
        shutil.copy2(png, RESULTS_DIR / "figuras" / png.name)
    shutil.copy2(exp / "relatorio_experimental.md", RESULTS_DIR / "relatorio_experimental.md")
    shutil.copy2(exp / "manifest.json", RESULTS_DIR / "manifest.json")


def main() -> None:
    if len(sys.argv) > 1:
        exp = Path(sys.argv[1])
    else:  # experimento com o manifesto mais recente
        exp = max((ROOT / "outputs" / "experiment").glob("*/manifest.json"), key=lambda p: p.stat().st_mtime).parent
    if len(sys.argv) > 2:
        demo_dir = Path(sys.argv[2])
    else:  # exemplo escolhido para o experimento, se houver; senão a demo mais recente
        demo_dir = exp / "demo" if (exp / "demo").is_dir() else ROOT / "outputs" / "demo"
    values, tables = compute(exp, demo_dir)
    copy_results(exp)
    for path in TARGETS:
        if not path.exists():
            continue
        new, missing = fill(path.read_text(encoding="utf-8"), values, tables)
        path.write_text(new, encoding="utf-8", newline="\n")
        print(f"{path.relative_to(ROOT)}: ok" + (f" (sem dado: {', '.join(sorted(missing))})" if missing else ""))
    print(f"resultados copiados para {RESULTS_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
