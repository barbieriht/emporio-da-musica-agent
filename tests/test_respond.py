import itertools

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from emporio_agent import Agent, Session


class RecordingFakeModel(GenericFakeChatModel):
    """Fake chat model that remembers the messages it received on each call."""

    received: list = []
    system_prompts: list = []

    def _generate(self, messages, *args, **kwargs):
        self.system_prompts.append([m.content for m in messages if m.type == "system"])
        self.received.append([m.content for m in messages if m.type != "system"])
        return super()._generate(messages, *args, **kwargs)


    def bind_tools(self, tools, **kwargs):
        return self


def make_agent(*replies, tools=(), after_hours_notice=None):
    model = RecordingFakeModel(messages=iter(replies), received=[], system_prompts=[])
    return Agent(model=model, tools=list(tools), after_hours_notice=after_hours_notice), model


def test_respond_returns_the_model_reply_to_a_greeting():
    agent, _ = make_agent(AIMessage(content="Fala! Como posso ajudar?"))

    reply = agent.respond(Session(), "Oi!")

    assert reply == "Fala! Como posso ajudar?"


def test_second_turn_sends_the_first_turn_to_the_model():
    agent, model = make_agent(AIMessage(content="Temos várias!"), AIMessage(content="Sim, em natural."))
    session = Session()

    agent.respond(session, "Vocês têm violão?")
    agent.respond(session, "E em cor natural?")

    assert model.received[1] == [
        "Vocês têm violão?",
        "Temos várias!",
        "E em cor natural?",
    ]


@tool
def opening_hours() -> str:
    """Horário de funcionamento da loja."""
    return "Seg a Sex 09h às 18h"


def test_tool_result_is_fed_back_to_the_model_before_the_final_reply():
    call = AIMessage(content="", tool_calls=[{"name": "opening_hours", "args": {}, "id": "c1"}])
    agent, model = make_agent(
        call, AIMessage(content="Abrimos de seg a sex, das 9h às 18h."), tools=[opening_hours]
    )

    reply = agent.respond(Session(), "Que horas vocês abrem?")

    assert reply == "Abrimos de seg a sex, das 9h às 18h."
    assert "Seg a Sex 09h às 18h" in model.received[1]


def test_runaway_tool_calls_stop_with_a_polite_fallback_after_five_model_calls():
    call = AIMessage(content="", tool_calls=[{"name": "opening_hours", "args": {}, "id": "c1"}])
    agent, model = make_agent(*itertools.repeat(call, 100), tools=[opening_hours])
    session = Session()

    reply = agent.respond(session, "Que horas vocês abrem?")

    assert "(67) 3341-4444" in reply
    assert len(model.received) == 5
    # the conversation stays usable: a follow-up turn is accepted
    agent.respond(session, "Oi de novo")


def test_every_model_call_carries_the_maestro_persona_as_a_system_prompt():
    agent, model = make_agent(AIMessage(content="Oi!"), AIMessage(content="Claro!"))
    session = Session()

    agent.respond(session, "Oi")
    agent.respond(session, "Quero um violão")

    for prompts in model.system_prompts:
        assert len(prompts) == 1
        assert "Maestro" in prompts[0]
        assert "assistente virtual" in prompts[0]
        assert "Empório da Música" in prompts[0]


class ExplodingModel(RecordingFakeModel):
    def _generate(self, messages, *args, **kwargs):
        raise RuntimeError("503 UNAVAILABLE")


def test_a_failed_model_call_leaves_the_session_history_untouched():
    agent = Agent(model=ExplodingModel(messages=iter([]), received=[], system_prompts=[]))
    session = Session()

    with pytest.raises(RuntimeError):
        agent.respond(session, "Oi")

    assert session.history == []


NOTICE = "🕘 A loja está fechada agora e reabre em segunda-feira, 09/11, às 09:00."


def test_after_hours_notice_is_shown_only_on_the_first_reply_of_the_session():
    agent, model = make_agent(
        AIMessage(content="Claro, temos violões!"),
        AIMessage(content="Custa R$ 599,90."),
        after_hours_notice=lambda: NOTICE,
    )
    session = Session()

    first = agent.respond(session, "Vocês têm violão?")
    second = agent.respond(session, "Quanto custa o Yamaha C40?")

    assert first == f"{NOTICE}\n\nClaro, temos violões!"
    assert second == "Custa R$ 599,90."
    # the notice is not part of what the model sees as its own previous answer
    assert model.received[1] == ["Vocês têm violão?", "Claro, temos violões!", "Quanto custa o Yamaha C40?"]


def test_a_notice_that_was_not_needed_at_first_is_shown_when_the_store_closes_later():
    states = iter([None, NOTICE, NOTICE])  # open, then closed, then still closed
    agent, _ = make_agent(
        AIMessage(content="Oi!"), AIMessage(content="Temos sim."), AIMessage(content="Tudo certo."),
        after_hours_notice=lambda: next(states),
    )
    session = Session()

    replies = [agent.respond(session, m) for m in ("Oi", "Tem violão?", "Obrigado")]

    assert replies == ["Oi!", f"{NOTICE}\n\nTemos sim.", "Tudo certo."]


def test_a_failed_model_call_does_not_use_up_the_notice():
    agent = Agent(
        model=ExplodingModel(messages=iter([]), received=[], system_prompts=[]),
        after_hours_notice=lambda: NOTICE,
    )
    session = Session()

    with pytest.raises(RuntimeError):
        agent.respond(session, "Oi")

    assert session.after_hours_notice_shown is False
