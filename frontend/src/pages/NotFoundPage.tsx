import { Link } from "react-router";
import { EmptyState } from "@/components/States";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <EmptyState title="Página não encontrada" action={<Button asChild variant="secondary"><Link to="/documentos">Voltar aos documentos</Link></Button>}>
      O endereço não corresponde a nenhuma tela. Talvez o link tenha mudado.
    </EmptyState>
  );
}
