"""Exibe no terminal o histórico de uma célula do reflection loop.

Uso:
    uv run python -m backend.reflection.show --doc <id> [--cell iniciante:texto]

Lê outputs/demo/reflection_<doc_id>.json, gerado por `backend.run --force-drift <nível>`
ou pelo experimento.
"""

import argparse
import json

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from backend.config import OUTPUTS_DIR
from backend.reflection.report import demo_path

SNIPPET = 420


def _pick_cell(cells: dict, wanted: str | None) -> str:
    if wanted:
        return wanted
    # mais tentativas primeiro; em empate, o texto analítico
    ranked = sorted(cells, key=lambda k: (-len(cells[k]["attempts"]), not k.endswith(":texto")))
    return ranked[0]


def _metric_cell(m: dict) -> Text:
    style = "bold green" if m["passed"] else "bold red"
    score = f"{m['score']:.2f}".rstrip("0").rstrip(".")
    return Text(f"{'✔' if m['passed'] else '✘'} {score}", style=style)


def render(payload: dict, cell: str, console: Console) -> None:
    data = payload["cells"][cell]
    attempts = data["attempts"]
    status = data["status"] or {}

    console.rule(f"[bold]Reflection loop · {payload['doc_id']} · {cell}")
    origin = (
        f"Desvio forçado: nível [bold]{payload['drift_level']}[/] gerado com as regras do Avançado na 1ª tentativa.\n"
        if payload.get("forced", True) else "Reflection real de uma execução normal (sem desvio forçado).\n"
    )
    console.print(
        origin + f"Status final: [bold]{status.get('status', '?')}[/] · tentativas: {status.get('attempts', len(attempts))} · "
        f"entregue: tentativa {status.get('delivered_attempt', '?')} · parada: {status.get('stop_reason', '?')}"
    )

    metric_names = [m["name"] for m in attempts[0]["metrics"]]
    bounds = {m["name"]: m["bound"] for m in attempts[0]["metrics"]}
    table = Table(title="Tentativas × métricas", show_lines=True)
    table.add_column("métrica")
    table.add_column("limiar", style="dim")
    for a in attempts:
        table.add_column(f"tentativa {a['attempt']}", justify="center")
    for name in metric_names:
        row = [name, bounds[name]]
        for a in attempts:
            m = next((x for x in a["metrics"] if x["name"] == name), None)
            row.append(_metric_cell(m) if m else Text("—"))
        table.add_row(*row)
    table.add_row(
        Text("nota agregada", style="bold"), "",
        *[Text(f"{a['aggregate_score']:.3f}", style="bold green" if a["passed"] else "bold yellow") for a in attempts],
    )
    table.add_row(
        "regressões", "",
        *[Text(", ".join(a["regressions"]) or "—", style="red" if a["regressions"] else "dim") for a in attempts],
    )
    console.print(table)

    for a in attempts[1:]:
        console.print(Panel(a["injected_feedback"] or "(vazio)", title=f"Feedback injetado → tentativa {a['attempt']}", border_style="yellow"))

    first, last = attempts[0], attempts[-1]
    console.print(Panel(
        Group(
            Text("ANTES (tentativa 1)", style="bold red"), Text(first["text"][:SNIPPET] + "…"), Text(""),
            Text(f"DEPOIS (tentativa {last['attempt']})", style="bold green"), Text(last["text"][:SNIPPET] + "…"),
        ),
        title="Trecho antes / depois",
    ))
    if len(attempts) > 1:
        diff = Text()
        for line in last["diff_from_previous"][:14]:
            diff.append(line + "\n", style="green" if line.startswith("+") else "red" if line.startswith("-") else "dim")
        console.print(Panel(diff, title=f"Diff tentativa {attempts[-2]['attempt']} → {last['attempt']} (por frase)"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mostra a demo do reflection loop.")
    parser.add_argument("--doc", required=True)
    parser.add_argument("--cell", help="ex.: iniciante:texto (padrão: a célula com mais tentativas)")
    args = parser.parse_args()

    path = demo_path(args.doc, OUTPUTS_DIR)
    if not path.exists():
        raise SystemExit(f"{path} não existe. Rode: uv run python -m backend.run --doc {args.doc} --force-drift iniciante")
    payload = json.loads(path.read_text(encoding="utf-8"))
    render(payload, _pick_cell(payload["cells"], args.cell or payload.get("focus_cell")), Console())


if __name__ == "__main__":
    main()
