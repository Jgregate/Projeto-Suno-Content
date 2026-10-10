"""Schemas da matriz de saída: níveis, formatos, conteúdo adaptado e conteúdo gerado."""

import re
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

MAX_VIDEO_SECONDS = 60
MAX_SCRIPT_WORDS = 150
CAROUSEL_MIN_SLIDES = 5
CAROUSEL_MAX_SLIDES = 8

AnchorIds = Annotated[
    list[str], Field(default_factory=list, description="Ids das âncoras factuais que sustentam o trecho.")
]


class Audience(StrEnum):
    """Nível de sofisticação do público."""

    BEGINNER = "iniciante"
    INTERMEDIATE = "intermediario"
    ADVANCED = "avancado"


class Format(StrEnum):
    """Formato de mídia da saída."""

    ARTICLE = "texto"
    CAROUSEL = "carrossel"
    VIDEO_SCRIPT = "roteiro"


# --- Conteúdo adaptado (saída dos Audience Adapters, ainda sem formato) ---


class AdaptedClaim(BaseModel):
    """Uma afirmação reescrita para o nível, ligada às âncoras que a sustentam."""

    text: str = Field(min_length=1)
    anchor_ids: list[str] = Field(min_length=1, description="Ids das âncoras usadas. Obrigatório.")


class AdaptedContent(BaseModel):
    """Conteúdo do documento reescrito para um nível, independente do formato."""

    audience: Audience
    angle: str = Field(description="Ângulo editorial: por que isso importa para este público.")
    claims: list[AdaptedClaim] = Field(min_length=1)
    takeaway: str = Field(description="Mensagem final para o leitor deste nível.")


# --- Formatos ---


class Section(BaseModel):
    """Seção do texto analítico."""

    heading: str
    body: str = Field(min_length=1)
    anchor_ids: AnchorIds


class ArticleBody(BaseModel):
    """Texto analítico para web/newsletter: título, linha fina e seções."""

    kind: Literal["texto"] = "texto"
    title: str
    subtitle: str = Field(description="Linha fina: uma frase que resume a notícia.")
    sections: list[Section] = Field(min_length=1)

    def plain_text(self) -> str:
        parts = [self.title, self.subtitle] + [f"{s.heading}\n{s.body}" for s in self.sections]
        return "\n\n".join(parts)

    def anchor_ids(self) -> list[str]:
        return [a for s in self.sections for a in s.anchor_ids]


class Slide(BaseModel):
    """Um slide do carrossel: título curto e texto curto."""

    role: Literal["gancho", "corpo", "conclusao"]
    title: str
    text: str
    anchor_ids: AnchorIds


class CarouselBody(BaseModel):
    """Carrossel de 5 a 8 slides: gancho, corpo(s), conclusão/CTA."""

    kind: Literal["carrossel"] = "carrossel"
    slides: list[Slide] = Field(min_length=CAROUSEL_MIN_SLIDES, max_length=CAROUSEL_MAX_SLIDES)

    @model_validator(mode="after")
    def _roles(self) -> "CarouselBody":
        roles = [s.role for s in self.slides]
        if roles[0] != "gancho" or roles[-1] != "conclusao" or any(r != "corpo" for r in roles[1:-1]):
            raise ValueError("Ordem esperada: 'gancho', depois só 'corpo', e por último 'conclusao'.")
        return self

    def plain_text(self) -> str:
        return "\n\n".join(f"{s.title}\n{s.text}" for s in self.slides)

    def anchor_ids(self) -> list[str]:
        return [a for s in self.slides for a in s.anchor_ids]


class ScriptBlock(BaseModel):
    """Bloco do roteiro com marcação de tempo em segundos."""

    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    visual_hook: str = Field(description="Indicação visual (texto na tela, gráfico, corte).")
    speech: str = Field(description="Fala do apresentador neste bloco.")
    anchor_ids: AnchorIds

    @model_validator(mode="after")
    def _ordered(self) -> "ScriptBlock":
        if self.end_s <= self.start_s:
            raise ValueError("end_s deve ser maior que start_s.")
        return self


def count_words(text: str) -> int:
    return len(re.findall(r"\d+(?:[.,]\d+)*%?|\w+(?:[-']\w+)*", text))


class VideoScriptBody(BaseModel):
    """Roteiro de vídeo curto (até 60 s), blocos em ordem cronológica.

    O limite de 60 s é estrutural (rejeita). O limite de ~150 palavras de fala
    é checado à parte e só registrado, para não descartar a saída.
    """

    kind: Literal["roteiro"] = "roteiro"
    blocks: list[ScriptBlock] = Field(min_length=1)

    @model_validator(mode="after")
    def _timeline(self) -> "VideoScriptBody":
        for prev, curr in pairwise(self.blocks):
            if curr.start_s < prev.end_s:
                raise ValueError("Blocos do roteiro não podem se sobrepor.")
        if self.blocks[-1].end_s > MAX_VIDEO_SECONDS:
            raise ValueError(f"Roteiro excede {MAX_VIDEO_SECONDS} s.")
        return self

    @property
    def word_count(self) -> int:
        return sum(count_words(b.speech) for b in self.blocks)

    def plain_text(self) -> str:
        return "\n".join(b.speech for b in self.blocks)

    def anchor_ids(self) -> list[str]:
        return [a for b in self.blocks for a in b.anchor_ids]


ContentBody = Annotated[ArticleBody | CarouselBody | VideoScriptBody, Field(discriminator="kind")]


def cell_key(audience: Audience, fmt: Format) -> str:
    """Chave de uma célula da matriz 3 x 3, ex.: 'iniciante:carrossel'."""
    return f"{audience.value}:{fmt.value}"


class GeneratedContent(BaseModel):
    """Saída de uma célula nível x formato em uma tentativa."""

    audience: Audience
    format: Format
    attempt: int = Field(ge=1, description="Número da tentativa (1 = primeira geração).")
    content: ContentBody
    anchor_ids: list[str] = Field(
        default_factory=list, description="Âncoras factuais usadas, para rastreabilidade."
    )
    warnings: SkipJsonSchema[list[str]] = Field(
        default_factory=list, description="Checagens determinísticas que falharam sem rejeitar a saída."
    )

    @model_validator(mode="after")
    def _format_matches_body(self) -> "GeneratedContent":
        if self.content.kind != self.format.value:
            raise ValueError(f"Formato '{self.format}' incompatível com conteúdo '{self.content.kind}'.")
        return self

    @property
    def key(self) -> str:
        return cell_key(self.audience, self.format)

    def plain_text(self) -> str:
        """Texto corrido usado pelas métricas determinísticas."""
        return self.content.plain_text()
