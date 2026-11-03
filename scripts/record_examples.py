"""Replays scripted customer messages through the real agent and saves markdown transcripts.

Usage:  uv run python scripts/record_examples.py [scenario-name ...]
Needs a configured provider in .env. Output varies a little between runs (it is an LLM).
"""
import os
import sys
from datetime import datetime
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage

from emporio_agent.agent import Session
from emporio_agent.cli import build_agent
from emporio_agent.config import DEFAULT_MODEL, DEFAULT_PROVIDER
from emporio_agent.prompt import GREETING

OUT_DIR = Path(__file__).resolve().parents[1] / "examples"

# name -> (title, what it shows, AGENT_TODAY or None, customer messages in Portuguese)
SCENARIOS = {
    "01-catalog": (
        "Catalog search and product details",
        "Category and price filter over the real catalog; a follow-up question about one model.",
        None,
        [
            "Quais opções de violões disponíveis custando até R$1000?",
            "Me fala mais do Yamaha F310.",
        ],
    ),
    "02-store-info-and-hours": (
        "Store information and whether it is open now",
        "Manual data (address) and a live check of the opening hours.",
        None,
        [
            "Qual o endereço da loja?",
            "E vocês estão abertos agora?",
        ],
    ),
    "03-out-of-stock-and-installments": (
        "Out-of-stock product, alternatives and installments",
        "Active product with zero stock: the agent does not confirm availability, suggests alternatives and computes installments.",
        None,
        [
            "Vocês têm o violão Giannini GF-3D?",
            "Quanto fica o Shelby SGD-195E? Dá pra parcelar em quantas vezes?",
        ],
    ),
    "04-real-order-return": (
        "Return of a real order (data + policy)",
        "Verification by order number and phone, the return reason and the 7-day window applied to order 7.",
        "2026-02-20",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Pedido 7, telefone (67) 99789-0123.",
        ],
    ),
    "05-out-of-scope-and-privacy": (
        "Out of scope and privacy",
        "A request for accessories, a question unrelated to the store and an attempt to see an order with the wrong phone.",
        None,
        [
            "Vocês vendem cordas e palhetas?",
            "Qual a melhor receita de bolo de chocolate?",
            "Quero ver o pedido 8, meu telefone é (67) 90000-0000.",
        ],
    ),
}


def trace(messages) -> list[str]:
    lines = []
    results = {m.tool_call_id: m for m in messages if isinstance(m, ToolMessage)}
    for m in messages:
        if isinstance(m, AIMessage):
            for call in m.tool_calls:
                result = str(results[call["id"]].content).strip()
                shown = result if len(result) <= 600 else result[:600] + " […]"
                lines.append(f"<details><summary>🔧 <code>{call['name']}({_args(call['args'])})</code></summary>\n\n```\n{shown}\n```\n\n</details>")
    return lines


def _args(args: dict) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in args.items())


def record(name: str) -> Path:
    title, shows, today, messages = SCENARIOS[name]
    if today:
        os.environ["AGENT_TODAY"] = today
    else:
        os.environ.pop("AGENT_TODAY", None)
    agent = build_agent()
    session = Session()
    provider = os.getenv("LLM_PROVIDER", DEFAULT_PROVIDER)
    model = os.getenv("LLM_MODEL", DEFAULT_MODEL)
    out = [
        f"# {title}\n",
        f"{shows}\n",
        f"- Provider/model: `{provider}` / `{model}`",
        f"- Recorded on: {datetime.now():%Y-%m-%d %H:%M}"
        + (f" (date simulated by the agent: `AGENT_TODAY={today}`)" if today else ""),
        "- The conversation is in Portuguese on purpose: the agent answers Brazilian customers in pt-BR.",
        "- The \"🔧\" blocks show the tools the agent called (arguments and result).\n",
        "---\n",
        f"**Maestro:** {GREETING}\n",
    ]
    for message in messages:
        before = len(session.history)
        reply = agent.respond(session, message)
        out.append(f"**Customer:** {message}\n")
        out += [t + "\n" for t in trace(session.history[before:])]
        out.append(f"**Maestro:** {reply}\n")
    path = OUT_DIR / f"{name}.md"
    path.write_text("\n".join(out), encoding="utf-8")
    return path


if __name__ == "__main__":
    names = sys.argv[1:] or list(SCENARIOS)
    for scenario in names:
        print(f"recording {scenario} ...", flush=True)
        print("  ->", record(scenario))
