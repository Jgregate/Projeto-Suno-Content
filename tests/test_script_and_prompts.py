from backend.config import PROMPTS_DIR
from backend.nodes.formatter import check_script
from backend.prompts import USER_MARKER, load_prompt, prompts_hash, render
from backend.schemas import ScriptBlock, VideoScriptBody, count_words


def _script(words_per_block: int, hook_end: float = 3) -> VideoScriptBody:
    speech = " ".join(["juros"] * words_per_block)
    return VideoScriptBody(blocks=[
        ScriptBlock(start_s=0, end_s=hook_end, visual_hook="x", speech=speech),
        ScriptBlock(start_s=hook_end, end_s=60, visual_hook="y", speech=speech),
    ])


def test_count_words_handles_numbers_and_hyphens():
    assert count_words("A Selic caiu para 13,75% em pontos-base.") == 7  # "13,75%" conta como 1


def test_script_word_limit_boundary():
    assert check_script(_script(75)) == []          # 150 palavras: ok
    issues = check_script(_script(76))              # 152: estoura
    assert len(issues) == 1 and "152 palavras" in issues[0]


def test_script_hook_over_three_seconds():
    assert any("gancho" in i for i in check_script(_script(10, hook_end=5)))


def test_all_templated_prompts_render():
    common = {"level_rules": "R", "audience": "iniciante", "angle": "a", "claims": "c", "takeaway": "t"}
    render("extractor", doc_type="ata_copom", title="T", document="D")
    render("adapter", level_rules="R", audience="iniciante", key_points="k", anchors="a", glossary_hints="g")
    for fmt in ("texto", "carrossel", "roteiro"):
        system, user = render(f"format_{fmt}", **common)
        assert system and user


def test_every_node_prompt_has_user_section():
    for path in PROMPTS_DIR.glob("*.md"):
        if not path.stem.startswith("rules_"):
            assert USER_MARKER in path.read_text(encoding="utf-8"), path.name


def test_prompts_hash_is_stable_and_short():
    assert prompts_hash() == prompts_hash()
    assert len(prompts_hash()) == 12
    assert load_prompt("adapter")[0].template.startswith("Você")


def test_evaluator_prompts_render_and_live_outside_generation_hash():
    from backend.config import BASELINE_PROMPTS_DIR, EVAL_PROMPTS_DIR

    render("claims", EVAL_PROMPTS_DIR, anchors="a", text="t")
    for level in ("iniciante", "intermediario", "avancado"):
        rubric = load_prompt(f"rubric_{level}", EVAL_PROMPTS_DIR)[0].template
        render("judge", EVAL_PROMPTS_DIR, rubric=rubric, format_rules="f", audience=level, format="texto", key_points="k", text="t")
    render("naive", BASELINE_PROMPTS_DIR, audience="iniciante", format="carrossel", document="R$ 10")
    # mudar prompts do avaliador não invalida o cache da geração
    assert prompts_hash() != prompts_hash(EVAL_PROMPTS_DIR)
