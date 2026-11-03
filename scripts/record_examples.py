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

# name -> (title, what it shows, AGENT_TODAY or None, customer messages)
SCENARIOS = {
    "01-catalogo": (
        "Busca no catálogo e detalhes de um produto",
        "Filtro por categoria e preço sobre o catálogo real; pergunta de acompanhamento sobre um modelo.",
        None,
        [
            "Quais opções de violões disponíveis custando até R$1000?",
            "Me fala mais do Yamaha F310.",
        ],
    ),
    "02-loja-e-horario": (
        "Informações da loja e se está aberta agora",
        "Dados do manual (endereço) e consulta em tempo real ao horário de funcionamento.",
        None,
        [
            "Qual o endereço da loja?",
            "E vocês estão abertos agora?",
        ],
    ),
    "03-sem-estoque-e-parcelamento": (
        "Produto sem estoque, alternativas e parcelamento",
        "Produto ativo com estoque zero: o agente não confirma disponibilidade, sugere alternativas e calcula parcelas.",
        None,
        [
            "Vocês têm o violão Giannini GF-3D?",
            "Quanto fica o Shelby SGD-195E? Dá pra parcelar em quantas vezes?",
        ],
    ),
    "04-devolucao-pedido-real": (
        "Devolução de um pedido real (dados + política)",
        "Verificação por número do pedido e telefone, motivo da devolução e janela de 7 dias aplicada ao pedido 7.",
        "2026-02-20",
        [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Pedido 7, telefone (67) 99789-0123.",
        ],
    ),
    "05-fora-do-escopo-e-privacidade": (
        "Fora do escopo e privacidade",
        "Pedido de acessórios, pergunta sem relação com a loja e tentativa de ver um pedido com telefone errado.",
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
        f"- Provedor/modelo: `{provider}` / `{model}`",
        f"- Gravado em: {datetime.now():%Y-%m-%d %H:%M}"
        + (f" (data simulada pelo agente: `AGENT_TODAY={today}`)" if today else ""),
        "- Os blocos \"🔧\" mostram as ferramentas que o agente chamou (argumentos e resultado).\n",
        "---\n",
        f"**Maestro:** {GREETING}\n",
    ]
    for message in messages:
        before = len(session.history)
        reply = agent.respond(session, message)
        out.append(f"**Cliente:** {message}\n")
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
