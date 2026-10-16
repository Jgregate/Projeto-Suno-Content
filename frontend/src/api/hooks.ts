import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import type { Audience, Format } from "./types";

export const useDocuments = () =>
  useQuery({ queryKey: ["documents"], queryFn: async () => unwrap(await api.GET("/documents")) });

export const useGlossary = () =>
  useQuery({ queryKey: ["glossary"], queryFn: async () => unwrap(await api.GET("/glossary")), staleTime: Infinity });

export const useThresholds = () =>
  useQuery({ queryKey: ["thresholds"], queryFn: async () => unwrap(await api.GET("/thresholds")), staleTime: Infinity });

export const useSummary = () =>
  useQuery({ queryKey: ["summary"], queryFn: async () => unwrap(await api.GET("/reports/summary")) });

export const useExperiment = () =>
  useQuery({ queryKey: ["experiment"], queryFn: async () => unwrap(await api.GET("/reports/experiment")), staleTime: Infinity });

export const useAnchors = (docId: string, enabled = true) =>
  useQuery({
    queryKey: ["anchors", docId],
    enabled,
    retry: false,
    queryFn: async () => unwrap(await api.GET("/documents/{doc_id}/anchors", { params: { path: { doc_id: docId } } })),
  });

/** run_id da execução mais recente do documento (a resposta de âncoras já o traz). */
export function useLatestRunId(docId: string, explicit: string | null) {
  const anchors = useAnchors(docId, !explicit);
  return { runId: explicit ?? anchors.data?.run_id ?? null, isLoading: !explicit && anchors.isLoading, error: anchors.error };
}

export const useResults = (runId: string | null) =>
  useQuery({
    queryKey: ["results", runId],
    enabled: !!runId,
    staleTime: Infinity,
    queryFn: async () => unwrap(await api.GET("/runs/{run_id}/results", { params: { path: { run_id: runId! } } })),
  });

export const useCellTerms = (runId: string | null, audience: Audience, format: Format, attempt?: number) =>
  useQuery({
    queryKey: ["terms", runId, audience, format, attempt],
    enabled: !!runId,
    staleTime: Infinity,
    queryFn: async () =>
      unwrap(
        await api.GET("/runs/{run_id}/cells/{audience}/{fmt}/terms", {
          params: { path: { run_id: runId!, audience, fmt: format }, query: attempt ? { attempt } : {} },
        }),
      ),
  });

/** Polling do status a cada 1 s até concluir ou falhar. */
export const useRunStatus = (runId: string | null) =>
  useQuery({
    queryKey: ["run", runId],
    enabled: !!runId,
    queryFn: async () => unwrap(await api.GET("/runs/{run_id}", { params: { path: { run_id: runId! } } })),
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1000),
  });

export function useStartRun() {
  return useMutation({
    mutationFn: async (body: { doc_id: string; force?: boolean; force_drift?: Audience | null }) =>
      unwrap(await api.POST("/runs", { body: { ...body, force: body.force ?? false } })),
  });
}

export function useUpload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      // openapi-fetch serializa JSON por padrão; multipart vai com bodySerializer próprio
      return unwrap(await api.POST("/documents", { body: form as unknown as never, bodySerializer: (b) => b as unknown as FormData }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });
}
