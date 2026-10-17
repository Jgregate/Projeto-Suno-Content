"""Tira os screenshots e o GIF do README com o app em modo demo.

    scripts/demo.sh                     # em outro terminal: API :8000 + frontend :5173
    uv run --group docs python scripts/capturar_telas.py [--doc <id>]

Grava docs/img/01_documentos.png … 06_avaliacao.png e docs/img/demo.gif (matriz → comparar → detalhe → reflection).
Navegador: CHROME_PATH (se definido) → Chrome instalado (channel="chrome") → Chromium do Playwright.
"""

import argparse
import io
import json
import os
import urllib.request
from pathlib import Path

from PIL import Image
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "img"
VIEWPORT = {"width": 1440, "height": 900}


def pick_doc(api: str) -> str:
    docs = json.load(urllib.request.urlopen(f"{api}/documents"))
    with_runs = [d for d in docs if d.get("runs")]
    if not with_runs:
        raise SystemExit("Nenhum documento com execução no cache: rode o experimento antes.")
    itau = [d for d in with_runs if "itau" in d["id"].lower()]
    return (itau or with_runs)[0]["id"]


def launch(p) -> Browser:
    if path := os.environ.get("CHROME_PATH"):
        return p.chromium.launch(executable_path=path)
    try:
        return p.chromium.launch(channel="chrome")
    except Exception:
        return p.chromium.launch()


def settle(page: Page) -> None:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)  # animações de entrada


def shot(page: Page, url: str, name: str) -> bytes:
    page.goto(url)
    settle(page)
    if name == "00_inicio":  # dispara as animações de rolagem antes da captura da página inteira
        page.evaluate("async () => { for (let y = 0; y < document.body.scrollHeight; y += 400) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); } window.scrollTo(0, 0); }")
        page.wait_for_timeout(1500)
    png = page.screenshot(full_page=name in {"00_inicio", "01_documentos", "06_avaliacao"})
    (OUT / f"{name}.png").write_bytes(png)
    print(f"docs/img/{name}.png")
    return page.screenshot()  # quadro do GIF sempre no tamanho da janela


def make_gif(frames: list[bytes], path: Path, hold_ms: int = 1800, width: int = 960) -> None:
    imgs = []
    for f in frames:
        im = Image.open(io.BytesIO(f)).convert("RGB")
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        imgs.append(im.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    imgs[0].save(path, save_all=True, append_images=imgs[1:], duration=hold_ms, loop=0, optimize=True)
    print(f"docs/img/{path.name} ({path.stat().st_size // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", help="id do documento (padrão: o do Itaú, se houver)")
    ap.add_argument("--app", default="http://localhost:5173")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--tema", choices=["light", "dark"], default="light")
    ap.add_argument("--detalhe", default="iniciante/texto", help="célula da tela de detalhe (nível/formato)")
    ap.add_argument("--reflection", default="intermediario/texto", help="célula da aba Reflection (nível/formato)")
    args = ap.parse_args()
    doc = args.doc or pick_doc(args.api)
    OUT.mkdir(parents=True, exist_ok=True)
    base = f"{args.app}/docs/{doc}"

    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport=VIEWPORT, color_scheme=args.tema, locale="pt-BR")
        shot(page, f"{args.app}/", "00_inicio")
        shot(page, f"{args.app}/documentos", "01_documentos")
        gif = [
            shot(page, base, "02_matriz"),
            shot(page, f"{base}?view=comparar", "03_comparar_niveis"),
            shot(page, f"{base}/{args.detalhe}", "04_detalhe"),
            shot(page, f"{base}/{args.reflection}?aba=reflection", "05_reflection"),
        ]
        # um quadro a mais no reflection, rolado até o diff
        page.mouse.wheel(0, 700)
        page.wait_for_timeout(500)
        gif.append(page.screenshot())
        shot(page, f"{args.app}/avaliacao", "06_avaliacao")
        browser.close()
    make_gif(gif, OUT / "demo.gif")


if __name__ == "__main__":
    main()
