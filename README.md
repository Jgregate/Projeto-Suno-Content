# Suno Content

**Adaptação de documentos financeiros para três níveis de investidor e três formatos, com um avaliador híbrido que mede cada saída.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-1C3C3C)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Testes](https://img.shields.io/badge/testes-150%20passando-2EA44F)
![Licença](https://img.shields.io/badge/licen%C3%A7a-MIT-blue)

Desenvolvido no case **Suno Content** (Academy × Finance, Inteli). A documentação completa, com arquitetura, métricas, decisões, resultados e testes, está em [`docs/documentacao.md`](docs/documentacao.md).

## Problema

Atas do Copom, fatos relevantes e releases de resultados são escritos em linguagem técnica e densa, que afasta investidores iniciantes e intermediários. Pedir a um LLM que "resuma para iniciantes" falha de duas formas: o modelo encurta frases e troca palavras, perdendo nuances ou inventando números, e a qualidade costuma ser julgada por outro prompt, que tende a aprovar o que soa bem, favorece textos longos e não mede quanto jargão ficou sem explicação.

## Solução

Um pipeline em grafo transforma cada documento em nove conteúdos (Iniciante, Intermediário e Avançado × texto analítico, carrossel e roteiro de vídeo de até 60 s). Todo número parte de uma âncora factual validada contra a fonte, e cada saída passa por um avaliador híbrido: primeiro métricas determinísticas (legibilidade Flesch em português, densidade e contextualização de termos técnicos, números sem correspondência na fonte), depois LLM com temperatura 0 para checar afirmações e dar notas com evidência literal. As saídas reprovadas voltam para reescrita com feedback numérico, em até três tentativas. Um dashboard mostra a matriz de saídas, a origem de cada afirmação, o histórico de correções e a telemetria do avaliador.

| Camada | Stack |
|---|---|
| Orquestração | LangGraph (`StateGraph` com fan-out paralelo), LangChain |
| Modelos | Groq (`gpt-oss-20b`, `gpt-oss-120b`, `qwen3.8-27b`); outros provedores via `.env` |
| Avaliação | spaCy `pt_core_news_lg`, pyphen, Flesch PT próprio, pytest |
| Dados | PyMuPDF, httpx (APIs do BCB e da CVM), pandas, matplotlib |
| Interface | FastAPI, React 19, Vite, TypeScript, Tailwind, TanStack Query, Recharts |

## Estrutura de pastas

```
.github/workflows/   integração contínua
backend/
  ingestion/         coleta e leitura de PDFs
  schemas/           contratos de dados
  prompts/           prompts versionados
  graph/             montagem do grafo
  nodes/             nós do grafo
  evaluator/         avaliador híbrido
  reflection/        loop de correção
  experiments/       baseline e experimento
  api/               API FastAPI
frontend/            dashboard React
data/                documentos e glossário
outputs/             execuções e resultados
docs/                documentação e imagens
notebooks/           calibração dos limiares
scripts/             demo, capturas e números
tests/               testes automatizados
```

## O que é cada pasta

**`.github/workflows/`** roda lint, testes e build a cada push. **`backend/`** é o núcleo em Python: `ingestion/` baixa atas do Copom (API do Banco Central) e fatos relevantes (dados abertos da CVM) e extrai o texto dos PDFs por página; `schemas/` define em Pydantic os contratos de documento, âncoras, conteúdo, avaliação e estado do grafo; `prompts/` guarda um prompt por nó e as regras de cada nível; `graph/` monta o `StateGraph`; `nodes/` tem o extractor, os adapters, os formatters, o avaliador e o refiner; `evaluator/` reúne as métricas, o glossário, os limiares e o judge; `reflection/` gera a demonstração do loop e as estatísticas; `experiments/` roda o baseline, o experimento completo e a concordância com a revisão humana; e `api/` expõe as execuções para o dashboard. Na raiz de `backend/` ficam a configuração, o cliente de LLM e o CLI do pipeline.

**`frontend/`** é o dashboard (página inicial, documentos, matriz 3×3, detalhe com rastreabilidade, loop de correção e avaliação). **`data/`** guarda os PDFs baixados (fora do git), o texto processado e o glossário de termos financeiros. **`outputs/`** guarda cada execução do pipeline (o que permite abrir o dashboard sem chamar o LLM) e o experimento completo, com CSVs, figuras e relatório. **`docs/`** tem a documentação completa, as capturas de tela, os resultados e o diagrama de arquitetura. **`notebooks/`** confere os limiares no conjunto golden. **`scripts/`** sobe a demonstração com um comando, gera as capturas de tela e leva os números do experimento para a documentação. **`tests/`** tem 150 testes offline, com LLM e HTTP falsos, e o conjunto golden de textos escritos à mão.

## Como abrir o dashboard

É preciso Python 3.11+, [uv](https://docs.astral.sh/uv/) e Node.js 20.19+ ou 22. O dashboard abre com as execuções já gravadas, sem chave de API.

```bash
uv sync --all-extras
cd frontend && npm ci && cp .env.example .env && cd ..
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
```

Depois, suba a API e o frontend em dois terminais, a partir da raiz do projeto:

```bash
uv run uvicorn backend.api.main:app --port 8000                   # terminal 1: API
cd frontend && npm run dev -- --port 5173 --strictPort            # terminal 2: dashboard
```

Abra **http://localhost:5173**. Como atalho, `powershell -ExecutionPolicy Bypass -File scripts\demo.ps1 -SkipTests` (Windows) ou `scripts/demo.sh` (macOS e Linux) instalam, sobem tudo e abrem o navegador. Para gerar conteúdo novo, preencha no `.env` os modelos e a chave do provedor e siga a seção [Como usar](docs/documentacao.md#2-como-usar) da documentação.

Licença: [MIT](LICENSE).
