import { BarChart3, FileText } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router";
import { SiteFooter } from "@/components/SiteFooter";
import { ThemeToggle } from "@/components/ThemeToggle";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/documentos", label: "Documentos", icon: FileText, end: true },
  { to: "/avaliacao", label: "Avaliação", icon: BarChart3, end: false },
];

/** Marca "( SUNO )" com o descritor do produto; leva à página inicial. */
export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-3" aria-label="Suno Content: início">
      <span aria-hidden className="flex items-center text-2xl leading-none">
        <span className="font-light text-brand">(</span>
        <span className="px-1.5 text-[15px] font-normal uppercase tracking-[0.3em] text-ink">Suno</span>
        <span className="font-light text-brand">)</span>
      </span>
      <span className="hidden border-l border-line pl-3 text-[11px] font-extrabold uppercase tracking-[0.1em] text-ink-3 lg:inline">
        conteúdo financeiro por nível
      </span>
    </Link>
  );
}

export function AppShell() {
  return (
    <div className="flex min-h-dvh flex-col">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-3 focus:py-2">
        Pular para o conteúdo
      </a>
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1320px] items-center gap-10 px-8">
          <Logo />
          <nav aria-label="Principal" className="flex h-full items-stretch gap-6">
            {nav.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "inline-flex items-center gap-2 border-b-[3px] pt-[3px] text-xs font-extrabold uppercase tracking-[0.08em] transition-colors",
                    isActive ? "border-brand text-ink" : "border-transparent text-ink-3 hover:text-brand",
                  )
                }
              >
                <Icon aria-hidden className="size-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <ThemeToggle />
          </div>
        </div>
      </header>
      <main id="conteudo" className="mx-auto w-full max-w-[1320px] flex-1 px-8 pb-24 pt-10">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}

export function PageHeader({ eyebrow, title, children, actions }: { eyebrow?: string; title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-6 border-b border-line pb-8">
      <div className="flex max-w-3xl flex-col gap-2">
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1 className="text-4xl font-bold leading-tight tracking-tight text-ink">{title}</h1>
        {children && <div className="text-ink-2">{children}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
