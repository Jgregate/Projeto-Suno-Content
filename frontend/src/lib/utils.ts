import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...inputs: ClassValue[]) => twMerge(clsx(inputs));

export const fmtNumber = (n: number, digits = 1) =>
  n.toLocaleString("pt-BR", { maximumFractionDigits: digits, minimumFractionDigits: 0 });

export const fmtPct = (n: number, digits = 0) => `${fmtNumber(n * 100, digits)}%`;

export const fmtMs = (ms: number) => (ms >= 1000 ? `${fmtNumber(ms / 1000, 1)} s` : `${Math.round(ms)} ms`);

export const fmtUsd = (n: number) => `US$ ${n.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
