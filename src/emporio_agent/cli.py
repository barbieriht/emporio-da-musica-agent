from emporio_agent.agent import Agent, Session
from emporio_agent.config import build_model

EXIT_WORDS = {"sair", "exit", "quit"}


def main() -> None:
    agent = Agent(model=build_model())
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
            print(f"Maestro: {agent.respond(session, message)}\n")


if __name__ == "__main__":
    main()
