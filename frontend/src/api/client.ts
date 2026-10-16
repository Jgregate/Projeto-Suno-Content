import createClient from "openapi-fetch";
import type { paths } from "./schema";

// Padrão "/api": mesma origem do frontend, repassada pelo proxy do Vite para a API (:8000).
// Uma URL absoluta em VITE_API_URL (ex.: http://localhost:8000) chama a API direto e depende de CORS.
export const API_URL = import.meta.env.VITE_API_URL || "/api";

const baseUrl = /^https?:\/\//.test(API_URL) ? API_URL : new URL(API_URL, window.location.origin).href.replace(/\/$/, "");

export const api = createClient<paths>({ baseUrl });

/** Erro com mensagem já em português, vinda do `detail` da API quando existir. */
export class ApiError extends Error {}

export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) return result.data;
  const detail = (result.error as { detail?: unknown } | undefined)?.detail;
  throw new ApiError(typeof detail === "string" ? detail : `A API respondeu ${result.response.status}.`);
}
