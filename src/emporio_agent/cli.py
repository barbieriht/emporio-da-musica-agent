from emporio_agent.agent import Agent, Session
from pathlib import Path

from emporio_agent.catalog import Catalog
from emporio_agent.config import build_model
from emporio_agent.tools import build_catalog_tools

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

EXIT_WORDS = {"sair", "exit", "quit"}


def main() -> None:
    catalog = Catalog.from_csv_dir(DATA_DIR)
    agent = Agent(model=build_model(), tools=build_catalog_tools(catalog))
    session = Session()
    print("Empório da Música — chat com o Maestro (digite 'sair' para encerrar)\n")
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
