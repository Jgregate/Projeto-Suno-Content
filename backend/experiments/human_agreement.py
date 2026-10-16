"""Concordância entre a revisão humana e o avaliador.

    uv run python -m backend.experiments.human_agreement outputs/experiment/<data>

1. Valida a revisão (revisao_humana.xlsx, se existir; senão revisao_humana.csv), checando linhas vazias, valores fora do padrão e ids que não batem.
   Com erro, para e lista o que corrigir.
2. Calcula, contra csv/avaliador_<doc>.csv:
   - acurácia e kappa de Cohen do nível (humano: nível percebido; avaliador: nível previsto);
   - concordância e kappa em erro factual (sim/não) e em trivialização;
   - erro absoluto médio entre o tom humano (1–5) e o judge_tom.
3. Grava csv/concordancia.csv, csv/confusao_humano_avaliador.csv e figuras/concordancia.png.
4. Substitui a seção de concordância do relatorio_experimental.md, com interpretação gerada dos números.
"""

import math
import sys
import unicodedata
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from backend.experiments.human_sheet import load_human
from backend.experiments.report import HUMAN_END, HUMAN_START, LABEL, LEVELS, md_table

YES_NO = ("sim", "nao")
REQUIRED = ("nivel_percebido", "tom_1a5")
# opcionais: uma coluna deixada inteira em branco vira dimensão "não avaliada" no relatório
OPTIONAL = ("erro_factual", "trivializou")


def _norm(v) -> str:
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().strip().lower()
    return {"s": "sim", "y": "sim", "yes": "sim", "n": "nao", "no": "nao"}.get(s, s)


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Kappa de Cohen para dois avaliadores sobre os mesmos itens."""
    n = len(a)
    if n == 0:
        return float("nan")
    labels = sorted(set(a) | set(b))
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((a.count(k) / n) * (b.count(k) / n) for k in labels)
    # pe = 1: os dois usaram uma única classe; o kappa não é definido.
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de 95% de Wilson para uma proporção k/n (bom para n pequeno)."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, mid - half), min(1.0, mid + half)


# --- validação ---

def validate(human: pd.DataFrame, machine: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Devolve (erros, avisos). Erros impedem o cálculo."""
    errors, warnings = [], []
    missing_cols = [c for c in ("id", *REQUIRED, *OPTIONAL, "erro_descricao") if c not in human.columns]
    if missing_cols:
        return [f"colunas ausentes: {', '.join(missing_cols)}"], []
    for col in OPTIONAL:
        filled = human[col].astype(str).str.strip().ne("")
        if not filled.any():
            warnings.append(f"{col} não preenchido: dimensão não avaliada")
        elif not filled.all():
            warnings.append(f"{col} preenchido em {int(filled.sum())} de {len(human)} saídas: concordância calculada só nelas")
    if human.id.duplicated().any():
        errors.append(f"ids repetidos: {', '.join(human.id[human.id.duplicated()])}")
    extra = sorted(set(human.id) - set(machine.id))
    absent = sorted(set(machine.id) - set(human.id))
    if extra:
        errors.append(f"ids que não existem no avaliador: {', '.join(extra)}")
    if absent:
        errors.append(f"saídas sem revisão: {', '.join(absent)}")

    for _, row in human.iterrows():
        rid = row.id
        if not any(str(row[c]).strip() for c in (*REQUIRED, *OPTIONAL)):
            errors.append(f"{rid}: linha vazia")
            continue
        empty = [c for c in REQUIRED if not str(row[c]).strip()]
        if empty:
            errors.append(f"{rid}: vazio em {', '.join(empty)}")
        lvl = _norm(row.nivel_percebido)
        if lvl and lvl not in LEVELS:
            errors.append(f"{rid}: nivel_percebido '{row.nivel_percebido}' (use iniciante/intermediário/avançado)")
        for col in ("erro_factual", "trivializou"):
            v = _norm(row[col])
            if v and v not in YES_NO:
                errors.append(f"{rid}: {col} '{row[col]}' (use sim/não)")
        tone = str(row.tom_1a5).strip()
        if tone and not (tone.isdigit() and 1 <= int(tone) <= 5):
            errors.append(f"{rid}: tom_1a5 '{tone}' (use inteiro de 1 a 5)")
        has_desc = bool(str(row.erro_descricao).strip())
        if _norm(row.erro_factual) == "sim" and not has_desc:
            warnings.append(f"{rid}: erro_factual = sim sem erro_descricao")
        if _norm(row.erro_factual) == "nao" and has_desc:
            warnings.append(f"{rid}: erro_factual = não, mas há erro_descricao")
    return errors, warnings


# --- cálculo ---

def agreement(human: pd.DataFrame, machine: pd.DataFrame) -> pd.DataFrame:
    df = human.merge(machine, on="id", suffixes=("_humano", "_avaliador"))
    rows = []

    def pair(name: str, h: pd.Series, m: pd.Series) -> None:
        mask = h.map(_norm).ne("") & h.notna()
        hh, mm = list(h[mask].map(_norm)), list(m[mask].map(_norm))
        hits = sum(x == y for x, y in zip(hh, mm, strict=True))
        lo, hi = wilson(hits, len(hh))
        rows.append({"dimensao": name, "n": len(hh),
                     "concordancia": round(hits / len(hh), 3) if hh else None,
                     "ic95_inf": round(lo, 3) if hh else None,
                     "ic95_sup": round(hi, 3) if hh else None,
                     "kappa_cohen": round(cohen_kappa(hh, mm), 3) if hh else None})  # NaN = uma só classe

    pair("nivel (percebido x previsto)", df.nivel_percebido, df.nivel_previsto)
    pair("nivel (percebido x alvo)", df.nivel_percebido, df.nivel_alvo)
    pair("erro factual", df.erro_factual_humano, df.erro_factual_avaliador)
    pair("trivializou", df.trivializou_humano, df.trivializou_avaliador)
    tone = df[["tom_1a5", "judge_tom"]].apply(pd.to_numeric, errors="coerce").dropna()
    rows.append({"dimensao": "tom (erro absoluto médio, 1-5)", "n": len(tone),
                 "concordancia": round(float((tone.tom_1a5 - tone.judge_tom).abs().mean()), 3) if len(tone) else None,
                 "ic95_inf": None, "ic95_sup": None, "kappa_cohen": None})
    return pd.DataFrame(rows)


def level_matrix(human: pd.DataFrame, machine: pd.DataFrame) -> pd.DataFrame:
    df = human.merge(machine, on="id")
    return pd.crosstab(pd.Categorical(df.nivel_percebido.map(_norm), LEVELS),
                       pd.Categorical(df.nivel_previsto.map(_norm), LEVELS),
                       rownames=["humano"], colnames=["avaliador"], dropna=False)


def fact_matrix(human: pd.DataFrame, machine: pd.DataFrame) -> pd.DataFrame:
    df = human.merge(machine, on="id", suffixes=("_humano", "_avaliador"))
    df = df[df.erro_factual_humano.map(_norm).isin(YES_NO)]  # coluna opcional: só as saídas respondidas
    return pd.crosstab(pd.Categorical(df.erro_factual_humano.map(_norm), YES_NO),
                       pd.Categorical(df.erro_factual_avaliador.map(_norm), YES_NO),
                       rownames=["humano"], colnames=["avaliador"], dropna=False)


def fig_agreement(levels: pd.DataFrame, facts: pd.DataFrame, table: pd.DataFrame, out: Path) -> None:
    get = table.set_index("dimensao")
    panels = [(levels, [LABEL[lvl] for lvl in LEVELS], "Nível", get.loc["nivel (percebido x previsto)"])]
    if get.loc["erro factual"].n:  # dimensão opcional; sem respostas, o painel fica de fora
        panels.append((facts, ["Sim", "Não"], "Erro factual", get.loc["erro factual"]))
    fig, axes = plt.subplots(1, len(panels), figsize=(10 if len(panels) == 2 else 6, 4.2),
                             gridspec_kw={"width_ratios": [3, 2][: len(panels)]})
    axes = [axes] if len(panels) == 1 else list(axes)
    for ax, (m, labels, title, stats) in zip(axes, panels, strict=True):
        k = len(labels)
        ax.imshow(m.values, cmap="Greens", vmin=0)
        ax.set_xticks(range(k), labels)
        ax.set_yticks(range(k), labels)
        ax.set_xlabel("avaliador")
        ax.set_ylabel("revisão humana")
        kappa = "" if pd.isna(stats.kappa_cohen) else f", κ = {stats.kappa_cohen:.2f}"
        ax.set_title(f"{title}: {stats.concordancia:.0%} de acordo{kappa} (n={int(stats.n)})")
        for i in range(k):
            for j in range(k):
                v = int(m.values[i, j])
                ax.text(j, i, v, ha="center", va="center", fontsize=12,
                        color="white" if v > m.values.max() / 2 else "black")
    fig.tight_layout()
    fig.savefig(out / "concordancia.png")
    plt.close(fig)


# --- interpretação ---

def kappa_band(k: float) -> str:
    if pd.isna(k):
        return "indefinido"
    if k < 0:
        return "pior que o acaso"
    for limit, name in ((0.2, "fraco"), (0.4, "razoável"), (0.6, "moderado"), (0.8, "substancial")):
        if k < limit:
            return name
    return "quase perfeito"


def interpret(table: pd.DataFrame) -> list[str]:
    get = table.set_index("dimensao")
    lines = []
    for dim, label in (("nivel (percebido x previsto)", "No nível"), ("erro factual", "Em erro factual"),
                       ("trivializou", "Em trivialização")):
        r = get.loc[dim]
        if not r.n:
            lines.append(f"- {label}: não avaliado na revisão humana.")
            continue
        hits = round(r.concordancia * r.n)
        lines.append(f"- {label}, humano e avaliador concordam em {hits} de {int(r.n)} saídas "
                     f"({r.concordancia:.0%}; IC 95% de Wilson {r.ic95_inf:.0%}–{r.ic95_sup:.0%}). "
                     + (f"Kappa = {r.kappa_cohen:.2f} ({kappa_band(r.kappa_cohen)})."
                        if not pd.isna(r.kappa_cohen) else
                        "Kappa indefinido: todas as respostas caíram numa única classe."))
    target = get.loc["nivel (percebido x alvo)"]
    if target.n:  # depois da linha do nível: o que o leitor percebe × o que foi pedido na geração
        lines.insert(1, f"- O nível percebido pelo revisor coincide com o nível pedido na geração em "
                        f"{round(target.concordancia * target.n)} de {int(target.n)} saídas ({target.concordancia:.0%}).")
    tone = get.loc["tom (erro absoluto médio, 1-5)"]
    if tone.n:
        lines.append(f"- No tom, o judge erra em média {tone.concordancia:.2f} ponto(s) na escala de 1 a 5.")
    n = int(get.loc["nivel (percebido x previsto)"].n or 0)
    if n:
        lines += [
            "",
            f"**Leitura honesta.** Com n = {n}, cada discordância move a concordância em {1 / n:.0%}. "
            "Os intervalos acima são largos: servem para ver a direção, não para afirmar que o avaliador "
            "equivale a um humano. O kappa também é instável com poucas saídas e classes desbalanceadas "
            "(ex.: se quase nenhuma saída tem erro factual, um único desacordo derruba o kappa mesmo com "
            "concordância alta). Há um único revisor, então não medimos a concordância entre humanos, "
            "que seria o teto realista para o avaliador. Todas as 9 saídas são do mesmo documento (Itaú 2T26).",
        ]
    return lines


def main() -> None:
    exp = Path(sys.argv[1]) if len(sys.argv) > 1 else sorted((Path("outputs") / "experiment").iterdir())[-1]
    human = load_human(exp)  # revisao_humana.xlsx, se existir; senão o CSV
    machine_files = sorted((exp / "csv").glob("avaliador_*.csv"))
    if not machine_files:
        raise SystemExit("csv/avaliador_<doc>.csv não encontrado: rode backend.experiments.experiment com --human-doc.")
    machine = pd.read_csv(machine_files[0], dtype=str).fillna("")

    errors, warnings = validate(human, machine)
    for w in warnings:
        print(f"aviso: {w}")
    if errors:
        print("a revisão humana tem problemas; corrija e rode de novo:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)

    table = agreement(human, machine)
    levels, facts = level_matrix(human, machine), fact_matrix(human, machine)
    table.to_csv(exp / "csv" / "concordancia.csv", index=False)
    levels.to_csv(exp / "csv" / "confusao_humano_avaliador.csv")
    (exp / "figuras").mkdir(exist_ok=True)
    fig_agreement(levels, facts, table, exp / "figuras")

    section = "\n".join([
        HUMAN_START, "",
        "Revisão cega: o revisor viu só o texto e o formato, sem nível-alvo nem notas do avaliador.", "",
        "![Concordância humano × avaliador](figuras/concordancia.png)", "",
        md_table(table), "",
        *interpret(table), "",
        "Kappa de Cohen: < 0,2 fraco; 0,2–0,4 razoável; 0,4–0,6 moderado; 0,6–0,8 substancial; > 0,8 quase perfeito.", "",
        HUMAN_END,
    ])
    report = exp / "relatorio_experimental.md"
    text = report.read_text(encoding="utf-8")
    start, end = text.index(HUMAN_START), text.index(HUMAN_END) + len(HUMAN_END)
    report.write_text(text[:start] + section + text[end:], encoding="utf-8")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
