"""Script que leva os números dos CSVs para README e roteiro."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("preencher", Path(__file__).parents[1] / "scripts" / "preencher_numeros.py")
preencher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preencher)


def test_fill_inline_and_block_is_idempotent():
    text = "A <!--n:a-->?<!--/n--> e <!--n:b-->?<!--/n-->\n<!--t:tab-->\nvelho\n<!--/t:tab-->\n"
    new, missing = preencher.fill(text, {"a": "56%"}, {"tab": "| x |\n|---|"})
    assert "<!--n:a-->56%<!--/n-->" in new
    assert "<!--n:b-->a calcular<!--/n-->" in new and missing == {"b"}
    assert "velho" not in new and "| x |" in new
    assert preencher.fill(new, {"a": "56%"}, {"tab": "| x |\n|---|"})[0] == new


def test_ptbr_format():
    assert preencher.pct(0.5556) == "56%"
    assert preencher.num(46656.0, 0) == "46.656"
    assert preencher.num(1.44, 2) == "1,44"
    assert preencher.usd(0).startswith("sem preço")
    assert preencher._bound({"min": 40, "max": 60}) == "40 a 60"
    assert preencher._bound({}) == "só reporta"
