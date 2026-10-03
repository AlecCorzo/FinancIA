import unicodedata

CATEGORIAS_GASTO = {
    "alimentacion", "transporte", "vivienda", "servicios", "salud",
    "educacion", "entretenimiento", "compras", "otros",
}
CATEGORIAS_INGRESO = {"salario", "ventas", "otros"}
CATEGORIAS = CATEGORIAS_GASTO | CATEGORIAS_INGRESO


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_categoria(valor: str | None, tipo: str | None = None) -> str:
    """Lleva cualquier categoría a una de la lista. Si no encaja, devuelve 'otros'."""
    categoria = _sin_tildes((valor or "").strip().lower())
    if categoria not in CATEGORIAS:
        return "otros"
    if tipo == "ingreso" and categoria not in CATEGORIAS_INGRESO:
        return "otros"
    if tipo == "gasto" and categoria not in CATEGORIAS_GASTO:
        return "otros"
    return categoria
