import itertools

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


def make_agent(*replies, tools=()):
    model = RecordingFakeModel(messages=iter(replies), received=[], system_prompts=[])
    return Agent(model=model, tools=list(tools)), model


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
