/** Rodapé no padrão de suno.com.br: marca, três colunas de links, redes sociais e aviso legal. */
const SUNO = "https://www.suno.com.br/";

const COLUMNS: { title: string; links: string[] }[] = [
  { title: "Menu", links: ["Institucional", "Política de Privacidade", "Política de Cookies", "Código de Conduta e Ética", "Termos de Uso"] },
  { title: "Suno", links: ["Login", "Assinaturas", "Seja Suno One"] },
  { title: "Atendimento", links: ["Fale conosco", "Imprensa", "Canal de Denúncia", "Trabalhe Conosco"] },
];

const SOCIAL = ["Facebook", "X", "Instagram", "YouTube"];

export function SiteFooter() {
  return (
    <footer className="bg-[#131313] text-[#bdbdbd]" style={{ colorScheme: "dark" }}>
      <div className="mx-auto grid max-w-[1320px] gap-12 px-8 pb-10 pt-16 md:grid-cols-[1.2fr_repeat(3,1fr)]">
        <div className="flex flex-col gap-5">
          <a href={SUNO} target="_blank" rel="noreferrer" aria-label="Suno (site oficial)" className="flex w-fit items-center text-3xl leading-none">
            <span className="font-light text-[#ec3f44]">(</span>
            <span className="px-2 text-lg uppercase tracking-[0.3em] text-white">Suno</span>
            <span className="font-light text-[#ec3f44]">)</span>
          </a>
          <p className="max-w-[32ch] text-sm leading-relaxed">
            Suno Content: adaptação de documentos financeiros públicos para três níveis de investidor, com avaliação medida.
          </p>
        </div>
        {COLUMNS.map((c) => (
          <nav key={c.title} aria-label={c.title} className="flex flex-col gap-3">
            <span className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-white">{c.title}</span>
            <ul className="flex flex-col gap-2 text-sm">
              {c.links.map((l) => (
                <li key={l}>
                  <a href={SUNO} target="_blank" rel="noreferrer" className="transition-colors hover:text-white">{l}</a>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center justify-between gap-4 border-t border-white/10 px-8 py-6">
        <ul className="flex flex-wrap gap-5 text-sm">
          {SOCIAL.map((s) => (
            <li key={s}>
              <a href={SUNO} target="_blank" rel="noreferrer" className="hover:text-white">{s}</a>
            </li>
          ))}
        </ul>
        <span className="text-[11px] font-extrabold uppercase tracking-[0.1em] text-[#8b8b8b]">Case Inteli Academy × Finance</span>
      </div>
      <div className="mx-auto max-w-[1320px] border-t border-white/10 px-8 py-8 text-xs leading-relaxed text-[#8b8b8b]">
        <p className="max-w-[110ch]">
          Os conteúdos gerados por este sistema têm caráter educativo e não constituem recomendação, oferta ou aconselhamento de
          investimento. Os números vêm dos documentos públicos citados em cada conteúdo (BCB, CVM e relações com investidores) e devem ser
          conferidos na fonte. Protótipo acadêmico desenvolvido para o case Suno Content; não é um produto oficial da Suno.
        </p>
        <p className="mt-4">© 2026 Suno Content · protótipo acadêmico. Suno é marca de Suno S.A.</p>
      </div>
    </footer>
  );
}
