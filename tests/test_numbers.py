from decimal import Decimal

import pytest

from backend.evaluator.numbers import extract_numbers, missing_numbers, number_index
from backend.nodes.extractor import validate_anchor_numbers
from backend.schemas import ExtractionResult, FactualAnchor

SOURCE = (
    "O lucro líquido recorrente foi de R$ 12.407 milhões, ou R$ 12,4 bilhões, com ROE de 24,3%. "
    "A Selic caiu 0,50 p.p., para 13,75% a.a. JCP de R$ 0,2120 por ação. Ativos de R$ 3.412.598,7 mil."
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("R$ 12,4 bilhões", [Decimal("12.4")]),
        ("12.407", [Decimal("12407")]),
        ("24,3%", [Decimal("24.3")]),
        ("0,50 p.p.", [Decimal("0.5")]),
        ("13,75% a.a.", [Decimal("13.75")]),
        ("R$ 3.412.598,7 mil", [Decimal("3412598.7")]),
        ("15,00%", [Decimal("15")]),
    ],
)
def test_extract_brazilian_numbers(raw, expected):
    assert extract_numbers(raw) == expected


def test_equivalent_forms_match():
    index = number_index(SOURCE)
    assert missing_numbers(["R$ 12,4 bi", "12.407", "24,30%", "-0,5 p.p.", "R$ 0,212"], index) == []


def test_missing_numbers_reported():
    index = number_index(SOURCE)
    assert missing_numbers(["25,1%", "24,3%", "R$ 13 bilhões"], index) == ["25,1%", "R$ 13 bilhões"]


def test_text_without_digits_is_not_checked():
    assert missing_numbers(["dois terços"], number_index(SOURCE)) == []


def test_validate_anchor_numbers_marks_invalid():
    extraction = ExtractionResult(
        key_points=["x"],
        anchors=[
            FactualAnchor(id="A01", claim="ok", numbers=["24,3%"], source_excerpt="ROE de 24,3%", page=1),
            FactualAnchor(id="A02", claim="errado", numbers=["24.3%"], source_excerpt="?", page=1),
        ],
    )
    warnings = validate_anchor_numbers(extraction, SOURCE)
    assert [a.id for a in extraction.valid_anchors] == ["A01"]
    assert extraction.anchors[1].invalid_numbers == ["24.3%"]
    assert len(warnings) == 1 and "A02" in warnings[0]


def test_validity_fields_hidden_from_llm_schema():
    props = FactualAnchor.model_json_schema()["properties"]
    assert "valid" not in props and "invalid_numbers" not in props
