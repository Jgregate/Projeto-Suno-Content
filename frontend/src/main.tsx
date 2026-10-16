import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { AppShell } from "@/components/AppShell";
import { DetailPage } from "@/pages/DetailPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { LandingPage } from "@/pages/LandingPage";
import { MatrixPage } from "@/pages/MatrixPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { LoadingBlock } from "@/components/States";

// Recharts só é carregado na tela de Avaliação
const EvaluationPage = lazy(() => import("@/pages/EvaluationPage").then((m) => ({ default: m.EvaluationPage })));
import "./index.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } });

const router = createBrowserRouter([
  { path: "/", element: <LandingPage /> },
  {
    element: <AppShell />,
    children: [
      { path: "/documentos", element: <DocumentsPage /> },
      { path: "/docs/:docId", element: <MatrixPage /> },
      { path: "/docs/:docId/:level/:format", element: <DetailPage /> },
      { path: "/avaliacao", element: <Suspense fallback={<LoadingBlock rows={4} />}><EvaluationPage /></Suspense> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
