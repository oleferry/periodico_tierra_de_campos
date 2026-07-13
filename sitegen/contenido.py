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

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

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


# --------------------------------------------------------------- sobre el pueblo

# Contexto evergreen verificado (docs/estudio-fuentes-y-viabilidad.md + patrimonio
# de conocimiento común y comprobable). Es contexto, no noticia. "club" = club
# deportivo de referencia identificado, o None si no se ha verificado ninguno.
PUEBLOS_INFO = {
    "mayorga": {"sobre": "Villa histórica del sur de Tierra de Campos, conocida por la fiesta del Vítor de San Toribio.", "club": None},
    "villalon-de-campos": {"sobre": "Famosa por su Rollo gótico, uno de los mejores de Castilla, y por sus ferias de San Juan y San Pedro.", "club": None},
    "villada": {"sobre": "Conocida por su Feria de la Matanza y su pasado ferroviario en el norte de la comarca.", "club": None},
    "medina-de-rioseco": {"sobre": "La «Ciudad de los Almirantes», nodo patrimonial y turístico de la comarca, con una Semana Santa de Interés Turístico Internacional y el Canal de Castilla a su paso.", "club": None},
    "sahagun": {"sobre": "Cruce del Camino de Santiago y capital del mudéjar leonés, con un rico patrimonio de ladrillo.", "club": None},
    "valderas": {"sobre": "Conjunto histórico del sur de León, con notable patrimonio civil y religioso.", "club": None},
    "carrion-de-los-condes": {"sobre": "Villa jacobea de gran peso patrimonial, con monasterios e iglesias en el Camino de Santiago.", "club": None},
    "paredes-de-nava": {"sobre": "Cuna del escultor Alonso Berruguete y del poeta Jorge Manrique. Celebra las Jornadas Vacceas y la Carrera Vaccea.", "club": "C.D. Villa de Paredes"},
    "becerril-de-campos": {"sobre": "Destaca por Santa María la Antigua, hoy espacio cultural y planetario («San Pedro Cultural»).", "club": "CD Becerril"},
    "fuentes-de-nava": {"sobre": "A orillas de la Laguna de la Nava, uno de los grandes humedales de Castilla y referencia para la observación de aves.", "club": None},
    "villalpando": {"sobre": "Capital histórica de la Tierra de Campos zamorana, conserva restos de sus murallas y un notable casco histórico.", "club": None},
    "villarramiel": {"sobre": "Villa palentina de tradición peletera, en el corazón de Tierra de Campos.", "club": None},
}


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


# --------------------------------------------------------------- almanaque

# NO es "El Calendario Zaragozano": ese es un almanaque comercial en venta
# (editorial propia, ISBN, se sigue publicando cada año) y sus predicciones
# son contenido de autor, no dato público — copiarlas sería plagio de un
# competidor editorial real, no periodismo de datos. Esto es nuestra propia
# versión del mismo GÉNERO (refrán + santo + luna), con fuentes libres:
# refranero de tradición oral anónima (dominio público, sin autor ni editor),
# santoral generado una vez desde Wikipedia/CC BY-SA (scripts/generate_santoral.py)
# y fase lunar calculada por fórmula astronómica (matemática, no de nadie).

# Dichos y refranes de tradición oral castellana/rural, ligados al campo, el
# tiempo y la vida de pueblo — de dominio público, sin autor identificable.
REFRANES = [
    "Año de nieves, año de bienes.",
    "Agua de mayo, pan para todo el año.",
    "En abril, aguas mil.",
    "Cielo aborregado, a las pocas horas mojado.",
    "Cuando el gallo canta a deshora, agua fuera.",
    "Marzo ventoso y abril lluvioso, sacan a mayo florido y hermoso.",
    "Por San Blas, la cigüeña verás; y si no la vieres, año de nieves.",
    "Hasta el cuarenta de mayo, no te quites el sayo.",
    "Si truena en enero, buen añero.",
    "Cuando el humo va al suelo, si no hay agua, hay hielo.",
    "Año de bellotas, año de brotas.",
    "Quien siembra vientos, recoge tempestades.",
    "En martes, ni te cases ni te embarques.",
    "A quien madruga, Dios le ayuda.",
    "No dejes para mañana lo que puedas hacer hoy.",
    "Más vale pájaro en mano que ciento volando.",
    "Cría fama y échate a dormir.",
    "El que a buen árbol se arrima, buena sombra le cobija.",
    "No hay mal que por bien no venga.",
    "A mal tiempo, buena cara.",
    "Donde hay patrón, no manda marinero.",
    "Al pan, pan, y al vino, vino.",
    "Perro ladrador, poco mordedor.",
    "Cada uno cuenta la feria según le va en ella.",
    "En casa del herrero, cuchillo de palo.",
    "No por mucho madrugar amanece más temprano.",
    "El que quiera peces, que se moje el culo.",
    "Nunca llueve a gusto de todos.",
    "Año de heladas, año de hogazas.",
    "Por San Isidro, la golondrina ha venido; y si no ha venido, poco ha de tardar.",
    "Agosto, frío en rostro.",
    "Por San Miguel, la oveja al hato y el pastor al brasero.",
    "Cuando el olmo echa hoja, siembra tu rastrojo.",
    "El que espera, desespera, pero el que siembra, cosecha.",
    "Trigo temprano, trigo temprano; nunca falla, y siempre gana.",
    "Año de muchas brevas, año de pocas piedras.",
    "Verano seco, invierno cubierto.",
    "Del dicho al hecho hay mucho trecho.",
    "Zapatero, a tus zapatos.",
    "El que no llora, no mama.",
    "Más vale tarde que nunca.",
    "En boca cerrada no entran moscas.",
    "El que mucho abarca, poco aprieta.",
    "A cada cerdo le llega su San Martín.",
    "El que siembra en tierra ajena, ni coge ni deja.",
    "Al que madruga, Dios le ayuda, pero al que no, también.",
    "Vísteme despacio, que tengo prisa.",
    "No hay atajo sin trabajo.",
    "El buey suelto bien se lame.",
    "Cuando las barbas de tu vecino veas pelar, echa las tuyas a remojar.",
    "Quien fue a Sevilla, perdió su silla.",
    "Genio y figura, hasta la sepultura.",
    "Piedra movediza, nunca moho la cobija.",
    "A grandes males, grandes remedios.",
    "El que tiene tienda, que la atienda.",
    "Nunca es tarde si la dicha es buena.",
    "El movimiento se demuestra andando.",
    "No hay peor sordo que el que no quiere oír.",
    "Cuando el río suena, agua lleva.",
    "El hábito no hace al monje, pero lo distingue de lejos.",
    "A la tercera va la vencida.",
    "Ojos que no ven, corazón que no siente.",
    "Dime con quién andas y te diré quién eres.",
    "El que a hierro mata, a hierro muere.",
    "En el término medio está la virtud.",
    "No todo el monte es orégano.",
    "El que ríe último, ríe mejor.",
    "Haz bien y no mires a quién.",
    "Camarón que se duerme, se lo lleva la corriente.",
    "Después de la tormenta, llega la calma.",
    "Tanto va el cántaro a la fuente, que al final se rompe.",
    "El que no arriesga, no gana.",
    "A buen entendedor, pocas palabras bastan.",
    "Cada oveja con su pareja.",
    "El que espera lo mucho, espera lo poco.",
    "Poderoso caballero es don Dinero.",
    "Casa con dos puertas, mala es de guardar.",
    "Muchos cocineros, mal guisan el potaje.",
    "El saber no ocupa lugar.",
    "Al hierro candente, batir de repente.",
    "En abril, no te descubras ni un hilo; en mayo, no te descubras ni un cabello.",
]


def refran_del_dia(hoy: date) -> str:
    """Rotación determinista, no aleatoria: mismo día → mismo refrán, en ciclo."""
    return REFRANES[hoy.timetuple().tm_yday % len(REFRANES)]


_SANTORAL: dict[str, str] | None = None


def santo_del_dia(hoy: date) -> str:
    global _SANTORAL
    if _SANTORAL is None:
        path = ROOT / "data" / "santoral.json"
        _SANTORAL = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    clave = f"{hoy.month:02d}-{hoy.day:02d}"
    return _SANTORAL.get(clave, "Sin santo fijo en el calendario romano (29 de febrero)")


def fase_lunar(hoy: date) -> dict:
    """Fase lunar aproximada por cálculo astronómico (ciclo sinódico ≈29.53 días),
    sin depender de ninguna fuente de terceros. Precisión de +-1 día, suficiente
    para una referencia de almanaque."""
    ref = date(2000, 1, 6)  # luna nueva de referencia conocida
    dias = (hoy - ref).days
    ciclo = dias % 29.530588853
    if ciclo < 1.84566:
        return {"fase": "Luna nueva", "emoji": "🌑"}
    if ciclo < 5.53699:
        return {"fase": "Luna creciente", "emoji": "🌒"}
    if ciclo < 9.22831:
        return {"fase": "Cuarto creciente", "emoji": "🌓"}
    if ciclo < 12.91963:
        return {"fase": "Gibosa creciente", "emoji": "🌔"}
    if ciclo < 16.61096:
        return {"fase": "Luna llena", "emoji": "🌕"}
    if ciclo < 20.30228:
        return {"fase": "Gibosa menguante", "emoji": "🌖"}
    if ciclo < 23.99361:
        return {"fase": "Cuarto menguante", "emoji": "🌗"}
    if ciclo < 27.68493:
        return {"fase": "Luna menguante", "emoji": "🌘"}
    return {"fase": "Luna nueva", "emoji": "🌑"}


def almanaque_del_dia(hoy: date) -> dict:
    return {"refran": refran_del_dia(hoy), "santo": santo_del_dia(hoy), "luna": fase_lunar(hoy)}


# --------------------------------------------------------------- leyendas

# Leyendas e historias populares por municipio. SOLO se incluyen las que están
# documentadas (tradición recogida por fuentes verificables: turismo oficial,
# Códice Calixtino, estudios locales) — igual que en el resto del proyecto,
# si no se puede trazar a una fuente, no se publica. Faltan 7 de los 12
# pilotos: pendiente de investigar con la misma exigencia antes de inventar
# nada. "fuente" es orientativa (dónde se puede contrastar), no una URL fija
# que pueda romperse.
LEYENDAS = {
    "mayorga": {
        "titulo": "El fuego que recuerda a San Toribio",
        "texto": "Cuenta la tradición que en 1752 llegó a Mayorga la reliquia de Santo Toribio de Mogrovejo, hijo del pueblo y arzobispo de Lima, defensor de los indígenas americanos. Desde entonces, cada año, la noche de El Vítor el pueblo apaga sus luces y recorre las calles solo con la luz de cientos de pieles de animal untadas en pez que arden en lo alto de varas, siguiendo un camino que se transmite de padres a hijos. Es Fiesta de Interés Turístico Nacional, y en Mayorga no hace falta explicarla: se hace.",
        "fuente": "tradición oral local y crónicas de la Procesión Cívica del Vítor",
    },
    "villalon-de-campos": {
        "titulo": "El rollo que entró en la copla",
        "texto": "En la plaza de Villalón se levanta desde 1523 un rollo de justicia de piedra labrada, de diez metros, único en España por su altura y su filigrana. Marcaba que la villa tenía jurisdicción propia para impartir justicia, hasta la pena capital. Su fama corrió tanto que entró en una copla popular que aún se recita: «Campanas, las de Toledo; iglesia, la de León; reloj, el de Benavente; y rollo, el de Villalón». Que a un pueblo pequeño lo pongan al lado de Toledo o León, en una copla que nadie sabe quién escribió, ya dice algo.",
        "fuente": "Bien de Interés Cultural (1929); copla de tradición oral castellana",
    },
    "medina-de-rioseco": {
        "titulo": "El cocodrilo de Santa María",
        "texto": "En la entrada de la iglesia de Santa María de Medina de Rioseco cuelga, desde hace siglos, la piel reseca de un caimán. La explicación seria es que algún indiano riosecano lo trajo de América como exvoto. Pero la leyenda que se cuenta en el pueblo es otra: que mientras se construía la iglesia, algo destrozaba cada noche el trabajo del día, hasta que se descubrió que era una bestia con forma de cocodrilo. Un preso se ofreció a acabar con ella a cambio de su libertad, y lo consiguió con maña. Desde entonces cuelga ahí, como advertencia y como trofeo.",
        "fuente": "tradición oral riosecana recogida por el turismo local",
    },
    "sahagun": {
        "titulo": "Las lanzas que se hicieron árboles",
        "texto": "El Códice Calixtino, guía de peregrinos del siglo XII, cuenta que Carlomagno acampó donde hoy está Sahagún antes de una batalla, y que sus soldados clavaron las lanzas en el suelo la noche antes de combatir. Al día siguiente las lanzas habían echado raíces y hojas, y de ellas nacieron los bosques que rodeaban la villa. La historia de verdad es otra —Sahagún nace en torno a la tumba de los mártires Facundo y Primitivo—, pero la leyenda de las lanzas es la que quedó escrita, y la que se sigue contando a quien pasa por el Camino de Santiago.",
        "fuente": "Códice Calixtino, libro V (siglo XII)",
    },
    "valderas": {
        "titulo": "El túnel que unía dos castillos",
        "texto": "De abuelos a nietos, junto al fuego en las noches de invierno, en Valderas se ha contado siempre que del castillo salía un pasadizo subterráneo tan largo que llegaba hasta el castillo de Benavente, y otro hasta el de Grajal de Campos. No hay ningún resto que lo confirme. Lo que sí es historia, y no leyenda, es que en el cerco de 1387, cuando un ejército angloportugués asedió la villa, mujeres, niños y ancianos escaparon por una salida secreta del castillo. Puede que la leyenda del túnel no sea más que el recuerdo, agrandado con los años, de aquella salida real.",
        "fuente": "tradición oral local; cerco de Valderas de 1387",
    },
}


def leyenda_de(slug: str) -> dict | None:
    return LEYENDAS.get(slug)
