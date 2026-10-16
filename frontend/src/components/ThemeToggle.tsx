import { Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

const KEY = "color-scheme";
const meta = () => document.querySelector<HTMLMetaElement>('meta[name="color-scheme"]');
const systemDark = () => window.matchMedia("(prefers-color-scheme: dark)").matches;
const rendered = (): "light" | "dark" => {
  const v = meta()?.content;
  return v === "light" || v === "dark" ? v : systemDark() ? "dark" : "light";
};

function subscribe(cb: () => void) {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) {
      const m = meta();
      if (m) m.content = e.newValue ?? "light dark";
      cb();
    }
  };
  mq.addEventListener("change", cb);
  window.addEventListener("storage", onStorage);
  window.addEventListener("color-scheme-change", cb);
  return () => {
    mq.removeEventListener("change", cb);
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("color-scheme-change", cb);
  };
}

/** Dois estados: sistema ou o oposto do sistema (voltar ao oposto remove a escolha salva). */
export function ThemeToggle() {
  const scheme = useSyncExternalStore(subscribe, rendered, () => "light");
  const toggle = () => {
    const target = scheme === "dark" ? "light" : "dark";
    const toSystem = target === (systemDark() ? "dark" : "light");
    const m = meta();
    if (m) m.content = toSystem ? "light dark" : target;
    try {
      if (toSystem) localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, target);
    } catch {
      /* armazenamento bloqueado: o tema vale só para esta aba */
    }
    window.dispatchEvent(new Event("color-scheme-change"));
  };
  return (
    <Button variant="ghost" size="icon" onClick={toggle} aria-label={scheme === "dark" ? "Usar tema claro" : "Usar tema escuro"}>
      {scheme === "dark" ? <Sun aria-hidden /> : <Moon aria-hidden />}
    </Button>
  );
}
