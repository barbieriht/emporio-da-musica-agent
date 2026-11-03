# Maestro — agente de atendimento da Empório da Música

Protótipo (Python) de um agente de atendimento por mensagens de texto para a **Empório da Música**,
loja fictícia de instrumentos musicais de Campo Grande/MS, feito para o Desafio Técnico AI Engineer da Artefact.

O **Maestro** conversa em português do Brasil, em tom informal mas profissional (como pede o manual da loja),
consulta preços, estoque, promoções e pedidos nos dados da loja, aplica as políticas do manual
(horários, pagamento, frete, trocas, garantia) e recusa com educação o que foge do escopo.

- Conversas de exemplo (com as ferramentas chamadas em cada turno): [`examples/`](examples/)
- Especificação que guiou o trabalho: [`SPEC.md`](SPEC.md) e [issue #1](https://github.com/barbieriht/emporio-da-musica-agent/issues/1)

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

### Data simulada (`AGENT_TODAY`)

Os pedidos de exemplo são de 2025–2026. Com a data real, toda devolução já estaria fora do prazo.
Para demonstrar um caso dentro da janela, defina por exemplo `AGENT_TODAY=2026-02-20` no `.env`
(afeta apenas a regra de devolução; a consulta "loja aberta agora" sempre usa o relógio real).

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
 Agent.respond(session, mensagem)  ── loop de ferramentas (máx. 5 chamadas ao modelo por mensagem)
      │         ▲
      │         └── resultado das ferramentas
      ▼
 LLM (system prompt do Maestro + histórico da sessão + definição das ferramentas)
      │ decide qual ferramenta chamar
      ▼
 ┌────────────┬──────────────┬───────────────┬─────────────────┐
 │ Catalog    │ Policies     │ Orders        │ Returns         │
 │ (CSVs)     │ (manual em   │ (CSVs, exige  │ (regra pura +   │
 │ busca,     │ seções .md,  │ pedido +      │ pedido verif.)  │
 │ preço,     │ parcelas,    │ telefone)     │                 │
 │ estoque    │ frete,       │               │                 │
 │            │ horário)     │               │                 │
 └────────────┴──────────────┴───────────────┴─────────────────┘
```

| Módulo | Responsabilidade |
|---|---|
| `agent.py` | `Agent.respond(session, mensagem)`: loop de ferramentas, histórico, limite de chamadas, rollback do histórico se o modelo falhar |
| `prompt.py` | Persona (Maestro), regras de conduta e saudação inicial |
| `catalog.py` | Carrega produtos/categorias/promoções; busca, preço efetivo, disponibilidade, alternativas |
| `policies.py` | Seções do manual; opções de parcelamento, frete, "loja aberta agora" (fuso America/Campo_Grande) |
| `orders.py` | Consulta de pedido com verificação do cliente |
| `returns.py` | Elegibilidade de devolução/troca por motivo, prazo e status do pedido |
| `tools.py` | Camada fina que expõe os módulos como *tools* do LangChain, formatando respostas em português |
| `config.py`, `cli.py` | Seleção do provedor por env, relógio (`AGENT_TODAY`), CLI de chat |

## Decisões técnicas e justificativas

**Abordagem: *function calling* com ferramentas determinísticas (sem RAG vetorial, sem agente de SQL).**
Os dados são pequenos (65 produtos, 19 pedidos, 49 clientes) e o manual tem ~8 páginas. Regras que precisam estar
certas (preço com promoção, janela de 7 dias, parcelas, frete, horário) são código testável, não texto para o modelo
interpretar. O LLM fica com o que ele faz bem: entender a pergunta, escolher a ferramenta e redigir a resposta no tom
da loja. Um agente de SQL geraria consultas livres sobre dados com regras de negócio escondidas (promoção ativa,
status que vale mais que estoque); ferramentas tipadas evitam isso e dão uma superfície pequena para testar.

**Framework: LangChain (modelos de chat e *tools*), com loop de agente próprio.** Escolhi LangChain/LangGraph, mas na
implementação só o LangChain se mostrou necessário: o loop (chamar modelo → executar ferramentas → devolver resultado)
tem pouco mais de 10 linhas, e escrevê-lo à mão deixou o ponto de teste simples (basta injetar um modelo falso).
LangChain continua útil pela troca de provedor por variável de ambiente e pela definição das ferramentas.
(Declarei `langgraph` no início e removi depois, por não ser usado.)

**Modelo e provedor: Gemini (padrão) e Groq (alternativa), ambos gratuitos.** Quem avalia precisa conseguir rodar sem
pagar; ambos têm camada gratuita e suportam *tool calling*. O modelo é fixado por versão (reprodutibilidade) e pode
ser trocado por env. Modelos locais (Ollama) foram descartados como padrão: o agente depende de chamar ferramentas
corretamente, onde modelos pequenos falham mais, e exigem hardware do avaliador.

**Estratégia de prompt.** O *system prompt* define persona e regras do manual: nunca informar preço, estoque ou prazo
sem consultar uma ferramenta; mostrar preço original junto do promocional; redirecionar acessórios (a loja só vende
instrumentos); recusar assuntos fora da loja; não fazer reservas nem pedidos (o agente só informa); não inventar
etapas de processo nem características de produtos. A saudação inicial é um texto fixo (não gasta chamada de modelo e
funciona mesmo com o provedor instável), e o prompt avisa o modelo de que ele já se apresentou.

**Recuperação das políticas: seções em Markdown, consulta por tópico.** Converti o PDF uma vez em nove arquivos em
`data/policies/` (loja, horários, pagamento, trocas, frete, promoções, atendimento, garantia, privacidade). Assim o
projeto roda sem dependência de leitura de PDF, as seções são revisáveis e o agente recebe só o trecho relevante.
Com um manual maior eu passaria a embeddings; para 8 páginas, o custo e a incerteza não se justificam. (Risco: a
conversão é manual e pode divergir do PDF original, que continua no repositório.)

**Tratamento dos dados.** Os CSVs são carregados em memória na inicialização e nunca alterados. Normalizações: preços
numéricos, `specs` (JSON) em dicionário, busca sem acento/caixa e com plural simples ("violão" encontra "Violões"),
preço efetivo com a promoção ativa, disponibilidade derivada de status + estoque.

**Privacidade e segurança dos dados de cliente.** Pedido só é mostrado com **número do pedido + telefone cadastrado**
(comparação só pelos dígitos); pedido inexistente, telefone errado e telefone de outro cliente dão a mesma resposta
genérica, sem revelar qual dado falhou. O e-mail não é usado porque um deles aparece em dois clientes.
A verificação é *stateless*: a ferramenta sempre recebe os dados, então o modelo não consegue pulá-la.

**Histórico de conversa.** Em memória, por sessão (`Session`). Persistir entre sessões não agrega ao protótipo de CLI.
Se o modelo falhar no meio de um turno, o histórico volta ao estado anterior (sem mensagem pendurada sem resposta).

**Interface: CLI.** O foco é o agente; um chat de terminal basta para avaliar.

**Estratégia de testes (96 testes, sem rede).** Testes só em fronteiras públicas acordadas, nunca em detalhes internos:
(1) `Agent.respond` com um modelo falso roteirizado (histórico, loop de ferramentas, limite de chamadas, persona,
rollback); (2) as interfaces `Catalog`, `Policies`, `Orders` e `assess_return` sobre os CSVs reais, com relógio
injetável. Os valores esperados vêm de literais conferidos nos CSVs/manual, não recalculados pelo mesmo código.
Ficam **fora** dos testes: a CLI, as camadas finas de *tools* e o comportamento do LLM real (verificado manualmente e
nos exemplos).

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

**Políticas**
- Contatos: telefone da loja (67) 3341-4444 e WhatsApp (67) 3321-4500 (o manual traz os dois em seções diferentes).
  E-mail `contato@emporiodamusica.com.br`; a tabela do §1.2 traz uma versão com acento, que não é um domínio válido.
- Parcelamento: com *n* parcelas, vale se `preço / n` atinge o mínimo da faixa (R$ 50 até 3x; R$ 80 de 4x a 6x;
  R$ 100 de 7x a 12x; o mínimo de R$ 50 também vale para 2x). Ex.: 3x a partir de R$ 150, 12x a partir de R$ 1.200.
- Frete: só a cidade de Campo Grande conta como "região metropolitana"; pedido de exatamente R$ 500 tem frete grátis
  (o manual diz "acima" e "abaixo"); fora dela o frete depende do CEP e o agente informa apenas os prazos.
- Feriados: considero os nacionais de data fixa; móveis (Carnaval, Sexta-feira Santa, Corpus Christi) e locais não
  entram, e o agente avisa para confirmar.
- PIX (5%) não se aplica a preço já promocional.

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

## Limitações conhecidas

- **O LLM ainda pode embelezar.** Mesmo com regras no prompt, o exemplo [`04`](examples/04-devolucao-pedido-real.md)
  acrescenta detalhes que o manual não diz ("gerar a etiqueta de devolução", "coleta", reembolso contado a partir do
  recebimento pela loja). Os números e prazos vêm das ferramentas, mas o texto em volta não é verificado.
- **Sem avaliação automatizada do comportamento do LLM.** Os testes cobrem regras e o loop, não a qualidade das
  respostas; os exemplos são uma amostra manual de uma execução.
- **Verificação de pedido fraca para produção**: telefone + número do pedido, sem limite de tentativas (alguém poderia
  tentar combinações) e sem defesa específica contra *prompt injection*.
- **Sem ações**: o agente só informa. Não reserva, cria nem cancela pedidos; encaminha para a loja.
- **Busca simples**: sem tolerância a erros de digitação, sinônimos ou perguntas por faixa de uso
  ("um violão bom pra começar").
- **Histórico só em memória**; reiniciar a CLI zera a conversa.
- **Dependência do provedor gratuito**: limites de taxa, sobrecarga (503) e modelos aposentados. A CLI mostra uma
  mensagem amigável quando o modelo falha, mas não troca de provedor sozinha.
- **Política copiada à mão do PDF** e **somente português**.
- Feriados móveis/locais e frete fora de Campo Grande não são calculados.

**O que eu faria com mais tempo:** um conjunto de avaliação (cenários + verificação de afirmações contra as saídas
das ferramentas, ou LLM como juiz); uma checagem automática de valores/prazos citados na resposta; limite de
tentativas e registro de auditoria na verificação de pedidos; persistência de sessão e canal real (WhatsApp);
busca com tolerância a erro de digitação e, se o manual crescer, embeddings; fluxo de encaminhamento para atendente
humano para reclamações e cancelamentos.

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

**O que decidi eu:** provedor gratuito e modelo (Gemini 3.7 Flash fixado; depois pedi o suporte à Groq), uso de
LangChain, respostas em pt-BR com código em inglês, `uv`, README em português, a persona "Maestro" e a apresentação
inicial (ideia minha), a quantidade de chamadas máximas por mensagem e o texto de fallback, regras de busca
(todas as palavras, campos pesquisados, limite de 10, ordem por relevância/desconto) e descarte da ordenação por
localização, status vencendo estoque, alternativas ±30%, comportamento para busca sem resultado/sem critério, conteúdo
de contatos e e-mail, premissa de pedidos online, a regra de parcelamento por faixas, tratamento de feriados,
verificação de pedido por número + telefone e sem listagem, mensagem genérica de falha, uso de `estimated_delivery`,
`AGENT_TODAY`, janela de defeito contada do recebimento e os cenários dos exemplos.

**O que o Claude propôs e implementou:** a arquitetura de ferramentas, os módulos e testes, a conversão do manual em
seções, o script de gravação dos exemplos e o texto deste README, sempre com as opções acima apresentadas para eu escolher.

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

## Estrutura do repositório

```
src/emporio_agent/   código do agente
tests/               96 testes (modelo falso + CSVs reais)
data/                CSVs e PDF da loja; data/policies/ = manual em seções .md
examples/            5 conversas gravadas com o modelo real
scripts/             gravação dos exemplos
docs/agents/, CLAUDE.md   configuração das skills do Claude Code
SPEC.md              especificação inicial
```
