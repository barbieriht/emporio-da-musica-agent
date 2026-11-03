from emporio_agent.agent import Agent, Session
from datetime import datetime
from pathlib import Path

from emporio_agent.catalog import Catalog
from emporio_agent.config import build_model, today
from emporio_agent.orders import Orders
from emporio_agent.policies import STORE_TZ, Policies
from emporio_agent.prompt import GREETING
from emporio_agent.tools import build_catalog_tools, build_order_tools, build_policy_tools, build_return_tools

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

EXIT_WORDS = {"sair", "exit", "quit"}


def build_agent() -> Agent:
    catalog = Catalog.from_csv_dir(DATA_DIR)
    policies = Policies.from_dir(DATA_DIR / "policies")
    orders = Orders.from_csv_dir(DATA_DIR, catalog)
    tools = (
        build_catalog_tools(catalog)
        + build_policy_tools(policies)
        + build_order_tools(orders)
        + build_return_tools(orders, policies, today)
    )
    return Agent(
        model=build_model(),
        tools=tools,
        after_hours_notice=lambda: policies.after_hours_notice(datetime.now(STORE_TZ)),
    )


def main() -> None:
    agent = build_agent()
    session = Session()
    print("Empório da Música — chat com o Maestro (digite 'sair' para encerrar)\n")
    print(f"Maestro: {GREETING}\n")
    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if message.lower() in EXIT_WORDS:
            break
        if message:
            try:
                print(f"Maestro: {agent.respond(session, message)}\n")
            except Exception as error:  # provider outage, quota, network...
                print(
                    "Maestro: Opa, estou com um problema técnico agora. Tente de novo em "
                    "instantes ou fale com a equipe no (67) 3341-4444.\n"
                    f"[detalhe técnico: {type(error).__name__}: {str(error)[:200]}]\n"
                )


if __name__ == "__main__":
    main()
