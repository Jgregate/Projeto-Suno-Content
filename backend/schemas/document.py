"""Schemas do documento-fonte e do resultado da extração (âncoras factuais)."""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema


class DocumentType(StrEnum):
    """Tipos de documento suportados pelo pipeline."""

    COPOM_MINUTES = "ata_copom"
    MATERIAL_FACT = "fato_relevante"
    EARNINGS_RELEASE = "release_resultados"
    OTHER = "outro"


class Page(BaseModel):
    """Texto limpo de uma página, mantido para rastrear âncoras até a fonte."""

    number: int = Field(ge=1, description="Número da página (1-indexado).")
    text: str
    source_doc_id: str | None = Field(
        default=None, description="Documento de origem quando vários PDFs viram uma fonte única."
    )


class SourceDocument(BaseModel):
    """Documento financeiro público já ingerido e limpo."""

    id: str = Field(description="Identificador estável (slug do nome do arquivo).")
    doc_type: DocumentType = DocumentType.OTHER
    title: str
    date: dt.date | None = Field(default=None, description="Data de publicação, quando conhecida.")
    text: str = Field(min_length=1, description="Texto limpo do documento inteiro.")
    pages: list[Page] = Field(min_length=1)
    source_path: str | None = Field(default=None, description="Caminho do PDF original.")


class FactualAnchor(BaseModel):
    """Afirmação factual verificável, ligada ao trecho e à página de origem.

    É a unidade usada pelo Factuality & Grounding Checker: toda afirmação
    gerada deve poder ser mapeada para uma âncora.
    """

    id: str = Field(description="Ex.: 'A01'.")
    claim: str = Field(description="Afirmação em linguagem neutra.")
    numbers: list[str] = Field(
        default_factory=list,
        description="Números citados na afirmação, como aparecem na fonte (ex.: '15,00%').",
    )
    source_excerpt: str = Field(description="Trecho literal do documento que sustenta a afirmação.")
    page: int = Field(ge=1)

    # Preenchidos pela validação determinística, não pelo LLM (fora do JSON schema).
    valid: SkipJsonSchema[bool] = True
    invalid_numbers: SkipJsonSchema[list[str]] = Field(default_factory=list)


class KeyNumber(BaseModel):
    """Número-chave do documento (ex.: Selic, lucro líquido, guidance)."""

    label: str = Field(description="O que o número mede (ex.: 'Taxa Selic').")
    value: str = Field(description="Valor como aparece na fonte (ex.: '15,00% a.a.').")
    anchor_id: str | None = Field(default=None, description="Âncora que sustenta o número.")


class ExtractionResult(BaseModel):
    """Saída estruturada do Document Extractor & Anchor."""

    key_points: list[str] = Field(min_length=1, description="Pontos centrais do documento.")
    anchors: list[FactualAnchor] = Field(default_factory=list)
    key_numbers: list[KeyNumber] = Field(default_factory=list)

    @property
    def valid_anchors(self) -> list[FactualAnchor]:
        return [a for a in self.anchors if a.valid]
