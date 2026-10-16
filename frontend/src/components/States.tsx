import { AlertCircle, Inbox } from "lucide-react";
import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-line-strong bg-surface px-6 py-14 text-center">
      <Inbox aria-hidden className="size-8 text-ink-3" />
      <h3 className="font-serif text-lg font-semibold">{title}</h3>
      {children && <p className="max-w-md text-sm text-ink-2">{children}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ title = "Não foi possível carregar", error, action }: { title?: string; error: unknown; action?: ReactNode }) {
  const message = error instanceof Error ? error.message : String(error);
  const offline = /fetch|network|Failed/i.test(message);
  return (
    <div role="alert" className="flex flex-col items-center gap-3 rounded-xl border border-bad/30 bg-bad-soft px-6 py-12 text-center">
      <AlertCircle aria-hidden className="size-8 text-bad" />
      <h3 className="font-serif text-lg font-semibold">{title}</h3>
      <p className="max-w-lg text-sm text-ink-2">
        {offline ? "A API não respondeu. Confira se o backend está rodando (uv run uvicorn backend.api.main:app --port 8000 --reload) na porta 8000 e reinicie o npm run dev se mudou o .env." : message}
      </p>
      {action}
    </div>
  );
}

export const LoadingBlock = ({ rows = 3 }: { rows?: number }) => (
  <div className="flex flex-col gap-3" aria-busy="true" aria-label="Carregando">
    {Array.from({ length: rows }, (_, i) => (
      <Skeleton key={i} className="h-24 w-full" />
    ))}
  </div>
);
