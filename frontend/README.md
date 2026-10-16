# Frontend (Suno Content)

Interface de demonstração: documentos e upload, matriz 3×3, comparação de níveis, detalhe com rastreabilidade (afirmação → trecho da fonte), termos destacados, aba Reflection e painel de avaliação.

**Stack:** React 19, Vite 8, TypeScript, Tailwind 4, Radix/shadcn, TanStack Query, Recharts.

```bash
npm ci
cp .env.example .env      # VITE_API_URL=/api (proxy do Vite para http://127.0.0.1:8000)
npm run dev               # http://localhost:5173 (a API precisa estar rodando na porta 8000)
npm test                  # Vitest + Testing Library
npm run lint && npm run build
npm run gen:api           # regenera src/api/schema.d.ts a partir de openapi.json
```

| Pasta | Conteúdo |
|---|---|
| `src/pages/` | Documentos, Matriz, Detalhe, Avaliação |
| `src/features/` | matriz, comparação de níveis, visões de conteúdo, métricas e reflection |
| `src/components/` | componentes de UI (shadcn em `ui/`), destaque de termos, barra de métrica, status |
| `src/api/` | cliente tipado (`openapi-fetch`) e hooks do TanStack Query |
| `src/lib/` | regras de exibição (níveis, métricas, termos, diff) |

Rotas, proxy e geração do cliente estão descritos em [`docs/documentacao_tecnica.md`](../docs/documentacao_tecnica.md#11-frontend).
