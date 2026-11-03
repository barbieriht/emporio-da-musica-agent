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
        AIMessage(content="Custa o preço de tabela."),
        after_hours_notice=lambda: NOTICE,
    )
    session = Session()

    first = agent.respond(session, "Vocês têm violão?")
    second = agent.respond(session, "Quanto custa o Yamaha C40?")

    assert first == f"{NOTICE}\n\nClaro, temos violões!"
    assert second == "Custa o preço de tabela."
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


def test_tools_can_reach_the_session_that_is_being_served():
    from emporio_agent import current_session

    seen = []

    @tool
    def peek() -> str:
        """Guarda a sessão atual."""
        seen.append(current_session())
        return "ok"

    call = AIMessage(content="", tool_calls=[{"name": "peek", "args": {}, "id": "c1"}])
    agent, _ = make_agent(call, AIMessage(content="Feito."), tools=[peek])
    session = Session()

    agent.respond(session, "Oi")

    assert seen == [session]
    assert seen[0] is session


# ---------------------------------------------------------------------------
# grounding: values and dates in the final reply must come from tool outputs / the customer
# ---------------------------------------------------------------------------
def price_tool(text):
    @tool
    def get_price() -> str:
        """Devolve o preço."""
        return text

    return get_price


def call_price():
    return AIMessage(content="", tool_calls=[{"name": "get_price", "args": {}, "id": "p1"}])


def test_a_reply_with_a_price_no_tool_returned_is_rewritten():
    agent, model = make_agent(
        call_price(),
        AIMessage(content="O Yamaha custa R$ 699,90."),   # wrong: the tool said 599,90
        AIMessage(content="O Yamaha custa R$ 599,90."),   # corrected after the feedback
        tools=[price_tool("Yamaha C40: R$ 599,90")],
    )
    session = Session()

    reply = agent.respond(session, "Quanto custa o Yamaha C40?")

    assert reply == "O Yamaha custa R$ 599,90."
    assert any("R$ 699,90" in m for m in model.received[2])  # the feedback names the offending value
    assert [m.content for m in session.history if m.type == "ai" and m.content] == ["O Yamaha custa R$ 599,90."]
    assert not any("R$ 699,90" in str(m.content) for m in session.history)


@pytest.mark.parametrize(
    "written",
    ["R$ 1.000,00", "R$ 1000", "R$ 1.000", "R$1000,00", "R$ 1 000,00", "R$ 1 000"],
)
def test_formatting_differences_are_tolerated(written):
    agent, model = make_agent(
        call_price(),
        AIMessage(content=f"Fica {written} à vista."),
        tools=[price_tool("Violão X: R$ 1.000,00")],
    )

    reply = agent.respond(Session(), "Quanto custa?")

    assert reply == f"Fica {written} à vista."
    assert len(model.received) == 2  # accepted at once: no rewrite round


def test_a_value_from_an_earlier_turn_or_from_the_customer_is_legitimate():
    agent, _ = make_agent(
        call_price(),
        AIMessage(content="O Yamaha custa R$ 599,90."),
        AIMessage(content="Continua R$ 599,90, e dentro do seu limite de R$ 800."),
        tools=[price_tool("Yamaha C40: R$ 599,90")],
    )
    session = Session()

    agent.respond(session, "Quanto custa o Yamaha C40?")
    second = agent.respond(session, "Cabe nos meus R$ 800?")

    assert second == "Continua R$ 599,90, e dentro do seu limite de R$ 800."


def test_a_derived_value_is_not_accepted_even_if_the_arithmetic_is_right():
    agent, model = make_agent(
        call_price(),
        AIMessage(content="Você economiza R$ 200,00."),   # 1000 - 800, but no tool said 200
        AIMessage(content="O preço é R$ 800,00, de R$ 1.000,00."),
        tools=[price_tool("De R$ 1.000,00 por R$ 800,00")],
    )

    reply = agent.respond(Session(), "Tem desconto?")

    assert reply == "O preço é R$ 800,00, de R$ 1.000,00."
    assert len(model.received) == 3


def test_replies_without_values_are_never_questioned():
    agent, model = make_agent(AIMessage(content="Posso ajudar com violões, baixos e mais."))

    assert agent.respond(Session(), "Oi") == "Posso ajudar com violões, baixos e mais."
    assert len(model.received) == 1


@pytest.mark.parametrize(
    "written, accepted",
    [
        ("28/02/2026", True),
        ("28/02", True),          # the day and month are known
        ("01/03/2026", False),    # nobody said this date
        ("28/02/2027", False),    # right day and month, wrong year
    ],
)
def test_dates_must_come_from_the_tools_too(written, accepted):
    corrected = AIMessage(content="A previsão é 28/02/2026.")
    agent, model = make_agent(
        call_price(),
        AIMessage(content=f"Chega em {written}."),
        corrected,
        tools=[price_tool("Previsão de entrega: 28/02/2026.")],
    )

    reply = agent.respond(Session(), "Quando chega?")

    assert (reply == f"Chega em {written}.") is accepted
    assert len(model.received) == (2 if accepted else 3)


def test_after_a_second_unsupported_reply_a_safe_message_is_sent_and_nothing_wrong_is_kept():
    agent, model = make_agent(
        call_price(),
        AIMessage(content="Custa R$ 111,00."),
        AIMessage(content="Custa R$ 222,00."),
        tools=[price_tool("Yamaha C40: R$ 599,90")],
    )
    session = Session()

    reply = agent.respond(session, "Quanto custa?")

    assert reply.startswith("Não consegui confirmar os valores com segurança")
    assert "(67) 3341-4444" in reply and "R$" not in reply
    assert not any("111,00" in str(m.content) or "222,00" in str(m.content) for m in session.history)
    assert session.history[-1].content == reply


def test_the_rewrite_round_may_call_a_tool_to_get_the_missing_value():
    agent, model = make_agent(
        AIMessage(content="O Yamaha custa R$ 599,90."),   # from memory: rejected
        call_price(),                                     # after the feedback it consults the tool
        AIMessage(content="O Yamaha custa R$ 599,90."),
        tools=[price_tool("Yamaha C40: R$ 599,90")],
    )

    assert agent.respond(Session(), "Quanto custa o Yamaha C40?") == "O Yamaha custa R$ 599,90."


@pytest.mark.parametrize(
    "sentence",
    [
        "A combinação vale a partir de R$ 1.000.",          # sentence-ending dot after the value
        "Valor: R$ 1.000. Quer ver outras opções?",
        "Fica (R$ 1.000) à vista.",
        "Fica R$ 1.000, sem juros.",
        "São R$ 1.000 em 12 parcelas.",                     # a number right after, after a space
        "Fica R$ 1000.00 no total.",                        # dot as the decimal separator
    ],
)
def test_punctuation_around_a_value_does_not_confuse_the_check(sentence):
    agent, model = make_agent(
        call_price(), AIMessage(content=sentence), tools=[price_tool("Violão X: R$ 1.000,00")]
    )

    assert agent.respond(Session(), "Quanto custa?") == sentence
    assert len(model.received) == 2


def test_unreadable_numbers_never_crash_the_agent():
    garbage = AIMessage(content="Custa R$ 1..2 ou R$ ,5 ou R$ 3.4.5 hoje.")
    agent, _ = make_agent(garbage, garbage)  # no evidence: rewritten once, then the safe message

    assert isinstance(agent.respond(Session(), "Oi"), str)
