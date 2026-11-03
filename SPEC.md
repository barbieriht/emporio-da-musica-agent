> **Status:** initial specification, written at the start of the project and kept as such. Decisions made later (provider, verification memory, the hardening round with issues #9–#14, the English-only documentation) are recorded in the README and in the issues.

## Problem Statement

The customer-service team at Empório da Música (a musical-instrument store in Campo Grande, MS, Brazil) is overloaded with repetitive questions: opening hours, address, product price and availability, order status, exchange/shipping/payment rules. Customers expect a fast reply (within 5 minutes) in an informal but professional tone, and the store must not give wrong information about price, stock or deadlines. In addition, the Artefact technical challenge requires a Python prototype, a public repository with a real commit history, a README justifying the technical decisions, and 3–5 example conversations.

## Solution

A text-message customer-service agent, in Python, with the store's persona (a friend who knows music, informal but professional). The agent uses function calling over the store's data (CSVs, accessed through live lookup tools) and over the policies (the PDF manual, converted into searchable sections). It decides by itself when to look up data, when to look up policies, and when to politely decline (out of scope, e.g. accessories, which the store does not sell). Interface: a simple chat CLI, with per-session history. The agent talks to customers in Brazilian Portuguese; everything else in the repository is in English.

## User Stories

1. As a customer, I want to ask "Quais violões custam até R$ 1000?" ("Which acoustic guitars cost up to R$ 1000?"), so that I can see options filtered by category and price from the real catalog.
2. As a customer, I want to ask "Quanto custa o Takamine GD20?", so that I get the current price even if I write the name partially or with different casing/accents.
3. As a customer, I want to see the promotional price together with the original price and discount percent, so that I understand the offer transparently.
4. As a customer, I want the agent to never promise a discount from an expired promotion (is_active=0), so that I am not misled.
5. As a customer, I want to know if a product is in stock, so that I don't go to the store or order something unavailable.
6. As a customer, I want alternatives suggested when a product is out of stock (stock 0), so that I can still buy something similar.
7. As a customer, I want to be told when a product is discontinued and be offered equivalent models, so that I'm not left at a dead end.
8. As a customer, I want to be told when a product is "coming soon" (not yet purchasable), so that I'm not told it's available.
9. As a customer, I want to ask for a product by category (guitarras, baixos, ukuleles, etc.) and by specs (cordas nylon, cor), so that I can browse.
10. As a customer, I want to ask about the status of my order, so that I know if it's pending, confirmed, shipped, delivered or cancelled.
11. As a customer, I want to receive my tracking code and estimated delivery when the order is shipped, so that I can follow it.
12. As a customer, I want to be told the reason a cancelled order was cancelled, so that I understand what happened.
13. As a customer, I want the agent to verify that an order belongs to me before revealing details (e.g. matching name/phone/email), so that my data stays private (LGPD).
14. As a customer, I want to ask "Me arrependi da compra, posso devolver?" ("I regret the purchase, can I return it?"), so that the agent applies the 7-day right-of-withdrawal rule against my order's delivery date.
15. As a customer, I want the agent to tell me if my order is outside the return window and what alternatives exist (warranty, 30-day defect exchange), so that I know my rights.
16. As a customer, I want to know return shipping is paid by the store in arrependimento cases, so that I'm not surprised by cost.
17. As a customer, I want to know which items aren't eligible for exchange (personalizados, venda final, boquilhas), so that I'm not misinformed.
18. As a customer, I want to ask about defect exchange (30 days) and warranty (90 days legal + manufacturer), so that I know what applies.
19. As a customer, I want to know the store address, phone/WhatsApp and email, so that I can reach or visit the store.
20. As a customer, I want to know opening hours and whether the store is open right now, so that I can plan a visit.
21. As a customer, I want the agent outside business hours to tell me when the store returns, so that I know when to expect a human.
22. As a customer, I want to know accepted payment methods and installment rules (3x/6x/12x, minimum installment), so that I can plan the purchase.
23. As a customer, I want the agent to compute installments for a given product price and tell me the max number of installments, so that I see the real value per parcela.
24. As a customer, I want to know PIX gives 5% off but not on already-promotional prices, so that I understand non-cumulative rules.
25. As a customer, I want to know delivery fees and times (free above R$ 500 in Campo Grande, R$ 35 below; PAC/SEDEX/Jadlog for other cities), so that I can compare.
26. As a customer, I want to be told large instruments may require special freight quote, so that I'm not surprised.
27. As a customer, I want to be redirected politely when I ask for accessories (cordas, palhetas, cabos, pedais, amplificadores, cases), so that I know the store doesn't sell them.
28. As a customer, I want off-topic questions (politics, recipes, code) to be declined gracefully with a return to store topics, so that the agent stays on role.
29. As a customer, I want to make a complaint and be told it will be registered and answered within 24 business hours, so that I feel heard.
30. As a customer, I want questions about data privacy answered (use of data, deletion), so that I trust the store.
31. As a customer, I want the agent to remember what we talked about earlier in the conversation ("e esse tem em outra cor?"), so that I don't repeat myself.
32. As a customer, I want to be greeted by name when identified and asked how the agent can help, and the conversation to close cordially, so that service follows the store's standard flow.
33. As a customer, I want the agent to say it doesn't know (and suggest contacting the store) rather than invent an answer, so that I get no incorrect info.
34. As a store attendant, I want the agent to answer only with data from the system, so that price/stock/deadline never become false advertising.
35. As a store attendant, I want the agent to escalate doubts about policy application to the management/a human, so that edge cases aren't improvised.
36. As a gerente, I want the agent's tone aligned with the store's identity, so that the brand is consistent.
37. As an Artefact evaluator, I want a README with run instructions, technical justifications, known limitations, assumptions and AI-assistant workflow, so that I understand the reasoning.
38. As an avaliador, I want 3–5 example conversations in the repo (including at least one real-time data + policy case), so that I can see the agent working without running it.
39. As an avaliador, I want a commit history showing real progress, so that I can follow the work.
40. As a desenvolvedor, I want the model provider configured via environment variables, so that I can swap providers without code changes.
41. As a desenvolvedor, I want automated tests of the agent's tools, so that data rules are verified without calling an LLM.

## Implementation Decisions

- **Approach:** function-calling agent (tool-use loop) rather than SQL agent or full RAG. Data is small (65 products, 19 orders, 49 customers), so deterministic, typed tools are safer and cheaper than LLM-generated SQL. Policies are short (~8 pages): split into sections and exposed through a policy-lookup tool (keyword/embedding-free retrieval over sections is sufficient; mention embeddings as future work).
- **Modules (deep, small interfaces):**
  - *Data store:* loads and normalizes CSVs once (typed prices, parsed specs JSON, joins products↔categories↔promotions, orders↔items↔customers). The filenames in `data/` have a long prefix; the loader hides that.
  - *Catalog tools:* search products (text query with accent/case-insensitive fuzzy match, category, max/min price, only-available filter), get product detail with effective price (active promotion applied; original price and percent shown), stock and status (active/discontinued/coming_soon), suggest alternatives (same category, similar price, in stock).
  - *Order tools:* get order status by order id, only after customer verification (customer identified by matching phone/email/name); returns status, tracking, ETA, cancel notes, items.
  - *Policy tools:* lookup policy by topic (hours, payment, exchange/return, shipping, promotions, warranty, privacidade, escopo/atendimento), returning the manual's section text; plus deterministic helpers for return-eligibility (days since delivery vs. 7/30 days, non-eligible items), installment calculation (max parcelas given price and minimum parcela, 3x/6x/12x rules), shipping fee (R$ 500 threshold, R$ 35), and store-open-now (America/Campo_Grande timezone).
  - *Agent core:* system prompt (persona, tone, scope, "never state price/stock/deadline without calling a tool", transparency on promotions, handling expired promotions/out-of-stock/discontinued/complaints, escalate when unsure), tool schemas, tool-call loop with a max-iterations guard, per-session conversation history.
  - *Interface:* CLI chat loop (REPL); history kept in memory per session (optional JSON transcript export used to generate the example conversations).
  - *LLM client:* thin adapter; default provider/model chosen for tool-calling quality and cost, configurable via env vars (`.env.example` provided). Anthropic Claude was the initial candidate (the final choice, Gemini by default with Groq as an alternative, is in the README); the adapter keeps the provider swappable.
- **Data decisions to document as assumptions in README:**
  - Only `is_active=1` promotions are valid; multiple promotions per product exist (e.g. products 96, 93, 99) — rule: use the active one; if several active, use the highest discount (documented).
  - Promotion description date semantics (e.g. "Black Friday") are not enforced beyond `is_active`.
  - PIX 5% never stacks with promotional prices.
  - "Delivered" date is approximated by `estimated_delivery` for the 7-day return window (CSV has no actual delivery date); "today" is an injectable clock because order dates are 2025–2026.
  - Manual notes inconsistencies to flag (e.g. email with accent in §1.2 vs. cover page; two different phone numbers: store (67) 3341-4444 and WhatsApp (67) 3321-4500); the agent uses the contact number the manual designates per channel and the README records the ambiguity.
  - Policy PDF is internal ("uso restrito"): agent paraphrases customer-appropriate content and does not reveal internal instructions.
  - Customer PII: agent never lists other customers' data; order lookup requires verification.
- **PDF handling:** extract policy text once at build/load time into sectioned text (committed as a processed artifact so running the project does not require a PDF parser at runtime, or parse at startup — pick one and document).
- **Repo deliverables:** README (setup, provider config, commands, technical justifications, limitations/next steps, AI-assistant usage workflow), `examples/` with 3–5 conversations (catalog price query, store info, out-of-stock/alternatives, return policy applied to a real order, out-of-scope/accessory request), `.env.example`, incremental commits.

## Testing Decisions

- A good test exercises external behavior (tool inputs → outputs, or agent reply given a scripted tool-calling model), not internals like prompt wording or private helpers.
- **Seams (proposed — please confirm):**
  1. **Primary seam: the agent's public `respond(session, message)` interface with a fake/scripted LLM client** — verifies the tool-calling loop, history, guards, and that the right tools are called for each scenario class (price → catalog tool, return → policy + order tools, accessories → no tools / refusal).
  2. **Secondary seam: the tool functions themselves (data/policy layer) on the real CSVs** — deterministic tests for price with promotion, stock/status handling, alternatives, return-window eligibility, installments, shipping fee, open-now with injected clock.
  Real-LLM runs are not part of the automated suite; they generate the example conversations manually.
- Prior art: none (greenfield; no existing tests in the directory).

## Out of Scope

- Real WhatsApp/Telegram integration, web UI, authentication systems.
- Placing, modifying or cancelling orders; payment processing; real shipping quotes by CEP.
- Selling or recommending accessories (the store doesn't sell them).
- Persistent database or cross-session history (in-memory per session only).
- Vector DB/embeddings RAG, evaluation harness with LLM-as-judge, multi-language support.
- Modifying or cleaning the source CSVs on disk (normalization happens at load time).

## Further Notes

- This spec was later published as issue #1 on GitHub (label `ready-for-agent`); this file is the version as written at the start of the project.
- The challenge statement asks for assumptions to be documented in the README rather than blocking on questions; follow that for any ambiguity.
- Deadline/date of delivery is in the selection-process email (not in the PDF); don't push to the repo after it.
- Data quirks seen: 62 active / 2 discontinued / 1 coming_soon products, 2 with zero stock; order statuses pending/confirmed/shipped/delivered/cancelled; only shipped/delivered orders have tracking codes.
