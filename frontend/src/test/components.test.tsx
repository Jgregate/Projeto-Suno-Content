import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import { MetricBar } from "@/components/MetricBar";
import { TermHighlight } from "@/components/TermHighlight";
import { MatrixGrid } from "@/features/MatrixGrid";
import { segmentTerms } from "@/lib/terms";
import { occurrence, results } from "./fixtures";

describe("MatrixGrid", () => {
  it("renderiza as 9 células, com status em texto", () => {
    render(<MemoryRouter><MatrixGrid results={results} docId="doc" /></MemoryRouter>);
    const cells = screen.getAllByTestId("matrix-cell");
    expect(cells).toHaveLength(9);
    expect(within(cells[0]).getByText("Aprovado")).toBeInTheDocument();
    expect(screen.getAllByText("Reprovado").length).toBeGreaterThan(0);
    expect(cells[0]).toHaveAttribute("href", "/docs/doc/iniciante/texto?run=doc__1");
  });
});

describe("MetricBar", () => {
  const group = () => screen.getByRole("group");

  it("passa quando o valor atende ao mínimo", () => {
    render(<MetricBar name="flesch_pt" value={72} bound={{ min: 60, max: null }} />);
    expect(group()).toHaveAttribute("data-passed", "true");
    expect(screen.getByText("Passou")).toBeInTheDocument();
  });

  it("falha abaixo do mínimo e acima do máximo", () => {
    const { rerender } = render(<MetricBar name="flesch_pt" value={38} bound={{ min: 60, max: null }} />);
    expect(group()).toHaveAttribute("data-passed", "false");
    expect(screen.getByText("Falhou")).toBeInTheDocument();
    rerender(<MetricBar name="term_density" value={3.2} bound={{ min: null, max: 2 }} />);
    expect(group()).toHaveAttribute("data-passed", "false");
  });

  it("respeita faixa (min e max) e a borda conta como aprovado", () => {
    const { rerender } = render(<MetricBar name="flesch_pt" value={60} bound={{ min: 40, max: 60 }} />);
    expect(group()).toHaveAttribute("data-passed", "true");
    rerender(<MetricBar name="flesch_pt" value={61} bound={{ min: 40, max: 60 }} />);
    expect(group()).toHaveAttribute("data-passed", "false");
  });

  it("sem limiar é informativa (não passa nem falha)", () => {
    render(<MetricBar name="flesch_pt" value={20} bound={{ min: null, max: null }} />);
    expect(group()).toHaveAttribute("data-passed", "info");
  });
});

describe("TermHighlight", () => {
  const text = "O hiato do produto ficou positivo. A Selic, ou seja, o juro básico, caiu.";
  const occ = [
    occurrence("hiato do produto", "hiato do produto", "O hiato do produto ficou positivo.", false),
    occurrence("Selic", "Selic", "A Selic, ou seja, o juro básico, caiu.", true),
  ];

  it("segmenta o texto nos termos encontrados", () => {
    const segs = segmentTerms(text, occ);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs.filter((s) => s.occurrence).map((s) => s.text)).toEqual(["hiato do produto", "Selic"]);
  });

  it("marca termo sem contexto e termo contextualizado de forma diferente", () => {
    render(<TermHighlight text={text} occurrences={occ} glossary={new Map()} />);
    const missing = document.querySelector('[data-term-status="sem-contexto"]');
    const ok = document.querySelector('[data-term-status="contextualizado"]');
    expect(missing).toHaveTextContent("hiato do produto");
    expect(missing).toHaveTextContent("termo técnico sem explicação");
    expect(ok).toHaveTextContent("Selic");
  });

  it("não marca nada quando não há termos", () => {
    render(<TermHighlight text="Texto sem jargão." occurrences={[]} glossary={new Map()} />);
    expect(document.querySelector("[data-term-status]")).toBeNull();
  });
});
