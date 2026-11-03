# Language note: tool descriptions (what the LLM reads to choose a tool) and tool outputs (what the LLM
# turns into the reply to a Brazilian customer) are deliberately in Brazilian Portuguese; comments and
# identifiers are in English.
from langchain_core.tools import tool

from emporio_agent.catalog import Catalog, Product
from emporio_agent.complaints import Complaints
from emporio_agent.orders import Orders
from emporio_agent.policies import Policies

_AVAILABILITY_PT = {
    "available": "disponível",
    "out_of_stock": "sem estoque no momento",
    "discontinued": "descontinuado (fora de catálogo)",
    "coming_soon": "em breve (ainda não disponível para compra)",
}


def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_product(p: Product) -> str:
    if p.discount_percent:
        price = f"de {_brl(p.list_price)} por {_brl(p.price)} ({p.discount_percent}% de desconto)"
    else:
        price = _brl(p.price)
    return f"[id {p.id}] {p.name} ({p.category}): {price} — {_AVAILABILITY_PT[p.availability]}"


def build_catalog_tools(catalog: Catalog) -> list:
    @tool
    def search_products(
        query: str = "",
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
    ) -> str:
        """Busca produtos no catálogo. Use para perguntas sobre modelos, categorias
        (Guitarras, Baixos, Baterias e Percussão, Teclados e Pianos, Violões, Instrumentos de
        Sopro, Cordas Orquestrais, Ukuleles), preços ou disponibilidade. 'query' é texto livre
        (marca, modelo, tipo); max_price/min_price em reais. Se houver vários resultados
        parecidos, pergunte ao cliente qual deseja."""
        results = catalog.search_products(query, category, min_price, max_price)
        if not results:
            return "Nenhum produto encontrado para esses critérios."
        return "\n".join(format_product(p) for p in results)

    @tool
    def get_product_details(product_id: int) -> str:
        """Detalhes de um produto pelo id (preço atual, promoção, disponibilidade).
        Se o produto estiver indisponível, já traz alternativas semelhantes."""
        product = catalog.get_product(product_id)
        if product is None:
            return "Produto não encontrado."
        lines = [format_product(product), f"Descrição: {product.description}"]
        if product.specs:
            lines.append("Especificações: " + ", ".join(f"{k}: {v}" for k, v in product.specs.items()))
        if product.availability != "available":
            alternatives = catalog.suggest_alternatives(product_id)
            lines.append("Alternativas disponíveis:")
            lines += [format_product(p) for p in alternatives] or ["(nenhuma alternativa semelhante)"]
        return "\n".join(lines)

    return [search_products, get_product_details]


def build_policy_tools(policies: "Policies") -> list:
    from datetime import datetime

    from emporio_agent.policies import STORE_TZ

    topics = ", ".join(policies.topics())

    @tool(
        description=(
            "Consulta o manual de políticas da loja. Tópicos disponíveis: "
            f"{topics}. Use para endereço/contatos (loja), horários, formas de pagamento, "
            "trocas e devoluções, frete, promoções, diretrizes de atendimento, garantia e privacidade."
        )
    )
    def get_policy(topic: str) -> str:
        text = policies.lookup(topic)
        return text if text is not None else f"Tópico desconhecido. Tópicos: {topics}."

    @tool
    def get_installments(price: float) -> str:
        """Opções de parcelamento no cartão de crédito (sem juros) para um valor em reais."""
        options = policies.installment_options(price)
        top = options[-1]
        return (
            f"Até {top.n}x de {_brl(top.value)} sem juros. Opções: "
            + ", ".join(f"{o.n}x de {_brl(o.value)}" for o in options)
        )

    @tool
    def get_shipping_quote(order_total: float, city: str) -> str:
        """Frete e prazo de entrega para o valor do pedido (em reais) e a cidade de destino."""
        quote = policies.shipping_quote(order_total, city)
        if quote.fee is None:
            return (
                f"Fora de Campo Grande: frete calculado pelo CEP, peso e dimensões. "
                f"Prazos: {quote.delivery_time}."
            )
        fee = "frete grátis" if quote.fee == 0 else f"taxa fixa de {_brl(quote.fee)}"
        return f"Campo Grande: {fee}, entrega em {quote.delivery_time}."

    @tool
    def is_store_open_now() -> str:
        """Informa se a loja está aberta agora e, se fechada, quando abre novamente."""
        status = policies.store_status(datetime.now(STORE_TZ))
        if status.is_open:
            return "A loja está aberta agora."
        note = f" (hoje é feriado nacional: {status.holiday})" if status.holiday else ""
        return (
            f"A loja está fechada agora{note}. Abre em "
            f"{status.next_open:%d/%m/%Y às %H:%M}. Em feriados locais ou móveis, confirmar com a loja."
        )

    return [get_policy, get_installments, get_shipping_quote, is_store_open_now]


_STATUS_PT = {
    "pending": "pendente (ainda não confirmado)",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


def _payment_pt(method: str) -> str:
    if method.startswith("credit_"):
        return f"cartão de crédito em {method.removeprefix('credit_')}"
    return {"pix": "PIX", "debit": "cartão de débito", "boleto": "boleto"}.get(method, method)


_CONTACTS = "telefone (67) 3341-4444 ou WhatsApp (67) 3321-4500"


def _resolve_order(orders: "Orders", now, order_id: int, phone: str | None):
    """Verify access to an order using the session's remembered verification.

    Returns (order, None) on success or (None, message_for_the_agent) otherwise."""
    from emporio_agent.agent import current_session

    result = orders.lookup(order_id, phone, current_session().verification, now())
    if result.status == "found":
        return result.order, None
    messages = {
        "invalid_order": "O número do pedido é inválido. Peça ao cliente o número correto. Nada foi consultado.",
        "invalid_phone": (
            "O telefone informado parece inválido (precisa de DDD + 8 ou 9 dígitos). Peça de novo. "
            "Nada foi consultado."
        ),
        "verification_needed": (
            ("A verificação anterior expirou por tempo. " if result.expired else "")
            + "Para consultar este pedido é preciso o telefone usado na compra: peça ao cliente."
        ),
        "not_verified": (
            "Não consegui confirmar esse pedido com esses dados. Não revele qual dado falhou. "
            f"Sugira conferir o número do pedido e o telefone usado na compra, ou falar com a equipe: {_CONTACTS}."
        ),
    }
    return None, messages[result.status]


def build_order_tools(orders: "Orders", now) -> list:
    @tool
    def get_order_status(order_id: int, phone: str | None = None) -> str:
        """Consulta o status de um pedido. Peça ao cliente o número do pedido e o telefone usado
        na compra; nunca invente dados. Depois de uma verificação bem-sucedida, o telefone fica
        lembrado por alguns minutos nesta conversa: nesse período basta o número do pedido (omita
        'phone'), só para pedidos do mesmo cliente. Se a ferramenta pedir o telefone, peça ao
        cliente. Retorna status, itens, total, pagamento, rastreio, previsão de entrega ou motivo
        do cancelamento."""
        order, problem = _resolve_order(orders, now, order_id, phone)
        if order is None:
            return problem
        lines = [
            f"Pedido {order.id} de {order.customer_first_name}, feito em {order.order_date:%d/%m/%Y}.",
            f"Status: {_STATUS_PT[order.status]}.",
            "Itens: " + ", ".join(f"{i.quantity}x {i.name}" for i in order.items) + ".",
            f"Total: {_brl(order.total)} ({_payment_pt(order.payment_method)}).",
        ]
        if order.tracking_code:
            lines.append(f"Código de rastreio: {order.tracking_code}.")
        if order.estimated_delivery:
            lines.append(f"Previsão de entrega: {order.estimated_delivery:%d/%m/%Y}.")
        if order.cancel_reason:
            lines.append(f"Motivo do cancelamento: {order.cancel_reason}.")
        return "\n".join(lines)

    return [get_order_status]


def build_return_tools(orders: "Orders", policies: "Policies", today, now) -> list:
    """`today` and `now` are zero-argument callables (current date / current datetime)."""
    from emporio_agent.returns import assess_return

    @tool
    def check_return_eligibility(order_id: int, reason: str, phone: str | None = None) -> str:
        """Verifica se um pedido pode ser devolvido ou trocado. Exige o número do pedido, a mesma
        verificação do status de pedido (telefone da compra, lembrado por alguns minutos após uma
        verificação bem-sucedida; omita 'phone' nesse caso) e o motivo, que você deve perguntar
        ao cliente se ele não disse: 'arrependimento' (desistiu da compra),
        'preferencia' (quer trocar cor/modelo) ou 'defeito' (problema de fabricação)."""
        if reason not in ("arrependimento", "preferencia", "defeito"):
            return "Motivo inválido. Use arrependimento, preferencia ou defeito."
        order, problem = _resolve_order(orders, now, order_id, phone)
        if order is None:
            return problem
        r = assess_return(order, reason, today())
        d = lambda x: f"{x:%d/%m/%Y}"  # noqa: E731
        if r.outcome == "eligible":
            text = f"Dentro do prazo: o cliente pode solicitar até {d(r.deadline)} (restam {r.days_left} dia(s))."
        elif r.outcome == "expired":
            text = f"Fora do prazo: terminou em {d(r.deadline)}."
            if r.legal_warranty_until:
                state = "ainda vigente" if r.in_legal_warranty else "encerrada"
                text += (
                    f" Garantia legal de 90 dias contra defeito de fabricação {state} "
                    f"(até {d(r.legal_warranty_until)}). A garantia do fabricante, se houver, está no "
                    "certificado do produto, e a loja pode intermediar mediante solicitação."
                )
        elif r.outcome == "not_received_yet":
            text = (
                f"O pedido ainda não foi entregue (previsão {d(r.starts_on)}); o prazo só começa "
                "a contar do recebimento."
            )
        elif r.outcome == "not_shipped":
            text = "O pedido ainda não foi enviado, então não há devolução; para cancelar, falar com a equipe."
        else:
            text = "O pedido está cancelado: não há o que devolver."
        return (
            f"{text}\n\nAssuma compra online. Se o item for personalizado/sob encomenda ou venda final, "
            "ou a compra tiver sido na loja física, confirme com a equipe.\n\n"
            "Regras do manual:\n" + (policies.lookup("trocas-devolucoes") or "")
        )

    return [check_return_eligibility]


def build_complaint_tools(complaints: "Complaints") -> list:
    contacts = "telefone (67) 3341-4444 ou WhatsApp (67) 3321-4500"

    def _save(action, text: str, contact: str, done: str) -> str:
        try:
            registration = action(text, contact)
        except ValueError:
            return "Faltou a descrição ou o contato (telefone ou e-mail) do cliente. Peça o que falta; nada foi registrado."
        except OSError:
            return (
                "NÃO foi possível registrar agora. Não diga ao cliente que foi registrado; peça desculpas "
                f"e oriente a falar com a equipe: {contacts}."
            )
        return f"{done} Protocolo {registration.protocol}. A equipe retorna em até 24 horas úteis."

    @tool
    def register_complaint(description: str, contact: str) -> str:
        """Registra uma reclamação do cliente. Só chame depois de ouvir o cliente e ter o contato
        dele (telefone ou e-mail) para o retorno; descreva o problema em uma ou duas frases.
        Só diga que a reclamação foi registrada se esta ferramenta confirmar."""
        return _save(complaints.register_complaint, description, contact, "Reclamação registrada.")

    @tool
    def request_human_handoff(reason: str, contact: str) -> str:
        """Encaminha o cliente para a equipe/gerência quando o assunto foge do que você pode
        resolver (dúvida sobre aplicação de política, cancelamento de pedido, compra ou reserva).
        Precisa do contato do cliente (telefone ou e-mail). Só diga que foi encaminhado se
        esta ferramenta confirmar."""
        return _save(complaints.request_handoff, reason, contact, "Encaminhado para a equipe.")

    return [register_complaint, request_human_handoff]


def build_payment_tools(catalog: Catalog, policies: "Policies") -> list:
    @tool
    def get_payment_options(product_id: int) -> str:
        """Formas de pagamento de um produto pelo id: preço no PIX (5% só se o produto não estiver
        em promoção), débito, boleto, parcelas no crédito sem juros e se dá para combinar formas de
        pagamento. Use sempre que o cliente perguntar como pagar, PIX, desconto à vista ou parcelas
        de um produto; não calcule esses valores de cabeça."""
        product = catalog.get_product(product_id)
        if product is None:
            return "Produto não encontrado."
        options = policies.payment_options(product.price, is_promotional=product.discount_percent is not None)
        top = options.installments[-1]
        lines = [format_product(product)]
        if options.pix_price is not None:
            lines.append(f"PIX: {_brl(options.pix_price)} (5% de desconto sobre o preço de tabela).")
        else:
            lines.append("PIX: sem o desconto de 5%, porque o preço já é promocional (promoções não são cumulativas).")
        lines.append(f"Cartão de débito: {_brl(product.price)} à vista.")
        lines.append(f"Boleto: {_brl(product.price)} à vista (compensação em até 3 dias úteis).")
        lines.append(
            f"Cartão de crédito: até {top.n}x de {_brl(top.value)} sem juros. Opções: "
            + ", ".join(f"{i.n}x de {_brl(i.value)}" for i in options.installments)
        )
        if options.combined_payment_allowed:
            lines.append("Dá para combinar formas de pagamento (ex.: PIX + cartão), pois a compra passa de R$ 2.000.")
        else:
            lines.append("Combinar formas de pagamento só é permitido em compras acima de R$ 2.000.")
        if product.availability != "available":
            lines.append("Atenção: o produto não está disponível para compra agora; avise o cliente.")
        return "\n".join(lines)

    return [get_payment_options]
