"""Configuração central do projeto, lida do .env.

Os papéis de LLM (fast, strong, judge) ficam aqui como strings "provedor:modelo";
a resolução para um cliente concreto fica em `backend/llm.py`.
"""

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
# As chaves de API (GROQ_API_KEY, GOOGLE_API_KEY...) são lidas de os.environ pelos clientes do
# LangChain, por isso o .env é carregado no ambiente além de alimentar `Settings`.
load_dotenv(ROOT_DIR / ".env")
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
GLOSSARY_PATH = DATA_DIR / "glossary" / "glossario.yaml"
OUTPUTS_DIR = ROOT_DIR / "outputs"
PROMPTS_DIR = ROOT_DIR / "backend" / "prompts"
PRICES_PATH = ROOT_DIR / "backend" / "model_prices.yaml"
EVAL_PROMPTS_DIR = ROOT_DIR / "backend" / "evaluator" / "prompts"
BASELINE_PROMPTS_DIR = ROOT_DIR / "backend" / "experiments" / "prompts"
THRESHOLDS_PATH = ROOT_DIR / "backend" / "evaluator" / "thresholds.yaml"
REPORTS_DIR = OUTPUTS_DIR / "reports"
REFERENCE_DIR = DATA_DIR / "reference"


class Settings(BaseSettings):
    """Variáveis de ambiente do pipeline."""

    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    llm_fast_model: str = "provider:model-name"
    """Modelo barato/rápido: adaptadores de audiência e formatadores."""

    llm_strong_model: str = "provider:model-name"
    """Modelo mais forte: Document Extractor e LLM Judge."""

    llm_judge_model: str = ""
    """Modelo do LLM Judge e do checker de afirmações. Vazio = usa o strong.
    De preferência um modelo diferente do que gera o texto (reduz autoavaliação)."""

    llm_claims_model: str = ""
    """Modelo do checker de afirmações (fidelidade). Vazio = usa o do judge. Separar os dois divide o
    consumo de tokens entre cotas diferentes do provedor."""

    llm_temperature: float = 0.2
    llm_reasoning_effort: str = ""
    """Esforço de raciocínio ("low", "medium", "high") para modelos que aceitam o parâmetro (gpt-oss).
    Vazio = padrão do provedor. "low" corta boa parte dos tokens de saída e da latência."""
    max_retries: int = 3
    """Máximo de tentativas por célula nível x formato no reflection loop (inclui a 1ª)."""

    reflection_epsilon: float = 0.01
    """Parada antecipada: se a nota agregada subir menos que isso entre duas tentativas, para."""


settings = Settings()
