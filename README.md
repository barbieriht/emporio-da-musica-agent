# Maestro — agente de atendimento da Empório da Música

Protótipo (Python) de um agente de atendimento por mensagens de texto para a **Empório da Música**,
loja fictícia de instrumentos musicais de Campo Grande/MS, feito para o Desafio Técnico AI Engineer da Artefact.

O **Maestro** conversa em português do Brasil, em tom informal mas profissional (como pede o manual da loja),
consulta preços, estoque, promoções e pedidos nos dados da loja, aplica as políticas do manual
(horários, pagamento, frete, trocas, garantia), registra reclamações e encaminhamentos para a equipe, e recusa com
educação o que foge do escopo. O que precisa estar certo (preços, prazos, parcelas, verificação de pedido, horário)
é código testado, não texto livre do modelo.

- Conversas de exemplo (com as ferramentas chamadas em cada turno): [`examples/`](examples/)
- Especificação que guiou o trabalho: [`SPEC.md`](SPEC.md) e [issue #1](https://github.com/barbieriht/emporio-da-musica-agent/issues/1)
- Como o projeto foi conduzido com o Claude Code e as skills `mattpocock-skills`: [seção abaixo](#skills-do-claude-code-usadas-mattpocock-skills)

## Como rodar

Requisitos: Python 3.12+ e [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/barbieriht/emporio-da-musica-agent.git
cd emporio-da-musica-agent
uv sync
cp .env.example .env        # preencha UMA chave de provedor (veja abaixo)
uv run python -m emporio_agent
```

Digite `sair` para encerrar. Para rodar os testes (não usam rede nem LLM real):

```bash
uv run pytest
```

### Provedor do modelo

O agente usa o `init_chat_model` do LangChain, então o provedor é escolhido por variáveis de ambiente (`.env`):

| Provedor | Variáveis | Observação |
|---|---|---|
| **Google Gemini** (padrão) | `GOOGLE_API_KEY` | Camada gratuita em <https://aistudio.google.com/apikey>. Modelo padrão fixado em `gemini-3.7-flash`. |
| **Groq** (alternativa) | `GROQ_API_KEY`, `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b` | Camada gratuita com limites: <https://console.groq.com/keys>. |

`LLM_PROVIDER` e `LLM_MODEL` sobrescrevem o padrão. **Nomes de modelo mudam e são aposentados** (o `gemini-2.5-flash`
já estava indisponível para contas novas durante o desenvolvimento, e um modelo Llama da Groq sugerido de memória
pelo assistente nem existia na chave): se der `404 model not found`, liste os modelos da sua chave e ajuste `LLM_MODEL`.
Se o provedor responder `503 high demand`, é sobrecarga temporária do modelo: tente de novo ou troque de modelo/provedor.

### Variáveis opcionais

| Variável | Efeito |
|---|---|
| `AGENT_TODAY=2026-02-20` | Os pedidos de exemplo são de 2025–2026; com a data real toda devolução já estaria fora do prazo. Esta variável simula a data **somente para a regra de devolução** (a consulta "loja aberta agora" e o aviso de fora do expediente usam sempre o relógio real). |
| `COMPLAINTS_FILE` | Onde reclamações e encaminhamentos são gravados (padrão: `complaints.jsonl` na raiz, ignorado pelo git). |

### Regerar os exemplos

```bash
uv run python scripts/record_examples.py            # todos
uv run python scripts/record_examples.py 04-devolucao-pedido-real
```

O script reproduz mensagens de cliente roteirizadas no agente real e salva as transcrições com as chamadas de
ferramenta. A saída varia um pouco a cada execução (é um LLM).

## Como o agente funciona

```
mensagem do cliente
      │
      ▼
 Agent.respond(session, mensagem)
      │  ├─ loop de ferramentas (máx. 5 chamadas ao modelo por mensagem)
      │  ├─ verificador: valores em R$ e datas da resposta final precisam vir das ferramentas
      │  └─ aviso de fora do expediente (só na 1ª resposta da sessão em que a loja está fechada)
      ▼
 LLM (system prompt do Maestro + histórico da sessão + definição das ferramentas)
      │ decide qual ferramenta chamar
      ▼
 ┌─────────┬──────────┬────────┬─────────┬────────────┐
 │ Catalog │ Policies │ Orders │ Returns │ Complaints │
 └─────────┴──────────┴────────┴─────────┴────────────┘
   CSVs      manual em   CSVs +   regra     arquivo
             seções .md  verific. pura      local
```

**As 11 ferramentas expostas ao modelo:**

| Ferramenta | O que faz |
|---|---|
| `search_products`, `get_product_details` | Busca no catálogo; detalhes (descrição, especificações, alternativas se indisponível) |
| `get_payment_options` | Por id de produto: PIX (5% só sem promoção), débito, boleto, parcelas, combinação de formas |
| `get_policy` | Seção do manual (loja, horários, pagamento, trocas, frete, promoções, atendimento, garantia, privacidade) |
| `get_installments`, `get_shipping_quote`, `is_store_open_now` | Parcelas de um valor, frete por cidade, loja aberta agora |
| `get_order_status`, `check_return_eligibility` | Pedido e devolução/troca, com verificação por telefone |
| `register_complaint`, `request_human_handoff` | Grava reclamação ou pedido de encaminhamento, com protocolo |

| Módulo | Responsabilidade |
|---|---|
| `agent.py` | `Agent.respond(session, mensagem)`: loop de ferramentas, histórico, limite de chamadas, rollback se o modelo falhar, aviso de fora do expediente, verificação das respostas, acesso das ferramentas à sessão |
| `grounding.py` | Extrai valores em R$ e datas de um texto e confere contra o que as ferramentas/cliente disseram |
| `prompt.py` | Persona (Maestro), regras de conduta e saudação inicial |
| `catalog.py` | Carrega produtos/categorias/promoções; busca, preço efetivo, disponibilidade, alternativas |
| `policies.py` | Seções do manual; parcelas, opções de pagamento, frete, "loja aberta agora" e aviso de fora do expediente (fuso America/Campo_Grande) |
| `orders.py` | Consulta de pedido: validação de formato, verificação por telefone e memória da verificação na sessão |
| `returns.py` | Elegibilidade de devolução/troca por motivo, prazo e status do pedido |
| `complaints.py` | Registro local (JSON Lines) de reclamações e encaminhamentos, com protocolo |
| `money.py` | Arredondamento comercial (meio para cima) com `Decimal` |
| `tools.py` | Camada fina que expõe os módulos como *tools* do LangChain, formatando respostas em português |
| `config.py`, `cli.py` | Seleção do provedor por env, relógio (`AGENT_TODAY`), montagem do agente, CLI de chat |

## Decisões técnicas e justificativas

**Abordagem: *function calling* com ferramentas determinísticas (sem RAG vetorial, sem agente de SQL).**
Os dados são pequenos (65 produtos, 19 pedidos, 49 clientes) e o manual tem ~8 páginas. Regras que precisam estar
certas (preço com promoção, janela de 7 dias, parcelas, frete, horário) são código testável, não texto para o modelo
interpretar. O LLM fica com o que ele faz bem: entender a pergunta, escolher a ferramenta e redigir a resposta no tom
da loja. Um agente de SQL geraria consultas livres sobre dados com regras de negócio escondidas (promoção ativa,
status que vale mais que estoque); ferramentas tipadas evitam isso e dão uma superfície pequena para testar.

**O que é código e o que é LLM (revisado depois de uma primeira versão).** Numa segunda rodada mapeei o que o modelo
ainda fazia "de cabeça" e movi para código o que podia ser determinístico: o **aviso de fora do expediente** (o manual
exige e antes só aparecia se o cliente perguntasse), o **desconto de PIX** (antes o modelo calculava), o **registro de
reclamações** (o prompt mandava "registrar", mas não havia ferramenta: o agente afirmava uma ação que não fazia), a
**validação de telefone e nº do pedido** e a **conferência de valores e datas da resposta final**. Ficaram com o LLM, de
propósito: entender linguagem livre, classificar o motivo da devolução e redigir. Descartei detectar "acessório" por
palavra-chave (colide com "Cordas Orquestrais", que é categoria vendida) e classificar intenção por regex.

**Framework: LangChain (modelos de chat e *tools*), com loop de agente próprio.** Escolhi LangChain/LangGraph, mas na
implementação só o LangChain se mostrou necessário: o loop (chamar modelo → executar ferramentas → devolver resultado,
mais o limite de chamadas e o verificador) cabe numa função curta, e escrevê-lo à mão deixou o ponto de teste simples
(basta injetar um modelo falso). LangChain continua útil pela troca de provedor por variável de ambiente e pela
definição das ferramentas. (Declarei `langgraph` no início e removi depois, por não ser usado.)

**Modelo e provedor: Gemini (padrão) e Groq (alternativa), ambos gratuitos.** Quem avalia precisa conseguir rodar sem
pagar; ambos têm camada gratuita e suportam *tool calling*. O modelo é fixado por versão (reprodutibilidade) e pode
ser trocado por env. Modelos locais (Ollama) foram descartados como padrão: o agente depende de chamar ferramentas
corretamente, onde modelos pequenos falham mais, e exigem hardware do avaliador.

**Estratégia de prompt.** O *system prompt* define persona e regras do manual: nunca informar preço, estoque ou prazo
sem consultar uma ferramenta; usar a ferramenta de pagamento em vez de calcular PIX/parcelas; mostrar preço original
junto do promocional; redirecionar acessórios (a loja só vende instrumentos); recusar assuntos fora da loja; não fazer
reservas nem pedidos (o agente só informa; para comprar, reservar ou cancelar usa o encaminhamento); pedir telefone e
nº do pedido só na primeira consulta; só dizer que registrou uma reclamação se a ferramenta confirmar; não inventar
etapas de processo nem características de produtos. A saudação inicial é um texto fixo (não gasta chamada de modelo e
funciona mesmo com o provedor instável), e o prompt avisa o modelo de que ele já se apresentou.

**Recuperação das políticas: seções em Markdown, consulta por tópico.** Converti o PDF uma vez em nove arquivos em
`data/policies/` (loja, horários, pagamento, trocas, frete, promoções, atendimento, garantia, privacidade). Assim o
projeto roda sem dependência de leitura de PDF, as seções são revisáveis e o agente recebe só o trecho relevante.
Com um manual maior eu passaria a embeddings; para 8 páginas, o custo e a incerteza não se justificam. (Risco: a
conversão é manual e pode divergir do PDF original, que continua no repositório.)

**Tratamento dos dados.** Os CSVs são carregados em memória na inicialização e nunca alterados. Normalizações: preços
numéricos, `specs` (JSON) em dicionário, busca sem acento/caixa e com plural simples ("violão" encontra "Violões"),
preço efetivo com a promoção ativa, disponibilidade derivada de status + estoque. **Dinheiro usa `Decimal` com
arredondamento comercial (meio para cima)**: ao conferir números achei que `799,90 × 0,95 = 759,905` saía `759,90`
por imprecisão de ponto flutuante, quando o correto comercial é `759,91`.

**Verificador de valores e datas da resposta final.** O LLM redige o texto e pode alterar ou inventar um valor. Depois
de cada resposta final, o código extrai os valores em R$ e as datas; cada um precisa aparecer nos resultados das
ferramentas da sessão ou nas mensagens do próprio cliente (formatos como `R$ 1.000,00`, `1000` e `1 000` são
equivalentes; datas valem pelo dia/mês, e pelo ano quando os dois lados o trazem). Valores derivados (somas,
diferenças) são **rejeitados** de propósito: as contas ficam nas ferramentas. Se algo não bate, o agente pede uma
reescrita uma vez, citando o valor problemático (nessa rodada ele pode chamar uma ferramenta); se falhar de novo, envia
uma mensagem segura sem valores, com o telefone e o WhatsApp da loja. A resposta rejeitada e o aviso de correção não
ficam no histórico.

**Privacidade e segurança dos dados de cliente.** Pedido só é mostrado com **número do pedido + telefone cadastrado**
(comparação só pelos dígitos); pedido inexistente, telefone errado e telefone de outro cliente dão a mesma resposta
genérica, sem revelar qual dado falhou. O e-mail não é usado porque um deles aparece em dois clientes.
Formatos são validados em código (telefone com DDD + 8/9 dígitos, nº de pedido inteiro positivo). Depois de uma
verificação bem-sucedida, a sessão lembra o telefone: expira após 10 minutos sem uso, com teto de 30 minutos desde que o
cliente informou o telefone, vale só para pedidos daquele cliente, e tentativas erradas nunca são lembradas (nem apagam
uma verificação válida). A regra vive em código (`Orders.lookup`), não no prompt, então o modelo não consegue pulá-la.
Reclamações e encaminhamentos guardam **só descrição e contato** (nunca a conversa), em `complaints.jsonl`, fora do git.

**Histórico de conversa.** Em memória, por sessão (`Session`). Persistir entre sessões não agrega ao protótipo de CLI.
Se o modelo falhar no meio de um turno, o histórico volta ao estado anterior (sem mensagem pendurada sem resposta).

**Interface: CLI.** O foco é o agente; um chat de terminal basta para avaliar.

**Estratégia de testes (163 testes, sem rede).** Testes só em fronteiras públicas acordadas, nunca em detalhes internos:
(1) `Agent.respond` com um modelo falso roteirizado (33 testes: histórico, loop de ferramentas, limite de chamadas,
persona, rollback, aviso de fora do expediente, contexto da sessão para as ferramentas, verificador de valores);
(2) as interfaces `Catalog` (26), `Policies` (51), `Orders` (31), `assess_return` (12) e `Complaints` (10) sobre os CSVs
reais ou arquivos temporários, com relógio e estado injetáveis. Os valores esperados vêm de literais conferidos nos
CSVs/manual, não recalculados pelo mesmo código. Ficam **fora** dos testes: a CLI, as camadas finas de *tools* e o
comportamento do LLM real (verificado manualmente e nos exemplos). Duas observações sobre a confiança nos testes:
fiz uma checagem de mutação no verificador (com ele desligado, 5 testes falham) e a execução com o modelo real achou
um *crash* que os testes unitários não pegaram (ver "Erros do assistente").

## Premissas assumidas

O enunciado pede para assumir interpretações razoáveis e documentá-las. As principais:

**Catálogo**
- Só promoções com `is_active=1` valem; se houver mais de uma ativa no mesmo produto, vale a maior (hoje não ocorre).
- **O status vence o estoque**: o produto 136 (descontinuado) mostra estoque 13 e o 130 (em breve) mostra estoque 2;
  ambos são tratados como indisponíveis.
- Busca por palavras (todas precisam aparecer) em nome, categoria e especificações; sem tolerância a erro de digitação.
  Até 10 resultados, ordenados por relevância → disponíveis antes → com desconto antes → menor preço.
  Produtos indisponíveis aparecem com sinalização.
- Filtros de preço usam o preço efetivo (já com promoção).
- Alternativas para um produto indisponível: mesma categoria, disponíveis, preço ±30%, mais próximos primeiro (até 3).
- Não ordeno por proximidade: há uma só loja e os produtos não têm localização.

**Políticas e pagamento**
- Contatos: telefone da loja (67) 3341-4444 e WhatsApp (67) 3321-4500 (o manual traz os dois em seções diferentes).
  E-mail `contato@emporiodamusica.com.br`; a tabela do §1.2 traz uma versão com acento, que não é um domínio válido.
- Parcelamento: com *n* parcelas, vale se `preço / n` atinge o mínimo da faixa (R$ 50 até 3x; R$ 80 de 4x a 6x;
  R$ 100 de 7x a 12x; o mínimo de R$ 50 também vale para 2x). Ex.: 3x a partir de R$ 150, 12x a partir de R$ 1.200.
- PIX: 5% sobre o preço de tabela, **só em produto sem promoção** (promoções não são cumulativas); a ferramenta recebe
  o id do produto e sabe sozinha se há promoção. Combinar formas de pagamento é permitido **a partir de R$ 2.000,
  inclusive** (o manual diz "acima de"; mesmo critério do frete).
- Frete: só a cidade de Campo Grande conta como "região metropolitana"; pedido de exatamente R$ 500 tem frete grátis
  (o manual diz "acima" e "abaixo"); fora dela o frete depende do CEP e o agente informa apenas os prazos.
- Feriados: considero os nacionais de data fixa; móveis (Carnaval, Sexta-feira Santa, Corpus Christi) e locais não
  entram, e o agente avisa para confirmar.
- Fora do expediente: o aviso com o horário de reabertura vem **antes** da resposta e **só uma vez por sessão** (na
  primeira resposta em que a loja está fechada); se a loja estava aberta e fechou no meio da conversa, aparece na
  primeira resposta seguinte.

**Pedidos e devoluções**
- Vale o `total_brl` registrado, nunca a soma dos itens a preços de hoje (nos pedidos 3 e 20 elas diferem).
- Os pedidos são considerados **compras online** (têm rastreio/entrega), então vale o arrependimento de 7 dias.
- Não há data de entrega real nos dados: uso `estimated_delivery` como data de recebimento. Pedido enviado ainda não
  começou a contar o prazo; pendente/confirmado não tem o que devolver; cancelado também não.
- Arrependimento e troca por preferência: 7 dias; **defeito: 30 dias contados do recebimento** (o manual diz "após a
  compra"; escolhi o recebimento por coerência com a garantia legal e para não consumir o prazo com o frete).
  Depois disso, a garantia legal de 90 dias (do recebimento) e a do fabricante, com a loja podendo intermediar.
- Itens personalizados ou "venda final" não são identificáveis nos dados: o agente manda confirmar com a equipe.
- "Hoje" é a data real do sistema, sobrescrevível por `AGENT_TODAY`.
- Verificação de pedido lembrada na sessão por 10 min de inatividade, teto de 30 min, escopo do telefone (todos os
  pedidos daquele cliente); sem listar pedidos só por telefone.

**Reclamações e encaminhamentos**
- Gravados localmente com protocolo sequencial, tipo (`complaint`/`handoff`), descrição, contato e horário; contato é
  obrigatório (sem ele nada é salvo e o agente pede). O retorno "em até 24 horas úteis" vem do manual, mas **não há
  mecanismo que o cumpra**: é só o registro.
- Se a gravação falhar, a ferramenta diz isso ao agente, que não pode afirmar que registrou.

## Limitações conhecidas

- **O LLM ainda pode embelezar o texto ao redor dos fatos.** Valores em R$ e datas são verificados, mas o resto não.
  No exemplo [`04`](examples/04-devolucao-pedido-real.md) o Maestro ainda diz que a equipe "vai gerar a etiqueta de
  postagem" e que o reembolso conta "após a loja receber o produto", o que o manual não diz. (Antes do verificador e
  das regras de prompt ele chegou a inventar lojas parceiras e a oferecer reservas.)
- **O verificador é limitado.** Cobre só valores em R$ e datas; não percentuais, número de parcelas ou prazos em dias.
  Rejeita também contas corretas feitas pelo modelo (decisão deliberada). **Não medi quantas respostas são reescritas**
  nem a taxa de falsos positivos: nos cinco cenários dos exemplos nenhuma caiu na mensagem segura, mas a amostra é pequena.
- **Sem avaliação automatizada do comportamento do LLM.** Os testes cobrem regras, o loop e o verificador, não a
  qualidade das respostas; os exemplos são uma amostra manual de uma execução.
- **Verificação de pedido ainda fraca para produção**: telefone + número do pedido, sem limite de tentativas (alguém
  poderia tentar combinações) e sem defesa específica contra *prompt injection*.
- **Reclamações em arquivo local**: sem fila, notificação à equipe, dono do caso nem prazo real; o arquivo guarda
  telefone/e-mail em texto simples, sem criptografia nem política de retenção (está fora do git, mas é dado pessoal).
- **Sem ações de negócio**: o agente só informa. Não reserva, cria nem cancela pedidos; registra e encaminha.
- **Busca simples**: sem tolerância a erros de digitação, sinônimos ou perguntas por faixa de uso
  ("um violão bom pra começar").
- **Histórico só em memória**; reiniciar a CLI zera a conversa e a verificação.
- **Dependência do provedor gratuito**: limites de taxa, sobrecarga (503) e modelos aposentados. A CLI mostra uma
  mensagem amigável quando o modelo falha, mas não troca de provedor sozinha.
- **Política copiada à mão do PDF** e **somente português**.
- Feriados móveis/locais e frete fora de Campo Grande não são calculados; "loja aberta agora" e o aviso de fora do
  expediente sempre usam o relógio real (não respeitam `AGENT_TODAY`).
- Os exemplos mostram catálogo, loja/horário, sem estoque + parcelamento, devolução e fora de escopo/privacidade; a
  memória de verificação, as reclamações, o aviso de fora do expediente e as opções de pagamento são cobertos por
  testes e por execuções manuais, mas não têm exemplo gravado (o desafio pede de 3 a 5 conversas).

**O que eu faria com mais tempo:** um conjunto de avaliação (cenários + LLM como juiz, medindo reescritas e falsos
positivos do verificador); estender o verificador a percentuais, parcelas e prazos; limite de tentativas e registro de
auditoria na verificação de pedidos; notificar a equipe nas reclamações e armazenar com política de retenção;
persistência de sessão e canal real (WhatsApp); busca com tolerância a erro de digitação e, se o manual crescer,
embeddings; fluxo de atendente humano de verdade para cancelamentos.

## Uso de assistentes de código

Usei **apenas o Claude Code** (CLI da Anthropic, modelo Sonnet), com o plugin de *skills* `mattpocock-skills`
(`to-spec`, `to-tickets`, `tdd`) para estruturar o trabalho. O fluxo, na prática:

1. **Especificação**: o Claude leu o PDF do desafio, os CSVs e o manual e escreveu o [`SPEC.md`](SPEC.md)
   (problema, histórias de usuário, decisões, testes, fora de escopo), publicado como issue #1.
2. **Tickets**: a especificação virou 7 issues no GitHub, em fatias verticais com dependências explícitas
   (esqueleto com persona → catálogo → políticas → pedidos → devoluções → exemplos → README).
3. **Por ticket, TDD**: antes de qualquer teste, o Claude propunha a **fronteira de teste** e eu confirmava. Depois,
   um ciclo por vez: teste que falha → código mínimo → próximo teste. Sempre que havia uma decisão de produto, ele
   me perguntava em vez de escolher sozinho.
4. **Verificação real**: eu rodava a CLI com o modelo real e colava a saída; o Claude ajustava a partir disso.
5. **Segunda rodada (endurecimento)**: perguntei ao Claude quais tarefas do LLM poderiam virar código. Ele mapeou dez,
   com valor e esforço, e eu concordei com a ordem proposta; viraram mais seis issues (#9 a #14), seguindo o mesmo fluxo.

**O que decidi eu:** provedor gratuito e modelo (Gemini 3.7 Flash fixado; depois pedi o suporte à Groq), uso de
LangChain, respostas em pt-BR com código em inglês, `uv`, README em português, a persona "Maestro" e a apresentação
inicial (ideia minha), a quantidade de chamadas máximas por mensagem e o texto de fallback, regras de busca
(todas as palavras, campos pesquisados, limite de 10, ordem por relevância/desconto) e descarte da ordenação por
localização, status vencendo estoque, alternativas ±30%, comportamento para busca sem resultado/sem critério, conteúdo
de contatos e e-mail, premissa de pedidos online, a regra de parcelamento por faixas, tratamento de feriados,
verificação de pedido por número + telefone e sem listagem, mensagem genérica de falha, uso de `estimated_delivery`,
`AGENT_TODAY`, janela de defeito contada do recebimento e os cenários dos exemplos. Na segunda rodada: aviso de fora do
expediente só na primeira resposta da sessão; reclamações em arquivo local só com descrição e contato; ferramenta de
pagamento por id de produto; **memória da verificação na sessão com limite de tempo** (a ideia do limite foi minha;
10 min de inatividade, teto de 30 min e escopo do telefone eu escolhi entre as opções propostas); e as regras do verificador (evidência = ferramentas + cliente, valores
derivados rejeitados, só R$ e datas, mensagem segura sem valores).

**O que o Claude propôs e implementou:** a arquitetura de ferramentas, os módulos e testes, a conversão do manual em
seções, o script de gravação dos exemplos, o mapeamento de tarefas LLM→código e o texto deste README, sempre com as
opções acima apresentadas para eu escolher.

**Erros do assistente que apareceram no caminho (e como foram pegos):**
- Sugeriu de memória o modelo `gemini-2.5-flash`, já indisponível, e um modelo Groq inexistente na minha chave: peguei
  na execução real; a lista de modelos foi consultada com a chave e o padrão foi atualizado.
- Um commit com "Closes #2" fechou a issue ao fazer push, antes da verificação manual; foi reaberta.
- Um teste de preço mínimo começou com o conjunto esperado errado (faltava o produto 93); a conferência nos CSVs corrigiu.
- Um método foi parar fora da classe por um erro de edição; os testes falharam e revelaram.
- A ordenação inicial colocava desconto antes de disponibilidade, contra o que combinamos; corrigida.
- O Maestro inventou lojas parceiras ("Music Center", "Lojinha do Som") e ofereceu "reservar o modelo", e as ferramentas
  não expunham descrição/especificações dos produtos: apareceram nas minhas execuções e na leitura dos exemplos
  gravados; viraram regras de prompt e uma correção (testada) na ferramenta.
- Declarou `langgraph` como dependência sem usá-lo; removido ao revisar o README.
- Um teste do histórico passou de primeira (o código do ciclo anterior já cobria); foi mantido como proteção.
- O PIX do Giannini saiu `R$ 759,90` em vez de `759,91` por *float*; o assistente percebeu ao conferir os números na saída
  da ferramenta e corrigiu com `Decimal` (teste primeiro).
- Ao implementar o verificador, uma edição duplicou métodos do `Agent`: o teste central continuou falhando e a leitura do
  arquivo mostrou a duplicação. Uma segunda edição falhou por um padrão que não casava com caracteres literais do arquivo.
- **O verificador quebrou com o modelo real**: o regex tratou o ponto final de "…até R$ 2.000." como parte do número e
  lançou `InvalidOperation`. Os testes unitários não pegaram; a regravação dos exemplos pegou. Foi corrigido com um regex
  mais estrito, um *parser* que nunca derruba a conversa e testes de pontuação e de números ilegíveis.
- O README dizia que a verificação de pedido era "*stateless*" depois que ela deixou de ser; corrigido na hora e revisado aqui.
- Vários testes novos do verificador passaram de primeira (o código do primeiro ciclo já os cobria); para não confiar
  em teste que não falha, o assistente desligou o verificador e conferiu que 5 deles quebram.

## Skills do Claude Code usadas (`mattpocock-skills`)

O projeto foi conduzido com o Claude Code e o plugin de *skills* **`mattpocock-skills`** (marketplace
`claude-plugins-official`, versão 1.3.1). Uma *skill* é um pacote de instruções que o Claude Code carrega para um tipo
de tarefa; estas empurram para um fluxo de engenharia disciplinado: **especificação → tickets em fatias verticais →
TDD em fronteiras de teste combinadas antes**. Usei quatro:

| Skill | Para que serviu aqui | Onde aparece no repositório |
|---|---|---|
| `setup-matt-pocock-skills` | Configurar onde ficam as issues (GitHub, via `gh`), o vocabulário de rótulos de triagem e o layout de documentação de domínio | [`CLAUDE.md`](CLAUDE.md) (bloco "Agent skills") e [`docs/agents/`](docs/agents/) (`issue-tracker.md`, `triage-labels.md`, `domain.md`) |
| `to-spec` | Transformar o PDF do desafio, os CSVs e o manual numa especificação (problema, histórias de usuário, decisões, testes, fora de escopo) e publicá-la como issue com o rótulo `ready-for-agent` | [`SPEC.md`](SPEC.md) e a issue #1 |
| `to-tickets` | Quebrar a especificação em *tracer bullets*: fatias verticais, cada uma demonstrável sozinha, com os bloqueios entre elas explícitos | Issues #2 a #8 (primeira rodada) e #9 a #14 (endurecimento), todas com "Parent" e "Blocked by" |
| `tdd` | Conduzir cada ticket em *red → green*, um teste por vez, só em fronteiras (*seams*) confirmadas | Os 163 testes em [`tests/`](tests/) e o histórico de commits |

**Como as regras das skills mudaram o trabalho, na prática:**
- **Fronteiras de teste antes de qualquer teste.** A skill `tdd` não permite escrever teste numa fronteira não confirmada.
  Por isso cada ticket começou com o Claude propondo a fronteira (o que ela pega e o que não pega) e eu confirmando:
  `Agent.respond` com modelo falso; as interfaces `Catalog`, `Policies`, `Orders`, `assess_return` e `Complaints`.
  Tudo fora disso (CLI, camada fina de *tools*, comportamento do LLM real) ficou deliberadamente sem teste automatizado.
- **Fatias verticais, não camadas.** Os tickets cortam o caminho inteiro (dados → regra → ferramenta → prompt → CLI),
  então cada um pôde ser verificado com o modelo real antes de seguir (e foi: eu rodava a CLI e colava a saída).
- **Um ciclo por vez, sem testes "imaginados".** Os testes nasceram de comportamento observável, com valores esperados
  independentes (literais conferidos nos CSVs e no manual), evitando testes que repetem a fórmula do código.
- **Decisões de produto viram perguntas.** A skill `to-spec` manda sintetizar a especificação sem entrevistar o usuário
  (e confirmar só as fronteiras de teste). Como pedi para participar das decisões, o Claude me perguntou também cada
  decisão de produto (regras de busca, parcelas, janela de devolução, tempo de memória da verificação...), e as
  respostas ficaram registradas nas issues.
- **Rótulos e rastreabilidade.** Issues com `ready-for-agent`, comentários de status em cada uma e fechamento só depois
  de verificar com o modelo real (um commit com "Closes #2" chegou a fechar uma issue cedo demais; foi reaberta).

**Onde me afastei das skills, ou onde elas encontraram limites:**
- Em alguns ciclos agrupei testes relacionados antes de implementar (por exemplo, os de formato e expiração da
  verificação de pedidos), em vez de um único teste por vez; e vários testes passaram de primeira porque o código do
  ciclo anterior já os cobria. Quando isso aconteceu, conferi que eles realmente falham (checagem de mutação no
  verificador de respostas).
- O `gh` instalado (2.4) é antigo: não tem sub-issues nativas, dependências entre issues nem `--comment` no `close`.
  As dependências ficaram em texto ("Blocked by") e o fechamento foi comentário + `close`.
- A skill de modelagem de domínio (`GLOSSARY.md` e ADRs) está configurada em `docs/agents/domain.md`, mas **não usei**:
  as decisões foram registradas nas issues e no README. Também não usei as skills de revisão de código, `grilling`,
  `prototype` ou `wizard`; o enunciado pedia um protótipo e o ciclo especificação → tickets → TDD bastou.
- O arquivo [`CLAUDE.md`](CLAUDE.md) e `docs/agents/` são configuração da ferramenta de desenvolvimento, não do agente
  Maestro: o agente em si não depende de nenhuma skill nem do Claude Code.

## Estrutura do repositório

```
src/emporio_agent/   código do agente
tests/               163 testes (modelo falso + CSVs reais)
data/                CSVs e PDF da loja; data/policies/ = manual em seções .md
examples/            5 conversas gravadas com o modelo real
scripts/             gravação dos exemplos
docs/agents/, CLAUDE.md   configuração das skills do Claude Code
SPEC.md              especificação inicial
complaints.jsonl     (gerado em execução, ignorado pelo git) reclamações e encaminhamentos
```
