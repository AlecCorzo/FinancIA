from interprete import ExtraccionLLM, normalizar


def ext(**cambios):
    base = dict(es_movimiento=True, transcripcion="gasté 25 lucas en almuerzo", tipo="gasto",
                monto=25000, categoria="alimentacion", descripcion="Almuerzo", motivo="")
    base.update(cambios)
    return ExtraccionLLM(**base)


def test_gasto_valido():
    r = normalizar(ext())
    assert r.movimiento.tipo == "gasto"
    assert r.movimiento.monto == 25000
    assert r.movimiento.categoria == "alimentacion"


def test_categoria_con_tilde_y_mayusculas():
    assert normalizar(ext(categoria="Alimentación")).movimiento.categoria == "alimentacion"


def test_categoria_desconocida_queda_en_otros():
    assert normalizar(ext(categoria="mascotas")).movimiento.categoria == "otros"


def test_ingreso_con_categoria_de_gasto_queda_en_otros():
    r = normalizar(ext(tipo="ingreso", categoria="transporte"))
    assert r.movimiento.tipo == "ingreso"
    assert r.movimiento.categoria == "otros"


def test_no_es_movimiento_se_rechaza_con_el_motivo_del_modelo():
    r = normalizar(ext(es_movimiento=False, motivo="No mencionaste un monto.", monto=0, tipo=""))
    assert r.movimiento is None
    assert r.motivo == "No mencionaste un monto."


def test_monto_cero_o_negativo_se_rechaza():
    assert normalizar(ext(monto=0)).movimiento is None
    assert normalizar(ext(monto=-5000)).movimiento is None


def test_tipo_invalido_se_rechaza():
    assert normalizar(ext(tipo="transferencia")).movimiento is None


def test_monto_absurdo_se_rechaza():
    assert normalizar(ext(monto=1e15)).movimiento is None
