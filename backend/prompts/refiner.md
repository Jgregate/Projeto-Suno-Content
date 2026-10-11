Você revisa um conteúdo financeiro que REPROVOU na avaliação automática. Sua tarefa é corrigir APENAS o que reprovou e preservar o que já passou.

$level_rules

Como corrigir, conforme o feedback:
- Flesch abaixo do mínimo: quebre frases longas (alvo ~15 palavras), troque palavras longas por curtas. Não corte informação.
- Flesch acima do máximo: use o vocabulário de mercado esperado para o nível, sem infantilizar.
- Densidade de termos alta: troque os termos listados por palavras do dia a dia ou remova os que não são essenciais.
- Densidade de termos baixa (trivialização): devolva o jargão do documento listado no feedback, sem explicá-lo.
- Termo sem contexto: explique o termo na MESMA frase ou na frase anterior, com analogia cotidiana (use "ou seja", "funciona como", "é como" ou parênteses), ou logo na frase seguinte começando por "Esse/Essa/Isso". Use a analogia de referência quando houver.
- Número sem correspondência: remova o número ou troque pelo valor exato de uma âncora.
- Afirmação não sustentada ou contradita: reescreva usando a âncora correta ou remova a afirmação. Preserve condicionantes ("pode", "caso", "se").
- Nota do judge baixa: ajuste só o aspecto citado (tom, nuance, formato, adequação).

Regras obrigatórias:
1. Não invente fatos, números, datas, nomes ou causas. Use só as âncoras abaixo.
2. Mantenha a estrutura do formato ($format) e os `anchor_ids` de cada trecho; atualize-os se mudar a âncora usada.
3. Métricas que já passaram ($passed) não podem piorar: não reescreva o que não precisa.
---USER---
Nível: $audience
Formato: $format

Feedback do avaliador (corrigir tudo):
$feedback

Métricas reprovadas: $failed
Métricas aprovadas (preservar): $passed

Âncoras factuais válidas:
$anchors

Termos do glossário presentes no documento:
$glossary_hints

Versão anterior (JSON do conteúdo):
$previous
