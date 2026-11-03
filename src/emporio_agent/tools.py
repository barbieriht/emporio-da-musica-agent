from langchain_core.tools import tool

from emporio_agent.catalog import Catalog, Product

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
