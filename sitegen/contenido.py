"""Contenido editorial evergreen de El Terracampino.

A diferencia de los scrapers (dato scrapeado de fuente oficial), esto es contenido
redactado: conocimiento hortícola general y fiestas verificadas. Se marca siempre
como orientativo y, en el caso de las fiestas, con su fuente (ficha municipal /
docs/estudio-fuentes-y-viabilidad.md).

NO se inventan datos que aparenten ser oficiales (precios, anuncios de particulares,
alquileres): eso rompería la confianza del medio. Para clasificados (traspasos,
alquileres) la web muestra la sección con un "envía tu anuncio", no datos falsos.
"""

from __future__ import annotations

from datetime import date

# --------------------------------------------------------------- huerta

# Calendario de huerta adaptado a la meseta norte (Tierra de Campos): clima
# continental, heladas tardías hasta bien entrado mayo, veranos secos y calurosos,
# suelo arcilloso. Orientación, NO asesoramiento técnico cerrado (prompt 06).
HUERTA = {
    1: "En enero la tierra descansa. Es tiempo de planificar la temporada, pedir semillas y preparar el terreno con estiércol bien hecho. Si no hiela, se puede plantar ajo y habas. Poda de árboles frutales en días secos.",
    2: "Febrero sigue frío en la meseta. Prepara semilleros protegidos de tomate, pimiento y berenjena en casa o invernadero. Fuera, aún manda la helada: paciencia. Buen mes para ajos si no se plantaron en otoño.",
    3: "En marzo despierta la huerta, pero ojo con las heladas tardías. Siembra directa de guisante, rábano, espinaca, acelga y lechuga de primavera. Sigue con semilleros de solanáceas al abrigo. Prepara los caballones.",
    4: "Abril es mes de trasplante temprano de lo resistente: cebolla, lechuga, acelga. Las heladas todavía pueden aparecer de madrugada, así que no te precipites con el tomate. Siembra zanahoria, remolacha y patata.",
    5: "Mayo es el mes grande de la meseta: cuando pasa el riesgo de helada (mediados de mes), trasplanta tomate, pimiento, berenjena, calabacín y pepino. Siembra judía, calabaza y maíz. Empieza a regar con regularidad.",
    6: "En junio la huerta corre. Riega temprano o al anochecer, nunca al mediodía. Entutora los tomates y quita brotes. Recolecta las primeras lechugas, guisantes, habas y ajos tiernos. Vigila el pulgón.",
    7: "Julio aprieta de calor y seca la tierra. El riego es lo primero: constante y a horas frescas. Recolecta ajo y cebolla para curar, y las primeras judías y calabacines. Aún puedes sembrar judía de ciclo corto y acelga para otoño.",
    8: "Agosto es de plena recolección: tomate, pimiento, berenjena, calabacín, judía. Acolcha el suelo para retener humedad. Empieza a sembrar lo de otoño e invierno: acelga, espinaca, lechuga, rábano, y planteles de coles y puerros.",
    9: "En septiembre baja la noche y se agradece. Trasplanta coles, brócoli, coliflor y puerro. Siembra espinaca, canónigos, rábano y lechuga de otoño. Recoge lo que queda del verano y empieza a limpiar caballones.",
    10: "Octubre cierra el verano. Recolecta calabaza, las últimas judías y los tomates que queden (que maduran en casa). Siembra habas y guisantes de otoño, y ajo. Buen momento para aportar compost y airear la tierra.",
    11: "En noviembre la huerta se recoge. Planta ajo si no lo hiciste, y habas. Recolecta puerro, acelga, col y las raíces de invierno. Protege del frío lo delicado. Recoge hojas para el compostero.",
    12: "Diciembre es de tierra parada y planificación. Se cosecha col, puerro, acelga y cardo. Poda frutales en días sin helada, abona con estiércol y deja descansar el suelo. Repasa las semillas para el año que viene.",
}

MESES_NOMBRE = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def huerta_del_mes(hoy: date) -> dict:
    return {"mes": MESES_NOMBRE[hoy.month].capitalize(), "texto": HUERTA[hoy.month]}


# --------------------------------------------------------------- fiestas

# Fiestas y ferias VERIFICADAS en las fichas municipales (docs/estudio-fuentes-y-viabilidad.md).
# (mes, día|None, nombre). día=None cuando el estudio no fijó fecha exacta (se muestra el mes).
FIESTAS = {
    "villalon-de-campos": [(6, 23, "San Juan"), (6, 29, "San Pedro"), (9, 8, "Virgen de Fuentes")],
    "sahagun": [(6, 12, "San Juan de Sahagún"), (7, 2, "Virgen Peregrina")],
    "valderas": [(7, None, "Ferias y fiestas de julio"), (9, None, "Fiestas patronales (Virgen del Socorro)")],
    "villalpando": [(8, 16, "San Roque"), (12, 8, "Inmaculada Concepción")],
    "paredes-de-nava": [(1, 20, "San Sebastián"), (9, 8, "Virgen de Carejas"), (8, None, "Jornadas Vacceas")],
    "fuentes-de-nava": [(8, 28, "San Agustín")],
    "carrion-de-los-condes": [(7, None, "Feria de Antigüedades, Almoneda y Coleccionismo")],
    "villada": [(11, None, "Feria de la Matanza")],
}


def eventos_comarca(nombre_por_slug: dict, hoy: date, n: int = 8) -> list[dict]:
    """Agenda COMÚN de la comarca: próximas fiestas de todos los pueblos, agregadas."""
    out = []
    hoy_ref = (hoy.month, hoy.day)
    for slug, fiestas in FIESTAS.items():
        pueblo = nombre_por_slug.get(slug, slug)
        for mes, dia, nombre in fiestas:
            ref = (mes, dia or 1)
            clave = (0 if ref >= hoy_ref else 1, mes, dia or 1)
            etiqueta = f"{dia} de {MESES_NOMBRE[mes]}" if dia else MESES_NOMBRE[mes].capitalize()
            out.append((clave, {"pueblo": pueblo, "slug": slug, "cuando": etiqueta, "nombre": nombre}))
    out.sort(key=lambda x: x[0])
    return [x[1] for x in out[:n]]


def proximas_fiestas(slug: str, hoy: date, n: int = 3) -> list[dict]:
    """Devuelve las próximas fiestas del pueblo desde hoy (ciclo anual)."""
    fiestas = FIESTAS.get(slug)
    if not fiestas:
        return []
    orden = []
    for mes, dia, nombre in fiestas:
        # distancia en "día del año" desde hoy, envolviendo al año siguiente
        ref = (mes, dia or 1)
        hoy_ref = (hoy.month, hoy.day)
        futura = ref >= hoy_ref
        clave = (0 if futura else 1, mes, dia or 1)
        etiqueta = f"{dia} de {MESES_NOMBRE[mes]}" if dia else MESES_NOMBRE[mes].capitalize()
        orden.append((clave, {"cuando": etiqueta, "nombre": nombre}))
    orden.sort(key=lambda x: x[0])
    return [x[1] for x in orden[:n]]
