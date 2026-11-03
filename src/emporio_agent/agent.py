from contextvars import ContextVar
from dataclasses import dataclass, field

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from emporio_agent import grounding
from emporio_agent.orders import Verification
from emporio_agent.prompt import SYSTEM_PROMPT

MAX_MODEL_CALLS = 5
UNVERIFIED_REPLY = (
    "Não consegui confirmar os valores com segurança agora. Pode falar com a nossa equipe "
    "no (67) 3341-4444 ou pelo WhatsApp (67) 3321-4500?"
)
FALLBACK_REPLY = (
    "Desculpe, não consegui concluir isso agora. "
    "Fale com a nossa equipe no (67) 3341-4444."
)


@dataclass
class Session:
    history: list[BaseMessage] = field(default_factory=list)
    after_hours_notice_shown: bool = False
    verification: Verification = field(default_factory=Verification)


_current_session: ContextVar[Session] = ContextVar("current_session")


def current_session() -> Session:
    """The session being served; tools use it to read/update per-session state."""
    return _current_session.get()


class Agent:
    def __init__(self, model, tools=(), after_hours_notice=None):
        self._after_hours_notice = after_hours_notice  # callable returning text or None
        self._tools = {t.name: t for t in tools}
        self._model = model.bind_tools(list(tools)) if tools else model

    def respond(self, session: Session, message: str) -> str:
        checkpoint = len(session.history)
        token = _current_session.set(session)
        try:
            reply = self._respond(session, message)
        except Exception:
            del session.history[checkpoint:]  # don't keep a half-finished turn
            raise
        finally:
            _current_session.reset(token)
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
        rejected: list[BaseMessage] = []  # rejected reply + feedback: removed from the history at the end
        try:
            for _ in range(MAX_MODEL_CALLS):
                reply = self._model.invoke([SystemMessage(content=SYSTEM_PROMPT), *session.history])
                session.history.append(reply)
                if reply.tool_calls:
                    for call in reply.tool_calls:
                        result = self._tools[call["name"]].invoke(call["args"])
                        session.history.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
                    continue
                text = _text(reply.content)
                problems = grounding.unsupported(text, _evidence(session.history))
                if not problems:
                    return text
                rejected.append(reply)
                if len(rejected) > 1:
                    session.history.append(AIMessage(content=UNVERIFIED_REPLY))
                    return UNVERIFIED_REPLY
                feedback = HumanMessage(content=_feedback(problems))
                session.history.append(feedback)
                rejected.append(feedback)
            session.history.append(AIMessage(content=FALLBACK_REPLY))
            return FALLBACK_REPLY
        finally:
            session.history[:] = [m for m in session.history if not any(m is r for r in rejected)]


def _text(content) -> str:
    """Reply text; some providers return a list of content blocks instead of a string."""
    if isinstance(content, str):
        return content
    return "".join(part if isinstance(part, str) else part.get("text", "") for part in content)


def _evidence(history: list[BaseMessage]) -> str:
    """Texts a value may legitimately come from: tool results and what the customer wrote."""
    return "\n".join(str(m.content) for m in history if m.type in ("tool", "human"))


def _feedback(problems: list[str]) -> str:
    return (
        "Sua resposta citou valores ou datas que não aparecem nos resultados das ferramentas nem na "
        f"conversa: {', '.join(problems)}. Reescreva a resposta sem citar valores que você não tem; se "
        "precisar deles, consulte a ferramenta adequada ou diga que não tem a informação."
    )
