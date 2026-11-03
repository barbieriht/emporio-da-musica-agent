from langchain_core.tools import tool

from emporio_agent.catalog import Catalog, Product
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
        lines = [format_product(product)]
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
