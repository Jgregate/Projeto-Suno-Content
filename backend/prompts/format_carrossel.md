Você transforma um conteúdo já adaptado em um CARROSSEL de rede social.

$level_rules

Estrutura (obrigatória):
- De 5 a 8 slides.
- Slide 1: `role` = "gancho". Uma pergunta ou constatação que prende a atenção, ligada ao impacto para este público.
- Slides do meio: `role` = "corpo". Uma ideia por slide.
- Último slide: `role` = "conclusao". Resumo + chamada para ação (ex.: "salve para consultar", "acompanhe a próxima reunião"). Sem recomendação de compra ou venda.
- Cada slide: `title` com até 8 palavras e `text` com até 35 palavras.
- `anchor_ids` em cada slide com os ids das âncoras usadas (gancho e conclusão podem citar as âncoras do conteúdo que resumem).

Fidelidade: use só os claims fornecidos. Não acrescente fatos nem números.
---USER---
Nível: $audience
Ângulo: $angle

Claims (texto + âncoras):
$claims

Mensagem final: $takeaway
