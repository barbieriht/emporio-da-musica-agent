# Maestro — customer-service agent for Empório da Música

A Python prototype of a text-message customer-service agent for **Empório da Música**, a fictional musical-instrument
store in Campo Grande, MS (Brazil), built for the Artefact AI Engineer technical challenge.

**Maestro** talks to customers in Brazilian Portuguese, in an informal but professional tone (as the store's manual
asks). It looks up prices, stock, promotions and orders in the store's data, applies the manual's policies (opening
hours, payment, shipping, exchanges, warranty), registers complaints and hand-off requests for the staff, and politely
declines anything out of scope. Whatever has to be right (prices, deadlines, installments, order verification, opening
hours) is tested code, not free text from the model.

- Example conversations (with the tools called in each turn): [`examples/`](examples/)
- Specification that guided the work: [`SPEC.md`](SPEC.md) and [issue #1](https://github.com/barbieriht/emporio-da-musica-agent/issues/1)
- How the project was built with Claude Code and the `mattpocock-skills` skills: [section below](#claude-code-skills-used-mattpocock-skills)
- All the documentation in a single PDF: [`docs/maestro-documentation.pdf`](docs/maestro-documentation.pdf)

## Language

Everything in the repository is written in **English** (README, specification, code, comments, test names, issues and
commit messages), with one deliberate exception: **what the agent says to customers, and the text that instructs the model, is Brazilian
Portuguese**. That covers the system prompt, the tool descriptions and tool outputs, the fixed messages (greeting,
fallbacks, after-hours notice), the store's policy manual in `data/policies/` (the store's own source document) and the
recorded example conversations. The customers are Brazilian and the data and manual are in Portuguese, so changing the
agent's language would change the product, not just the documentation. The example files have English headers and
Portuguese transcripts. For the same reason, the string literals inside the tests (what the agent is expected to say)
are Portuguese.

## How to run

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/barbieriht/emporio-da-musica-agent.git
cd emporio-da-musica-agent
uv sync
cp .env.example .env        # fill in ONE provider key (see below)
uv run python -m emporio_agent
```

Type `sair` (Portuguese for "quit") to leave. To run the tests (they use neither the network nor a real LLM):

```bash
uv run pytest
```

### Model provider

The agent uses LangChain's `init_chat_model`, so the provider is chosen with environment variables (`.env`):

| Provider | Variables | Notes |
|---|---|---|
| **Google Gemini** (default) | `GOOGLE_API_KEY` | Free tier at <https://aistudio.google.com/apikey>. Default model pinned to `gemini-3.7-flash`. |
| **Groq** (alternative) | `GROQ_API_KEY`, `LLM_PROVIDER=groq`, `LLM_MODEL=openai/gpt-oss-120b` | Free tier with limits: <https://console.groq.com/keys>. |

`LLM_PROVIDER` and `LLM_MODEL` override the default. **Model names change and get retired**: `gemini-2.5-flash` was
already unavailable for new accounts during development, and a Groq Llama model that the assistant suggested from memory
did not exist for the key. If you get `404 model not found`, list the models your key can use and set `LLM_MODEL`.
If the provider answers `503 high demand`, the model is temporarily overloaded: retry, or switch model/provider.

### Optional variables

| Variable | Effect |
|---|---|
| `AGENT_TODAY=2026-02-20` | The sample orders are from 2025–2026, so with the real date every return would already be expired. This variable simulates the date **for the return rule only** (the "store open now" check and the after-hours notice always use the real clock). |
| `COMPLAINTS_FILE` | Where complaints and hand-off requests are written (default: `complaints.jsonl` in the project root, ignored by git). |

### Regenerating the examples

```bash
uv run python scripts/record_examples.py            # all of them
uv run python scripts/record_examples.py 04-real-order-return
```

The script replays scripted customer messages through the real agent and saves the transcripts with the tool calls. The
output varies a little on every run (it is an LLM).

### Regenerating the documentation PDF

```bash
uv run python scripts/build_docs_pdf.py
```

It renders this README, `SPEC.md`, `docs/agents/*.md` and the five example conversations into
`docs/maestro-documentation.pdf`. It needs the `markdown` package (dev dependency, installed by `uv sync`) and the
`wkhtmltopdf` program on the system.

## How the agent works

```
customer message
      │
      ▼
 Agent.respond(session, message)
      │  ├─ tool loop (at most 5 model calls per message)
      │  ├─ checker: R$ values and dates in the final reply must come from the tools
      │  └─ after-hours notice (only on the first reply of a session in which the store is closed)
      ▼
 LLM (Maestro system prompt + session history + tool definitions)
      │ decides which tool to call
      ▼
 ┌─────────┬──────────┬────────┬─────────┬────────────┐
 │ Catalog │ Policies │ Orders │ Returns │ Complaints │
 └─────────┴──────────┴────────┴─────────┴────────────┘
   CSVs      manual as   CSVs +   pure       local
             .md files   verific. rules      file
```

**The 11 tools exposed to the model:**

| Tool | What it does |
|---|---|
| `search_products`, `get_product_details` | Catalog search; details (description, specs, alternatives when unavailable) |
| `get_payment_options` | By product id: PIX (5% only without a promotion), debit, boleto, installments, combining payment methods |
| `get_policy` | A section of the manual (store, hours, payment, exchanges, shipping, promotions, service guidelines, warranty, privacy) |
| `get_installments`, `get_shipping_quote`, `is_store_open_now` | Installments for an amount, shipping by city, whether the store is open now |
| `get_order_status`, `check_return_eligibility` | Order status and return/exchange eligibility, with phone verification |
| `register_complaint`, `request_human_handoff` | Writes a complaint or a hand-off request, with a protocol number |

| Module | Responsibility |
|---|---|
| `agent.py` | `Agent.respond(session, message)`: tool loop, history, call limit, rollback if the model fails, after-hours notice, reply checking, tool access to the session |
| `grounding.py` | Extracts R$ values and dates from a text and checks them against what the tools/customer said |
| `prompt.py` | Persona (Maestro), conduct rules and the opening greeting |
| `catalog.py` | Loads products/categories/promotions; search, effective price, availability, alternatives |
| `policies.py` | Manual sections; installments, payment options, shipping, "store open now" and the after-hours notice (America/Campo_Grande time zone) |
| `orders.py` | Order lookup: format validation, phone verification and session memory of the verification |
| `returns.py` | Return/exchange eligibility by reason, deadline and order status |
| `complaints.py` | Local JSON Lines log of complaints and hand-offs, with a protocol number |
| `money.py` | Commercial rounding (half up) with `Decimal` |
| `tools.py` | Thin layer exposing the modules as LangChain *tools*, formatting answers in Portuguese |
| `config.py`, `cli.py` | Provider selection from env, clock (`AGENT_TODAY`), agent assembly, chat CLI |

## Technical decisions and rationale

**Approach: function calling with deterministic tools (no vector RAG, no SQL agent).** The data is small (65 products,
19 orders, 49 customers) and the manual is ~8 pages. Rules that must be right (promotional price, 7-day window,
installments, shipping, opening hours) are testable code, not text for the model to interpret. The LLM keeps what it does
well: understanding the question, choosing the tool and writing the answer in the store's tone. A SQL agent would write
free-form queries over data with hidden business rules (active promotion, status beating stock); typed tools avoid that
and give a small surface to test.

**What is code and what is LLM (revised after a first version).** In a second round I mapped what the model was still
doing "in its head" and moved to code whatever could be deterministic: the **after-hours notice** (the manual requires
it and before it only appeared if the customer asked), the **PIX discount** (the model used to compute it), the
**registration of complaints** (the prompt said "register", but there was no tool: the agent claimed an action it did
not perform), the **validation of phone and order number**, and the **checking of values and dates in the final reply**.
Deliberately left to the LLM: understanding free language, classifying the return reason and writing the reply. I ruled
out detecting "accessory" requests by keyword (it collides with "Cordas Orquestrais", a category the store does sell) and
classifying intent with regexes.

**Framework: LangChain (chat models and tools), with my own agent loop.** I chose LangChain/LangGraph, but in the
implementation only LangChain turned out to be needed: the loop (call model → run tools → return result, plus the call
limit and the checker) fits in one short function, and writing it by hand kept the test seam simple (just inject a fake
model). LangChain remains useful for switching providers by environment variable and for defining the tools. (I declared
`langgraph` at the start and removed it later because it was unused.)

**Model and provider: Gemini (default) and Groq (alternative), both free.** Whoever evaluates this must be able to run it
without paying; both have a free tier and support tool calling. The model is pinned by version (reproducibility) and can
be switched by env. Local models (Ollama) were ruled out as the default: the agent depends on calling tools correctly,
where small models fail more, and they require the evaluator's hardware.

**Prompt strategy.** The system prompt defines the persona and the manual's rules: never state a price, stock or deadline
without consulting a tool; use the payment tool instead of computing PIX/installments; show the original price next to
the promotional one; redirect accessory requests (the store only sells instruments); decline subjects unrelated to the
store; do not make reservations or orders (the agent only informs; to buy, reserve or cancel it uses the hand-off); ask
for phone and order number only on the first lookup; only say a complaint was registered if the tool confirms it; do not
invent process steps or product features. The opening greeting is a fixed text (it costs no model call and works even
when the provider is unstable), and the prompt tells the model it has already introduced itself.

**Policy retrieval: Markdown sections, lookup by topic.** I converted the PDF once into nine files in `data/policies/`
(store, hours, payment, exchanges, shipping, promotions, service guidelines, warranty, privacy). That way the project
runs without a PDF-reading dependency, the sections are reviewable, and the agent receives only the relevant excerpt.
With a larger manual I would move to embeddings; for 8 pages, the cost and the uncertainty are not justified. (Risk: the
conversion is manual and may drift from the original PDF, which stays in the repository.)

**Data handling.** The CSVs are loaded into memory at start-up and never modified. Normalizations: numeric prices, `specs`
(JSON) as a dictionary, accent- and case-insensitive search with simple plurals ("violão" finds "Violões"), effective
price with the active promotion, availability derived from status + stock. **Money uses `Decimal` with commercial
rounding (half up)**: while checking numbers I found that `799.90 × 0.95 = 759.905` came out as `759.90` because of
floating-point imprecision, when the correct commercial result is `759.91`.

**Checker for values and dates in the final reply.** The LLM writes the text and may alter or invent a value. After every
final reply, the code extracts the R$ values and the dates; each one must appear in the session's tool results or in the
customer's own messages (formats such as `R$ 1.000,00`, `1000` and `1 000` are equivalent; dates match by day/month, and
by year when both sides carry it). Derived values (sums, differences) are **rejected** on purpose: calculations live in
the tools. If something does not match, the agent asks for one rewrite, quoting the offending value (in that round it may
call a tool); if that fails too, it sends a safe message without values, with the store's phone and WhatsApp. The rejected
reply and the correction notice do not stay in the history.

**Privacy and security of customer data.** An order is only shown with **order number + registered phone** (compared by
digits only); a non-existent order, a wrong phone and another customer's phone all give the same generic answer, without
revealing which piece failed. The e-mail is not used because one of them appears on two customers. Formats are validated
in code (phone with area code + 8/9 digits, positive integer order number). After a successful verification the session
remembers the phone: it expires after 10 minutes without use, with a 30-minute cap since the customer typed the phone, it
only covers that customer's orders, and wrong attempts are never remembered (nor do they erase a valid verification). The
rule lives in code (`Orders.lookup`), not in the prompt, so the model cannot skip it. Complaints and hand-offs store
**only the description and the contact** (never the conversation), in `complaints.jsonl`, outside git.

**Conversation history.** In memory, per session (`Session`). Persisting across sessions adds nothing to a CLI prototype.
If the model fails in the middle of a turn, the history goes back to its previous state (no message left hanging without a
reply).

**Interface: CLI.** The focus is the agent; a terminal chat is enough to evaluate it.

**Testing strategy (163 tests, no network).** Tests only at agreed public boundaries, never on internals: (1)
`Agent.respond` with a scripted fake model (33 tests: history, tool loop, call limit, persona, rollback, after-hours
notice, session context for the tools, value checker); (2) the `Catalog` (26), `Policies` (51), `Orders` (31),
`assess_return` (12) and `Complaints` (10) interfaces over the real CSVs or temporary files, with injectable clock and
state. Expected values come from literals checked against the CSVs/manual, not recomputed by the same code. **Outside**
the tests: the CLI, the thin *tool* layers and the behaviour of the real LLM (checked manually and in the examples). Two
notes on how much to trust the tests: I ran a mutation check on the checker (with it disabled, 5 tests fail), and the run
with the real model found a *crash* that the unit tests missed (see "Assistant mistakes").

## Assumptions

The brief asks to assume reasonable interpretations and document them. The main ones:

**Catalog**
- Only promotions with `is_active=1` count; if several are active on the same product, the largest wins (does not happen today).
- **Status beats stock**: product 136 (discontinued) shows stock 13 and 130 (coming soon) shows stock 2; both are treated
  as unavailable.
- Search by words (all must appear) in name, category and specifications; no typo tolerance. Up to 10 results, ordered by
  relevance → available first → discounted first → lower price. Unavailable products appear flagged.
- Price filters use the effective price (promotion already applied).
- Alternatives for an unavailable product: same category, available, price ±30%, closest first (up to 3).
- I do not sort by proximity: there is a single store and the products have no location.

**Policies and payment**
- Contacts: store phone (67) 3341-4444 and WhatsApp (67) 3321-4500 (the manual gives both, in different sections).
  E-mail `contato@emporiodamusica.com.br`; the table in §1.2 has a version with an accent, which is not a valid domain.
- Installments: with *n* installments, it is allowed if `price / n` reaches the tier minimum (R$ 50 up to 3x; R$ 80 from
  4x to 6x; R$ 100 from 7x to 12x; the R$ 50 minimum also applies to 2x). E.g. 3x from R$ 150, 12x from R$ 1,200.
- PIX: 5% off the list price, **only on a product without a promotion** (promotions are not cumulative); the tool receives
  the product id and knows by itself whether there is a promotion. Combining payment methods is allowed **from R$ 2,000,
  inclusive** (the manual says "above"; same criterion as shipping).
- Shipping: only the city of Campo Grande counts as the "metropolitan region"; an order of exactly R$ 500 ships free (the
  manual says "above" and "below"); outside it, shipping depends on the ZIP code and the agent only gives the deadlines.
- Holidays: I consider national fixed-date holidays; movable ones (Carnival, Good Friday, Corpus Christi) and local ones
  are not included, and the agent tells the customer to confirm.
- After hours: the notice with the reopening time comes **before** the reply and **only once per session** (on the first
  reply in which the store is closed); if the store was open and closed in the middle of the conversation, it appears on
  the next reply.

**Orders and returns**
- The recorded `total_brl` is what counts, never the sum of the items at today's prices (on orders 3 and 20 they differ).
- Orders are treated as **online purchases** (they have tracking/delivery), so the 7-day right of withdrawal applies.
- There is no actual delivery date in the data: I use `estimated_delivery` as the receipt date. A shipped order has not
  started its window; pending/confirmed has nothing to return; cancelled neither.
- Withdrawal and preference exchange: 7 days; **defect: 30 days counted from receipt** (the manual says "after the
  purchase"; I chose receipt for consistency with the legal warranty and so shipping does not eat the window). After that,
  the 90-day legal warranty (from receipt) and the manufacturer's, with the store able to mediate.
- Personalized or "final sale" items cannot be identified in the data: the agent sends the customer to confirm with the staff.
- "Today" is the system's real date, overridable with `AGENT_TODAY`.
- Order verification is remembered in the session for 10 min of inactivity, capped at 30 min, scoped to the phone (all
  orders of that customer); no listing of orders by phone alone.

**Complaints and hand-offs**
- Saved locally with a sequential protocol, kind (`complaint`/`handoff`), description, contact and time; the contact is
  mandatory (without it nothing is saved and the agent asks). The "reply within 24 business hours" comes from the manual,
  but **no mechanism enforces it**: it is only the record.
- If the write fails, the tool tells the agent so, and the agent must not claim it registered.

## Known limitations

- **The LLM can still embellish the text around the facts.** R$ values and dates are checked, the rest is not. In example
  [`04`](examples/04-real-order-return.md) Maestro still says the staff "will generate the postage label" and that
  the refund counts "after the store receives the product", which the manual does not say. (Before the checker and the
  prompt rules it even invented partner stores and offered reservations.)
- **The checker is limited.** It only covers R$ values and dates; not percentages, number of installments or deadlines in
  days. It also rejects correct calculations done by the model (a deliberate decision). **I did not measure how many
  replies get rewritten** nor the false-positive rate: in the five example scenarios none fell into the safe message, but
  the sample is small.
- **No automated evaluation of the LLM's behaviour.** The tests cover rules, the loop and the checker, not the quality of
  the answers; the examples are a manual sample from one run.
- **Order verification is still weak for production**: phone + order number, no attempt limit (someone could try
  combinations) and no specific defence against prompt injection.
- **Complaints in a local file**: no queue, no notification to the staff, no case owner and no real deadline; the file
  holds phone/e-mail in plain text, with no encryption or retention policy (it is outside git, but it is personal data).
- **No business actions**: the agent only informs. It does not reserve, create or cancel orders; it records and forwards.
- **Simple search**: no typo tolerance, synonyms or use-based questions ("a good guitar for beginners").
- **History in memory only**; restarting the CLI resets the conversation and the verification.
- **Dependence on the free provider**: rate limits, overload (503) and retired models. The CLI shows a friendly message
  when the model fails, but it does not switch providers by itself.
- **Policy copied by hand from the PDF**, and **Portuguese only** for the agent's replies.
- Movable/local holidays and shipping outside Campo Grande are not computed; "store open now" and the after-hours notice
  always use the real clock (they ignore `AGENT_TODAY`).
- The examples show catalog, store/hours, out of stock + installments, return, and out of scope/privacy; the verification
  memory, complaints, the after-hours notice and the payment options are covered by tests and manual runs, but have no
  recorded example (the brief asks for 3 to 5 conversations).

**What I would do with more time:** an evaluation set (scenarios + LLM-as-judge, measuring rewrites and checker false
positives); extend the checker to percentages, installments and deadlines; attempt limits and an audit log on order
verification; notify the staff on complaints and store them with a retention policy; session persistence and a real
channel (WhatsApp); search with typo tolerance and, if the manual grows, embeddings; a real human-agent flow for cancellations.

## Use of AI coding assistants

I used **only Claude Code** (Anthropic's CLI, Sonnet model), with the `mattpocock-skills` plugin of *skills*
(`to-spec`, `to-tickets`, `tdd`) to structure the work. The workflow, in practice:

1. **Specification**: Claude read the challenge PDF, the CSVs and the manual and wrote [`SPEC.md`](SPEC.md) (problem,
   user stories, decisions, tests, out of scope), published as issue #1.
2. **Tickets**: the specification became 7 GitHub issues, as vertical slices with explicit dependencies (skeleton with
   persona → catalog → policies → orders → returns → examples → README).
3. **TDD per ticket**: before any test, Claude proposed the **test boundary** and I confirmed it. Then, one cycle at a
   time: failing test → minimal code → next test. Whenever there was a product decision, it asked me instead of choosing
   by itself.
4. **Real verification**: I ran the CLI with the real model and pasted the output; Claude adjusted from there.
5. **Second round (hardening)**: I asked Claude which of the LLM's tasks could become code. It mapped ten, with value and
   effort, and I agreed with the proposed order; they became six more issues (#9 to #14), following the same flow.
6. **Language**: I initially wrote the README in Portuguese (my choice at the time). When I found out that the
   deliverables must be in English, I asked Claude to translate the README and the documentation and generate a PDF; the
   agent itself keeps speaking Portuguese (see "Language").

**What I decided:** free provider and model (Gemini 3.7 Flash pinned; later I asked for Groq support), the use of
LangChain, replies in pt-BR with code in English, `uv`, the "Maestro" persona and the opening introduction (my idea), the
maximum number of calls per message and the fallback text, search rules (all words, searched fields, limit of 10, order by
relevance/discount) and dropping the sort by location, status beating stock, alternatives ±30%, behaviour for a search with
no result/no criteria, contacts and e-mail content, the online-orders assumption, the tiered installment rule, holiday
handling, order verification by number + phone and no listing, the generic failure message, use of `estimated_delivery`,
`AGENT_TODAY`, the defect window counted from receipt, and the example scenarios. In the second round: the after-hours
notice only on the first reply of the session; complaints in a local file with only description and contact; the payment
tool by product id; **session memory of the verification with a time limit** (the idea of the limit was mine; the 10 min
inactivity, 30 min cap and phone scope I chose among the proposed options); and the checker's rules (evidence = tools +
customer, derived values rejected, only R$ and dates, a safe message without values). And, at the end, the scope of the
English translation and what goes into the PDF.

**What Claude proposed and implemented:** the tool architecture, the modules and tests, the conversion of the manual
into sections, the script that records the examples, the LLM→code task mapping, the PDF build script, the translation,
and the text of this README, always presenting options for me to choose from.

**Assistant mistakes along the way (and how they were caught):**
- It suggested `gemini-2.5-flash` from memory, already unavailable, and a Groq model that did not exist for my key: I
  caught it on the real run; the key's model list was queried and the default updated.
- A commit with "Closes #2" closed the issue on push, before the manual verification; it was reopened.
- A minimum-price test started with the wrong expected set (product 93 was missing); checking against the CSVs fixed it.
- A method ended up outside the class because of an editing error; the tests failed and revealed it.
- The initial ordering put discount before availability, against what we agreed; fixed.
- Maestro invented partner stores ("Music Center", "Lojinha do Som") and offered to "reserve the model", and the tools did
  not expose product descriptions/specifications: these showed up in my runs and when reading the recorded examples; they
  became prompt rules and a (tested) fix in the tool.
- It declared `langgraph` as a dependency without using it; removed while reviewing the README.
- A history test passed on the first run (the previous cycle's code already covered it); it was kept as protection.
- The PIX price of the Giannini came out `R$ 759,90` instead of `759,91` because of *float*; the assistant noticed it
  while checking the numbers in the tool output and fixed it with `Decimal` (test first).
- While implementing the checker, an edit duplicated methods of `Agent`: the central test kept failing and reading the
  file showed the duplication. A second edit failed because a pattern did not match literal characters in the file.
- **The checker crashed with the real model**: the regex treated the final dot of "…up to R$ 2.000." as part of the number
  and raised `InvalidOperation`. The unit tests did not catch it; re-recording the examples did. It was fixed with a
  stricter regex, a parser that never breaks the conversation, and tests for punctuation and unreadable numbers.
- The README said order verification was "stateless" after it stopped being so; fixed on the spot and reviewed here.
- Several new checker tests passed on the first run (the first cycle's code already covered them); so as not to trust a
  test that never fails, the assistant disabled the checker and confirmed that 5 of them break.

## Claude Code skills used (`mattpocock-skills`)

The project was run with Claude Code and the **`mattpocock-skills`** plugin of *skills* (marketplace
`claude-plugins-official`, version 1.3.1). A skill is a package of instructions that Claude Code loads for a kind of task;
these ones push towards a disciplined engineering flow: **specification → tickets as vertical slices → TDD at test
boundaries agreed beforehand**. I used four:

| Skill | What it was for here | Where it shows in the repository |
|---|---|---|
| `setup-matt-pocock-skills` | Configure where issues live (GitHub, via `gh`), the triage-label vocabulary and the domain-documentation layout | [`CLAUDE.md`](CLAUDE.md) ("Agent skills" block) and [`docs/agents/`](docs/agents/) (`issue-tracker.md`, `triage-labels.md`, `domain.md`) |
| `to-spec` | Turn the challenge PDF, the CSVs and the manual into a specification (problem, user stories, decisions, tests, out of scope) and publish it as an issue labelled `ready-for-agent` | [`SPEC.md`](SPEC.md) and issue #1 |
| `to-tickets` | Break the specification into *tracer bullets*: vertical slices, each demonstrable on its own, with the blocking relations made explicit | Issues #2 to #8 (first round) and #9 to #14 (hardening), all with "Parent" and "Blocked by" |
| `tdd` | Drive each ticket in *red → green*, one test at a time, only at confirmed boundaries (*seams*) | The 163 tests in [`tests/`](tests/) and the commit history |

**How the skills' rules changed the work, in practice:**
- **Test boundaries before any test.** The `tdd` skill does not allow writing a test at an unconfirmed boundary. So every
  ticket began with Claude proposing the boundary (what it catches and what it misses) and me confirming it:
  `Agent.respond` with a fake model; the `Catalog`, `Policies`, `Orders`, `assess_return` and `Complaints` interfaces.
  Everything outside that (CLI, thin tool layer, real LLM behaviour) was deliberately left without automated tests.
- **Vertical slices, not layers.** The tickets cut the whole path (data → rule → tool → prompt → CLI), so each could be
  verified with the real model before moving on (and was: I ran the CLI and pasted the output).
- **One cycle at a time, no "imagined" tests.** Tests were born from observable behaviour, with independent expected
  values (literals checked in the CSVs and the manual), avoiding tests that repeat the code's formula.
- **Product decisions become questions.** The `to-spec` skill says to synthesize the specification without interviewing
  the user (and to confirm only the test boundaries). Since I asked to take part in the decisions, Claude also asked me
  every product decision (search rules, installments, return window, verification-memory time...), and the answers were
  recorded in the issues.
- **Labels and traceability.** Issues with `ready-for-agent`, a status comment on each one, and closing only after
  verifying with the real model (a commit with "Closes #2" once closed an issue too early; it was reopened).

**Where I departed from the skills, or where they hit limits:**
- In some cycles I grouped related tests before implementing (for example the format and expiry ones for order
  verification) instead of one test at a time; and several tests passed on the first run because the previous cycle's code
  already covered them. When that happened I checked that they really fail (mutation check on the reply checker).
- The installed `gh` (2.4) is old: it has no native sub-issues, no issue dependencies and no `--comment` on `close`.
  Dependencies were left as text ("Blocked by") and closing was comment + `close`.
- The domain-modelling skill (`GLOSSARY.md` and ADRs) is configured in `docs/agents/domain.md`, but **I did not use it**:
  decisions were recorded in the issues and in the README. I also did not use the code-review, `grilling`, `prototype` or
  `wizard` skills; the brief asked for a prototype and the specification → tickets → TDD cycle was enough.
- [`CLAUDE.md`](CLAUDE.md) and `docs/agents/` configure the development tool, not the Maestro agent: the agent itself
  depends neither on any skill nor on Claude Code.

## Repository structure

```
src/emporio_agent/   agent code
tests/               163 tests (fake model + real CSVs)
data/                store CSVs and PDF; data/policies/ = the manual as .md sections (Portuguese)
examples/            5 conversations recorded with the real model (English headers, Portuguese transcripts)
scripts/             example recording and documentation-PDF build
docs/                tool configuration (docs/agents/) and maestro-documentation.pdf
SPEC.md              initial specification
complaints.jsonl     (created at run time, ignored by git) complaints and hand-offs
```
