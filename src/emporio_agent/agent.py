from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from emporio_agent.prompt import SYSTEM_PROMPT

MAX_MODEL_CALLS = 5
FALLBACK_REPLY = (
    "Desculpe, não consegui concluir isso agora. "
    "Fale com a nossa equipe no (67) 3341-4444."
)


@dataclass
class Session:
    history: list[BaseMessage] = field(default_factory=list)


class Agent:
    def __init__(self, model, tools=()):
        self._tools = {t.name: t for t in tools}
        self._model = model.bind_tools(list(tools)) if tools else model

    def respond(self, session: Session, message: str) -> str:
        checkpoint = len(session.history)
        try:
            return self._respond(session, message)
        except Exception:
            del session.history[checkpoint:]  # don't keep a half-finished turn
            raise

    def _respond(self, session: Session, message: str) -> str:
        session.history.append(HumanMessage(content=message))
        for _ in range(MAX_MODEL_CALLS):
            reply = self._model.invoke([SystemMessage(content=SYSTEM_PROMPT), *session.history])
            session.history.append(reply)
            if not reply.tool_calls:
                return reply.content
            for call in reply.tool_calls:
                result = self._tools[call["name"]].invoke(call["args"])
                session.history.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        session.history.append(AIMessage(content=FALLBACK_REPLY))
        return FALLBACK_REPLY
