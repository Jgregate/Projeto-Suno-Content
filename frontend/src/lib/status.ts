import type { CellStatus } from "@/api/types";

export function statusText(status: CellStatus | null | undefined): string {
  if (!status) return "Sem avaliação";
  if (status.status === "aprovado") return "Aprovado";
  if (status.status.startsWith("aprovado_apos")) return `Aprovado após ${status.attempts} tentativas`;
  return "Reprovado";
}

