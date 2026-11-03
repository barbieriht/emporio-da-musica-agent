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
    after_hours_notice_shown: bool = False


class Agent:
    def __init__(self, model, tools=(), after_hours_notice=None):
        self._after_hours_notice = after_hours_notice  # callable returning text or None
        self._tools = {t.name: t for t in tools}
        self._model = model.bind_tools(list(tools)) if tools else model

    def respond(self, session: Session, message: str) -> str:
        checkpoint = len(session.history)
        try:
            reply = self._respond(session, message)
        except Exception:
            del session.history[checkpoint:]  # don't keep a half-finished turn
            raise
        return self._with_notice(session, reply)

    def _with_notice(self, session: Session, reply: str) -> str:
        if self._after_hours_notice and not session.after_hours_notice_shown:
            notice = self._after_hours_notice()
            if notice:
                session.after_hours_notice_shown = True
                return f"{notice}\n\n{reply}"
        return reply

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
