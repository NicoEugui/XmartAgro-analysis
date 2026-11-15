# Cómo funciona XmartAgro, de la A a la Z

Este documento es para cualquiera del equipo: explica qué hace el sistema, cómo está pensado, qué está construido, qué se emula en el
front y qué es real o simulado. No hace falta saber programar para leer las secciones 1 a 8. Los nombres entre comillas invertidas
(`así`) son archivos o comandos del repositorio `XmartAgro-analysis`, por si querés ver el detalle.

---

## 1. La idea en un minuto

**El problema.** En el secano, el productor decide qué sembrar sin saber cuánta agua tiene su suelo ni qué tan seguido le faltó en el pasado.

**Qué responde XmartAgro.** Para un campo, dice:
1. **Cuánta agua tiene el suelo hoy** (en milímetros de agua útil).
2. **En cuántos de los últimos 39 años** (zafras 1987 a 2025) cada opción de cultivo habría tenido agua suficiente, justa o ninguna. Se muestra como **10 gotas** por opción.
3. **Si cada opción mejora o empeora el suelo** (por el rastrojo, la cobertura, la soja seguida).

**Cómo lo hace.** No pronostica la lluvia. Toma el agua que hay hoy y le aplica el clima real de cada una de las 39 zafras pasadas. Eso da 39 historias posibles y se cuentan.

**Qué NO hace.** No predice rendimiento, no calcula ganancias, no dice "esto es lo mejor". Muestra el riesgo de cada opción para que decidan el productor y el agrónomo.

**Dónde entra el machine learning.** Tres modelos chicos aprenden de los datos de todos los campos para mejorar tres cosas: corregir al satélite (B), entender qué es una mala zafra para un productor (A) y reconocer qué se sembró mirando el verdor del campo (C). Ninguno genera texto ni calcula el agua: aprenden reglas que el cálculo consulta. Se explican en la sección 7.

---

## 2. El mapa general

```
  FUENTES                 INGESTA            ALMACENES                 ¿CUÁNDO CORRE?
  ───────                 ───────            ─────────                 ──────────────
  NASA (POWER, SMAP,  ─┐
        MODIS)         │
  Sensores del campo  ─┼─►  valida,      ─►  Series  (campo × día)  ─►  PIPELINE NOCTURNO
  Formularios de       │    marca la fuente    Ejemplos (A, B, C)        1 Preparar
   productor/agrónomo ─┘    y guarda                │                    2 Corregir satélite  (usa B)
                                                    │                    3 Balance de agua
                                                    ▼                    4 Escenarios        (usa A y C)
                                          ENTRENAMIENTO PERIÓDICO              │
                                          · B cada semana                      ▼
                                          · A y C cada zafra            Resultados precalculados
                                          · valida con campos apartados        │
                                          · publica solo si mejora             ▼
                                                    │                   API  ─►  PANTALLA
                                                    ▼                   (solo lee)  del productor
                                          Registro de modelos                       y del agrónomo
                                          (versiones)  ◄── el pipeline lee la
                                                           versión publicada
```

**Siete principios** que todo el sistema respeta:

1. **Nada se calcula cuando el usuario pide.** Todo se precalcula de noche; la API solo lee. En el campo hay poca señal y la respuesta tiene que ser inmediata.
2. **Pipeline y entrenamiento no se llaman entre sí.** Se comunican solo por los almacenes. Si uno falla, el otro sigue.
3. **Los modelos tienen versiones.** El pipeline usa la última publicada y cada resultado guarda con qué versiones se calculó.
4. **Funciona desde el primer campo.** Si un modelo no tiene datos suficientes, se usa una regla fija de partida. El modo base usa solo datos de NASA.
5. **Es repetible.** Correr dos veces el mismo campo y día da el mismo resultado.
6. **Es trazable.** Cada dato guarda su fuente. Lo simulado nunca se mezcla con lo real sin marcarlo.
7. **Privado por diseño.** Se aprende de todos los campos, pero ningún productor ve datos de otro; solo se comparten las reglas aprendidas.

---

## 3. Qué es real y qué es simulado

Esta tabla es la más importante para presentar el proyecto con honestidad.

| Cosa | ¿Real o simulado? | Dónde |
|---|---|---|
| Clima (lluvia y temperatura) de los 8 campos | **Real** (NASA POWER, un archivo por coordenada) | `src/xmart_analysis/data/sites/*/power_daily.csv` |
| Humedad de satélite SMAP y verdor MODIS | **Real** en Soriano y La Estanzuela; **simulada** en los otros seis | `src/xmart_analysis/data/sites/soriano/`, `src/xmart_analysis/data/sites/la_estanzuela/` |
| Encuesta de 12 productores | **Real** (rotaciones y zafras malas nombradas) | `src/xmart_analysis/data/survey/` |
| Sensores del campo | **Simulados** (todavía no hay sensores reales) | `src/xmart_analysis/data/learning/nodes.csv` |
| Unidad de suelo CONEAT de cada campo (grupo, índice de productividad, suelos dominantes) | **Real** (mapa oficial del MGAP, módulo opcional) | `src/xmart_analysis/data/learning/soil_units.csv`, `src/xmart_analysis/data/soils/coneat_groups.csv` |
| Textura y capacidad de agua del suelo de cada campo | **Simuladas, derivadas** de la unidad CONEAT con reglas declaradas | `src/xmart_analysis/soils/derive.py` |
| Pendiente de cada campo | **Simulada** | `src/xmart_analysis/data/learning/fields.csv` |
| Análisis de suelo y Plan de Uso (materia orgánica, fósforo, pH, erosión) | **Simulado** | `src/xmart_analysis/data/learning/soil_plans.csv` |
| Años en que cada productor sembró cada cultivo | **Simulado** (la encuesta da la rotación, no los años) | `src/xmart_analysis/learning/producers.py` |
| Cómo les fue en cada zafra (muy mal a excelente) | **Simulado** | `src/xmart_analysis/learning/outcomes.py` |
| Parámetros de cultivo (Kc, etapas, p) | Tabla de partida **pendiente de fuente**; las variantes por productor son simuladas dentro de rangos de FAO-56 | `src/xmart_analysis/data/crop_parameters.csv`, `src/xmart_analysis/data/learning/crop_ranges.csv` |
| Los tres modelos A, B y C | **Reales** como método, entrenados con datos simulados | `src/xmart_analysis/learning/` |

Cada fila simulada dice `simulated: True` y su fuente (`simulated_panel`). Regla: **los números de ML de este proyecto dicen que el método funciona, no cuánta precisión tendría con campos reales.**

---

## 4. Los datos de entrada

### 4.1 De la NASA
| Producto | Qué mide | Resolución | Desde | Para qué lo usamos |
|---|---|---|---|---|
| **NASA POWER** | Lluvia y temperatura diarias | ~50 km | 1986 | El balance de agua y las 39 zafras |
| **SMAP L4** | Humedad de la zona de raíces (hasta 1 m) | 9 km, cada 3 h | 2015 | Calibrar el suelo y entrenar el modelo B |
| **SMAP L3** | Humedad de la superficie | 9 km | 2015 | Validar que la dinámica del agua es correcta |
| **MODIS NDVI** | Verdor de la vegetación | 250 m, cada 16 días | 2000 | Modelo C y meses de suelo desnudo |
| **GPM IMERG** | Lluvia | ~10 km | 1998 | Control de la lluvia de POWER |

Los datos de NASA son gratuitos y se citan en la pantalla de fuentes. Los pedidos hechos en AppEEARS están en `src/xmart_analysis/data/requests/` (sin datos personales).

### 4.2 Del productor, del agrónomo y de los sensores
- **Productor:** qué sembró, cuándo y cómo le fue en sus últimas cinco zafras; las opciones que quiere comparar (mínimo tres, una es la actual).
- **Agrónomo:** análisis de suelo (materia orgánica, fósforo, pH) y erosión estimada del Plan de Uso.
- **Sensores:** una lectura cada 3 horas, enviada en un lote diario. Mínimo 30 cm de profundidad. Cada lectura necesita una **medición de referencia** (una muestra de suelo pesada, secada y vuelta a pesar) para saber cuánto se desvía esa sonda. Sin ella, la lectura se guarda pero no sirve para aprender.

### 4.3 El suelo como módulo que se conecta (CONEAT en Uruguay)
El suelo viene de un **módulo opcional**, pensado para que otro país conecte su propio sistema (en Uruguay, CONEAT del MGAP) sin tocar nada más:

```
  mapa de suelos      ──►  adaptador       ──►  "unidad de suelo"            ──►  tabla del campo
  (CONEAT: shapefile)      (ConeatMap)           código, índice de                 soil_units.csv
                                                  productividad, suelos dominantes
```
- **Puerto** (`src/xmart_analysis/soils/ports.py`): cualquier sistema tiene que contestar "¿en qué unidad cae este punto?" con la misma forma (`SoilUnit`). Sin sistema configurado (`NullSoilMap`) todo funciona como antes, con suelos medios.
- **CONEAT** (`src/xmart_analysis/soils/coneat.py`): lee el mapa oficial del MGAP (un shapefile de unos 120 MB que **no se guarda en el repositorio**) y devuelve el grupo del punto. Los datos de cada grupo salen de `src/xmart_analysis/data/soils/coneat_groups.csv` (128 grupos, leídos de la descripción oficial de grupos).
- **Otro país:** se escribe un adaptador que devuelva la misma `SoilUnit` y se agrega al registro `SYSTEMS` (`src/xmart_analysis/soils/__init__.py`). El resto del proyecto no se entera.
- **Cómo se usa:** el índice de productividad del grupo (100 es el promedio del país) fija cuánta agua guarda el suelo del campo simulado; los suelos dominantes fijan su textura (liviana, media o pesada); la textura fija el error plantado del satélite. Son reglas declaradas y provisionales (`src/xmart_analysis/data/soil_order_texture.csv` y las constantes `soil_*`), no un cálculo de agua disponible.
- **Qué NO hace:** CONEAT no entrega agua disponible en milímetros; da un índice y suelos dominantes. Por eso la capacidad es una **derivación nuestra**, y la pantalla no debe decir que es "el agua disponible de CONEAT".

Para refrescarlo: `xmart-analysis coneat-groups PDF` (tabla de grupos, necesita `pdftotext`) y `xmart-analysis soil-units --shapefile MAPA.shp` (la unidad de cada campo, necesita `pip install -e '.[coneat]'`).

Un hallazgo: el punto de Soriano cae en el grupo **11.4**, no en el 10.8b que mostraba el ejemplo del demo. El demo ahora usa 11.4.

### 4.4 Los ocho campos del panel
Dos reales (Soriano, La Estanzuela) y seis simulados (Salto, Paysandú, Río Negro, Flores, Durazno, Florida). Los seis simulados tienen **su propio clima real** de NASA POWER en su propia coordenada; lo demás de ellos (suelo, SMAP, sensores, zafras) es simulado. Su suelo sale de la unidad CONEAT de su coordenada (sección 4.3). Cada campo tiene **dos sensores** (a 30 y 60 cm) con su propio suelo, desvío y ruido, porque un mismo campo no es parejo.

---

## 5. Los cuatro almacenes

Los almacenes son el único punto de contacto entre las partes. Dos reglas valen para los de **series** y **ejemplos**: *solo se agregan filas, nunca se editan*, y *una fila que ya existe se saltea*. Por eso se puede cargar el mismo dato dos veces sin cambiar nada y recalcular cualquier período sin efectos secundarios. Está en `src/xmart_analysis/learning/stores.py`.

| Almacén | Qué guarda | Quién escribe | Quién lee |
|---|---|---|---|
| **Series** | `daily`: por campo y día, el clima de NASA y la humedad del satélite. `nodes`: por sensor y día, la lectura cruda y la calibrada | La ingesta | El pipeline nocturno |
| **Ejemplos** | Una colección por modelo (A, B, C): cada fila es un caso con su respuesta | La ingesta y el balance de agua | El entrenamiento |
| **Registro de modelos** | Cada versión entrenada: estado (candidata, publicada, retirada), cuántos datos usó, su métrica, el archivo | El entrenamiento | El pipeline |
| **Resultados** | Lo precalculado para cada campo y opción | El pipeline | La API y la pantalla |

Código: ingesta en `src/xmart_analysis/learning/ingest.py`, registro en `src/xmart_analysis/learning/registry.py`, resultados en `src/xmart_analysis/worker/adapters/files.py`.

Hoy son archivos (líneas JSON). Cambiar a una base de datos es escribir otro adaptador con los mismos métodos, sin tocar a quien usa el almacén.

---

## 6. El pipeline nocturno, paso a paso

**Estado de cada paso hoy** (la columna de la derecha dice qué falta para conectarlo):

| Paso | Estado | Qué falta |
|---|---|---|
| 1 · Preparar | Parcial: se lee de archivos CSV y del almacén de series | La ingesta diaria automática de NASA y sensores |
| 2 · Corregir el satélite | El modelo B está entrenado, validado y registrado | Que el paso lea el modelo publicado del registro |
| 3 · Balance de agua | **Hecho** (`src/xmart_analysis/engine/water_model.py`) | — |
| 4 · Escenarios | **Hecho**, con los cortes fijos de partida | Que consulte los modelos A y C publicados |
| Salud del suelo | **Hecho** (reglas) sobre el panel de productores | Conectarla al resultado de cada campo |

Corre cada noche, **por campo**, y los campos son independientes: uno con error no frena a los demás. Cada paso escribe su salida antes de que empiece el siguiente. Si un paso falla, el campo queda en estado `error` con un código (por ejemplo `climate_gap` si POWER tiene un hueco).

### Paso 1 · Preparar
Arma una serie diaria limpia por campo desde 1986: descarta valores de relleno (-999 en POWER), toma el promedio diario del SMAP (8 lecturas), promedia las lecturas del sensor del día y marca cada hueco.

### Paso 2 · Corregir el satélite (usa el modelo B)
Para cada día con SMAP, calcula "qué humedad real corresponde a lo que dice el satélite en un campo como este". Si el campo tiene sensor calibrado con suficiente superposición (unos 90 días), usa su corrección propia; si no, la de campos parecidos. **Sin modelo B publicado, el SMAP pasa sin corregir y se marca `correccion: ninguna`.**

*Cómo lo aplica el exportador del front* (`src/xmart_analysis/learning/apply.py`, `Adjustments.start_state`): la serie de SMAP corregida por B reemplaza a la serie del sensor simulado como lectura del balance de agua (entra al motor igual que las lecturas de un sensor). Desde el último día con satélite, el motor sigue solo hasta el último día del clima (hoy son 8 días), así que el agua de partida es la de hoy y no la de la última pasada del satélite. El JSON lo dice: `summary.water.source` es `smap_corrected` y `summary.water.correction` trae la versión de B y el último día con satélite.

### Paso 3 · Balance de agua
Trata la zona de raíces como un **depósito**, día por día (`src/xmart_analysis/engine/water_model.py`):

```
agua de hoy = agua de ayer + lluvia − consumo real − drenaje        (entre 0 y la capacidad del suelo)
```
- **Consumo de referencia (ET0):** fórmula de Hargreaves con temperatura mínima, máxima y latitud.
- **Consumo del cultivo:** ET0 × coeficiente del cultivo (Kc), que cambia con la etapa (inicial, desarrollo, media, final).
- **Estrés:** cuando el agua baja de la fracción de agotamiento (p) del cultivo, el consumo real se reduce en proporción. Con p ≈ 0,5, el cultivo empieza a sufrir cuando queda la mitad del agua útil.
- **Corrección con sensor:** si hay lectura ese día, el agua se acerca a la lectura con una ganancia fija (hoy 0,3).
- **Estrés de cada zafra:** `1 − (consumo real ÷ consumo sin límite)` durante la etapa crítica. Va de 0 (sin estrés) a 1.

Los parámetros del suelo (capacidad, punto de marchitez, drenaje) se ajustan por campo contra el SMAP corregido, con optimización evolutiva sobre 2015–2020 y validación en 2021–2026. Ese ajuste no corre cada noche, sino cuando hay un modelo B nuevo o una vez por semana.

### Paso 4 · Escenarios, suelo y textos (usa los modelos A y C)
Para cada opción del campo y cada zafra con clima completo (1987 a 2025):
1. Parte del agua de hoy.
2. Corre el balance con el clima de esa zafra, desde hoy hasta el fin de la etapa crítica, con la fecha de siembra de la opción.
3. Calcula el estrés en la etapa crítica.
4. **Clasifica con el modelo A:** probabilidad de que el productor diga "me fue mal". Alta → *sin agua*, media → *justa*, baja → *tuvo agua*. **Sin modelo A publicado**, usa cortes fijos de estrés (0,10 y 0,30, provisionales). Con A publicado, el "de cada 10" de la tarjeta es el de A, y `risk_basis` conserva al lado lo que dicen los cortes fijos, para comparar. (Por zafra, la clase individual de `scenarios` sigue siendo la de los cortes fijos: A da probabilidades, no una clase por zafra.)
5. Cuenta las tres clases sobre el total y las convierte a "de cada 10". El semáforo es provisional: bajo si 8 o más de 10 tuvieron agua; alto si 3 o más se quedaron sin agua.

Además calcula la **salud del suelo** (sección 8) y los **cinco puntos del desafío** (por qué se sugiere, evidencia, beneficios, vacíos, riesgos), que son plantillas que se llenan con tablas, no textos libres.

**Modo:** si cualquier entrada del campo es simulada, el resultado se marca `modo: demo` y la pantalla muestra "Modo demo · datos simulados".

---

## 7. El machine learning

Son **tres modelos independientes**. Los tres aprenden con ejemplos de **todos los campos** y se ajustan de a poco a cada uno.

### 7.1 La regla gradual (común a los tres)

```
valor del campo = (n × estimación del campo + k × estimación regional) / (n + k)
```
- `n` = cuántos ejemplos propios tiene el campo (días con sensor para B, zafras para A).
- `k` = cuántos ejemplos propios hacen falta para que campo y región pesen igual (hoy 30 días para B, 4 zafras para A).
- Un campo nuevo (`n = 0`) usa la estimación regional. Con muchos datos propios, pesa casi solo lo suyo.

Por eso un productor nuevo arranca con lo que aprendieron sus vecinos. Está en `src/xmart_analysis/learning/pooling.py`.

### 7.2 Modelo B · Cuánto se equivoca el satélite
- **Pregunta:** en un campo como este, ¿qué humedad real corresponde a lo que dice SMAP?
- **Entra:** el SMAP del día, la arcilla y la pendiente del campo, la época del año.
- **Respuesta que aprende:** la humedad del sensor calibrado.
- **Método:** regresión lineal entre campos, más el error medio propio del campo (con la regla gradual).
- **Para qué sirve:** corrige el SMAP de todo el historial desde 2015, también en campos sin sensor.

### 7.3 Modelo A · Qué es una mala zafra
- **Pregunta:** con este estrés, ¿qué tan probable es que el productor diga "me fue mal"?
- **Entra:** el estrés que calculó el balance y el cultivo.
- **Respuesta que aprende:** cómo calificó el productor la zafra (mal, normal, bien).
- **Método:** regresión logística ordinal, una curva por cultivo y una general.
- **Para qué sirve:** reemplaza los cortes fijos de estrés por unos aprendidos de los productores.

### 7.4 Modelo C · Historial de cultivos
- **Pregunta:** viendo la curva de verdor de una zafra, ¿qué se sembró y cuándo estuvo el suelo desnudo?
- **Entra:** cinco números de la curva de NDVI: cuándo empieza el verde, cuándo y cuánto llega a su pico, cuántos días dura verde y cuántos picos tiene.
- **Respuesta que aprende:** el cultivo (o barbecho) que confirmó el productor.
- **Método:** bosque aleatorio (*random forest*).
- **Para qué sirve:** proponerle el historial a un productor nuevo, que solo confirma o corrige.
- **Límite conocido:** el píxel de MODIS (250 m) mezcla campos.

### 7.5 Cómo se entrena, se valida y se publica
1. **Disparo:** B una vez por semana; A y C al cerrar una zafra o cuando entran muchos ejemplos nuevos.
2. **Lectura:** se toman los ejemplos del almacén (`src/xmart_analysis/learning/training.py`).
3. **Validación con campos apartados:** se separa al azar alrededor de un 25% de los campos **enteros**, se entrena con el resto y se mide en los apartados; se repite 20 veces y se promedia (`src/xmart_analysis/learning/validation.py`). Se apartan campos enteros porque la pregunta es si el modelo funciona con un productor nuevo.
4. **Comparación:** la candidata se compara con la **regla fija de partida** sobre esos mismos campos apartados.
5. **Publicación:** pasa a `publicada` solo si hay datos suficientes **y** le gana a la regla fija. Si no, queda `candidata` con el motivo y la versión publicada sigue sirviendo.
6. **Uso:** desde la noche siguiente, el pipeline usa la nueva versión. Para volver atrás alcanza con republicar una anterior.

Mínimos para publicar: B, unos 90 días de superposición con medición de referencia y al menos 3 campos; A, unas 20 zafras por cultivo; C, 60 zafras.

### 7.6 Qué dicen los números hoy
Medidos en campos apartados, sobre el panel simulado:

| Modelo | Con ML | Regla fija |
|---|---|---|
| B (error en m³/m³, menos es mejor) | 0,0251 sin sensor, 0,0237 con 90 días propios | 0,0300 (SMAP sin corregir) |
| A (acierto de clase) | 81,4% | 81,1% |
| C (acierto de cultivo) | 84,1% | 10,1% (clase más común) |

**Cómo leerlos:** como los resultados de cada zafra los generamos con nuestras propias reglas, los modelos recuperan esas reglas. Entonces:
- A casi no mejora (81,4% contra 81,1%) porque los cortes fijos ya están cerca de la regla simulada.
- C acierta fácil porque las curvas simuladas son limpias; en la realidad el píxel mezcla cultivos.
- B depende del tamaño del error de satélite que planteamos, que es un supuesto.

Con datos reales (sensores calibrados, calificaciones de productores, cultivos confirmados) se reemplazan las filas simuladas **y el código no cambia**. Recién ahí los números serían los verdaderos.

### 7.7 La retrospectiva: qué habría dicho la herramienta antes de cada zafra
Es la prueba del "¿y si el productor hubiera tenido XmartAgro?". Para un campo, un cultivo y una zafra pasada, la herramienta responde **el día de la siembra, como lo haría hoy**: toma el agua que el suelo tenía ese día y le aplica el clima de **las otras 38 zafras** (la zafra misma queda afuera, para que no conozca su propio futuro). Cuenta cuántas terminaron con agua, justa o sin agua y da el riesgo. Después se mira la zafra con su clima real. Está en `src/xmart_analysis/learning/retrospective.py` y en la sección 4 del informe.

Qué dice hoy (panel simulado, ocho campos, cuatro cultivos, todas las zafras):
- **Soja de primera sembrada en noviembre de 2022 (zafra 2022/23):** la herramienta habría dado riesgo **alto en 6 de los 8 campos** y medio en los otros 2 (entre 5 y 8 de cada 10 zafras sin agua). La zafra terminó sin agua en **los 8**, con un estrés de 0,77 a 0,99: peor que el 97% a 100% de las otras zafras.
- **Pero hay que decirlo con honestidad:** como los parámetros de cultivo todavía están pendientes, la soja y el maíz terminan sin agua en cerca del **64%** de las zafras. Entonces un aviso "alto" aporta poco: de los casos de soja con aviso alto, el 67% terminó sin agua, contra una base de 64%. El trigo y la cebada casi nunca terminan sin agua (9% y 6%) y, cuando pasó, la herramienta no había avisado.
- **Contra los datos reales de la encuesta:** las dos zafras que más productores nombraron como malas (2022/23 y 2025/26) son las dos con mayor estrés medio para soja y maíz en el panel.

**Cómo contarlo:** "con XmartAgro, antes de sembrar la soja en noviembre de 2022 habría salido un aviso de riesgo alto, y fue la peor zafra de la serie". Y a la vez: "la herramienta separa bien una zafra catastrófica de una normal; que no separe más depende de tener los parámetros de cada cultivo con fuente". No es una verificación contra un campo real, porque nadie midió esas zafras: compara el aviso con el mismo modelo.

---

## 8. La salud del suelo

Son **reglas**, no aprendizaje (`src/xmart_analysis/engine/soil_health.py`). Para un campo da un **estado** (bueno, regular, pobre), una **tendencia** (mejora, estable, empeora) y una **precisión** (baja sin análisis de suelo, media con uno).

Cada zafra suma o resta puntaje según:
- el **rastrojo** que deja su cultivo (maíz y sorgo dejan mucho, soja poco, barbecho nada);
- si hay **cobertura o pastura** (suma);
- los **meses con suelo desnudo** al año (resta cuando pasan de 4);
- **soja sobre soja**: cada zafra seguida de soja después de la primera resta, hasta un tope.

El análisis de suelo mueve el puntaje: erosión estimada sobre 7 t/ha/año o materia orgánica bajo 2,5% restan; materia orgánica desde 4% suma. La tabla de lo que hace cada cultivo al suelo está en `src/xmart_analysis/data/crop_soil_effects.csv`; los umbrales, en `src/xmart_analysis/data/model_constants.csv` (`soil_*`). **Todos son supuestos provisionales a fundamentar.**

También calcula el **efecto de cada opción**: mejora, se mantiene o empeora, sin necesitar análisis.

Límites: un cultivo por zafra (un cultivo de invierno y la soja que lo sigue cuentan como dos), y los meses desnudos salen del ciclo del cultivo hasta que se use la curva de NDVI de cada zafra.

---

## 9. Cómo lo emulamos en el front, y cómo sería de verdad

### 9.1 Lo que hacemos hoy: emulación con JSON estático
No hay API ni base corriendo en la demo. El front lee **un archivo JSON** que el análisis genera una vez:

```
xmart-analysis export --out schema --models models --now 2026-11-14T10:30:00+00:00
```
- Con `--models` (la carpeta del registro que deja `learn`), el JSON trae el bloque **`learning`** (ver más abajo); sin esa opción el bloque es `null` y el resto del análisis es idéntico.
- Usa el escenario de demo (`src/xmart_analysis/data/demo_scenario.json`): un campo con la serie de sensor simulada.
- Escribe `frontend.json`, su esquema y una descripción de campos. El ejemplo versionado es `schema/frontend.example.json` (el README explica cómo se actualiza).
- El JSON es de **versión 3.0**. Dice en qué **modo** está (`demo`, `live`, `pending`, `error` u `offline`) y trae un cartel visible "Modo demo · datos simulados". `pending` y `offline` los decide la pantalla: el primero para un campo nuevo que la corrida de la noche todavía no alcanzó, el segundo cuando no puede leer el archivo.
- Incluye los **datos granulares de los gráficos** (sección `charts`), para que el front dibuje lo mismo que el informe.

- Los gráficos incluyen también la **retrospectiva** (grupo `retrospective`): lo que habría dicho la herramienta antes de la zafra 2022/23 en cada campo.

**El bloque `learning`** (lo que aportan los tres modelos; código en `src/xmart_analysis/frontend/learning.py`):

| Parte | Qué trae | Modelo |
|---|---|---|
| `models` | Versión, fecha de entrenamiento, cuántos ejemplos y campos, y la métrica contra la regla fija que reemplaza | A, B y C |
| `options` | Para cada opción: de cada 10 zafras, cuántas espera el modelo que el productor llame buenas, normales o malas, **al lado** de lo que dicen los cortes fijos (son los mismos números que ya llevan las tarjetas, ver abajo) | A |
| `satellite` | Los últimos 90 días del campo del demo: el satélite tal cual, corregido y el sensor (simulado) | B |
| `crop_history` | Una propuesta por zafra con la curva real de MODIS del campo del demo: el cultivo, la confianza y `action` (`propose` si alcanza la confianza, `ask` si la pantalla debe preguntar) | C |

**El calendario: cualquier fecha del último año, cualquier cultivo** (bloque `calendar` y campo `as_of`; código en `src/xmart_analysis/engine/calendar_grid.py`). El front es un archivo estático, así que no puede calcular "qué pasa si abro la app el 20 de mayo y elijo cebada". Lo calcula el motor de antemano, para una fecha por semana (53 fechas, hacia atrás desde el último día del clima) y para los 9 cultivos que se pueden sembrar:
- **El agua de cada fecha** es el estado del campo ese día: la serie corregida (con B, si se aplican los modelos) corrida día a día, con los huecos llenados por el modelo.
- **Cada cultivo** se evalúa con la misma función que la pantalla principal (`platform_session.crop_card`), en su **próxima fecha de siembra**, con el clima de las 39 zafras y, con modelos, con el modelo A (`risk_basis` trae los cortes fijos al lado).
- **`offered`** es verdadero si la siembra queda a menos de `offer_days` (120) de la fecha. Las demás se muestran como guía aproximada con su aviso: el agua que tiene el campo hoy se va desdibujando con el tiempo. Por eso en diciembre-enero casi no hay cultivos "ofrecidos" (el trigo se siembra en junio, 5 meses después): la pantalla debería decirlo en vez de inventar.
- **`as_of`** (en la raíz) es el día al que corresponde todo ("Estado al 13 nov"), para que nadie lea una foto vieja como la de hoy.
- Es una **emulación**: las fechas son las del último año de la serie, como si la app se hubiera abierto ese día. En producción, cada noche el pipeline regeneraría el calendario con el estado nuevo.
- `schema/preview.html` es una página mínima (HTML y JS sin librerías) que lee solo `frontend.example.json` y deja elegir fecha y cultivo; sirve para ver cómo se consume el bloque (se abre con `python3 -m http.server` dentro de `schema/`).

**Los modelos se aplican, no solo se muestran.** Con `--models`, el resultado de la pantalla principal cambia respecto del análisis sin modelos:
- `summary.water`: el agua de partida sale del satélite corregido por B (`source: smap_corrected`, `correction`: versión de B y último día con satélite). Ya no se usa la serie del sensor simulado, y `status.simulated_inputs` pasa a `["training_panel"]`.
- `summary.options[]`: `drops` y `water_risk` son los de A, y `risk_basis` dice `source: model_a`, la versión y los cortes fijos al lado (`fixed_cuts_drops`, `fixed_cuts_water_risk`). Las opciones sin zafras que leer (por ejemplo, un ciclo ya terminado) quedan en `fixed_cuts`.
- Sin `--models` todo vuelve al cálculo de reglas fijas (`source: sensor`, `risk_basis.source: fixed_cuts`) y los modelos ni se importan (numpy no hace falta).

Lo que cambia es lo que aprendieron **todos los campos del panel**: B pondera lo regional con lo propio del campo (regla gradual de 7.1) y A usa las zafras de todos los campos. Tres avisos que el bloque lleva escritos: `simulated: true` (los modelos aprendieron de datos simulados), `satellite.in_sample` (el campo del demo es uno de los que B aprendió, así que no es una prueba) y `crop_history[].confirmed: false`. **El modelo C sobre la curva real suele dudar**: aprendió de curvas simuladas y el píxel real mezcla cultivos, así que muchas zafras salen con confianza baja y la pantalla tiene que preguntar en vez de proponer.

Todo lo precalculado ya está dentro del archivo, así que el front **no calcula nada**, igual que en producción.

### 9.2 Cómo funcionaría en producción (sin cambiar el código de cálculo)
Un día en la vida de un campo:

| Hora | Qué pasa | Qué almacén toca |
|---|---|---|
| Durante el día | El nodo sensor junta 8 lecturas; el productor carga una zafra en la app | — |
| Una vez por día | El nodo envía su lote. La **ingesta** valida (duplicados, fuera de rango, series planas), marca la fuente y guarda | Series (`nodes`), Ejemplos (B) |
| Una vez por día | La ingesta de NASA trae lluvia, temperatura, SMAP y NDVI nuevos | Series (`daily`) |
| Cuando el productor guarda un formulario | Se guarda su zafra, opciones y datos de suelo | Campo, historial; Ejemplos (A, C) |
| De noche, por campo | El **pipeline** corre los 4 pasos de la sección 6, leyendo del registro la versión **publicada** de cada modelo | Lee Series y Registro, escribe Resultados |
| Cada semana / fin de zafra | El **entrenamiento** corre y, si mejora, publica una versión nueva | Lee Ejemplos, escribe Registro |
| Cuando abre la app | La **API** lee los resultados ya calculados y los muestra | Lee Resultados |

El caso de uso del pipeline ya existe (`src/xmart_analysis/worker/application.py`): lee la última lectura del sensor y las respuestas guardadas, corre el análisis y guarda el resultado, saltando el trabajo si nada cambió. Usa **puertos** (`src/xmart_analysis/worker/ports.py`) con adaptadores de archivos, memoria y Mongo, así que cambiar de almacenamiento no toca la lógica.

**Lo que falta para conectar todo** (no se hace ahora, porque el front se emula): que el pipeline real lea el registro (el exportador del front ya lo hace con `--models`, y esa misma clase `Adjustments` es la que usaría), un planificador que dispare el pipeline y el entrenamiento, y la ingesta diaria de NASA y de sensores. Los modelos, el registro, los almacenes y las reglas de publicación ya están y están probados.

### 9.3 Qué ve cada usuario
- **Productor (celular):** el agua de hoy en mm, una tarjeta por opción (riesgo de agua con 10 gotas, y cómo queda el suelo) y, al tocarla, los cinco puntos del desafío.
- **Agrónomo:** lo anterior más los gráficos detrás de cada respuesta y la carga de datos técnicos del campo.

---

## 10. Cómo correr todo

Instalar: `pip install -e '.[plots,calibrate,learn,coneat]'`. Tests: `PYTHONPATH=src:tests python -m unittest discover -s tests`.

| Quiero... | Comando |
|---|---|
| Ver el análisis de la demo y dibujar las pantallas | `xmart-analysis run` |
| Generar el JSON para el front | `xmart-analysis export --out schema --now 2026-11-14T10:30:00+00:00` |
| Comparar el modelo con SMAP, MODIS, IMERG y la encuesta | `xmart-analysis validate --smap-l3 --smap-l4 --modis-ndvi --imerg` |
| Regenerar el informe con gráficos | `xmart-analysis report --smap-l3 --smap-l4 --modis-ndvi --imerg` |
| Recalibrar el suelo contra SMAP L4 | `xmart-analysis calibrate --out src/xmart_analysis/data/sites/soriano/calibration.json` |
| Cargar las series y los ejemplos a los almacenes | `xmart-analysis ingest --out models` |
| Entrenar A, B y C, validar y registrar | `xmart-analysis learn --out models` |
| Verificar que los datos coinciden con su registro | `python -m xmart_analysis.datasets check` |
| Rehacer la tabla de grupos CONEAT desde la descripción oficial | `xmart-analysis coneat-groups DESCRIPCION.pdf` |
| Buscar la unidad CONEAT de cada campo del panel | `xmart-analysis soil-units --shapefile MAPA.shp` |

---

## 11. Dónde está cada cosa

| Carpeta | Qué hay |
|---|---|
| `src/xmart_analysis/engine/` | El cálculo: balance de agua, cultivos, escenarios, salud del suelo. Sin entrada ni salida de archivos |
| `src/xmart_analysis/soils/` | El módulo de suelos conectable: el puerto, el adaptador de CONEAT y las reglas que derivan textura y capacidad |
| `src/xmart_analysis/learning/` | El panel simulado, los modelos A, B y C, los almacenes, la validación y el registro |
| `src/xmart_analysis/worker/` | El caso de uso del pipeline, sus puertos y adaptadores (Mongo, archivos, memoria) |
| `src/xmart_analysis/frontend/` | El contrato JSON para el front: armado, esquema y gráficos |
| `src/xmart_analysis/validation/` | Comparaciones con datos independientes de NASA y con la encuesta |
| `src/xmart_analysis/report/` | Figuras y el informe de experimentos |
| `src/xmart_analysis/data/` | Todos los datos y tablas, cada valor con su estado y fuente |
| `schema/` | El esquema JSON y los ejemplos que consume el front |
| `tests/` | Las pruebas (no necesitan base de datos) |
| `reports/` | El informe de experimentos (Markdown y PDF) |

**Cada valor numérico del modelo** (que no sea una fórmula) vive en una tabla con su **estado**: `source` (tiene fuente), `fitted` (ajustado a datos), `data` (dato), `assumption` (supuesto, con nota) o `pending` (espera un dato). Nada se presenta como medido si es `assumption` o `pending`.

---

## 12. Preguntas frecuentes

**¿Esto es IA generativa?** No. Son tres modelos de machine learning clásico (regresión y bosque aleatorio). Ninguno genera texto: los textos de la pantalla son plantillas.

**¿Por qué no entrenan con datos reales?** Hoy solo hay dos campos reales con datos de satélite, nueve zafras malas nombradas en la encuesta y ninguna lectura de sensor real. Es la razón de simular el resto, siempre marcado.

**¿Qué pasa cuando haya datos reales?** Se agregan filas a los almacenes con `simulated: False`; los modelos se reentrenan solos con la misma validación; si mejoran, se publican.

**¿Qué pasa si un campo no tiene sensor?** Funciona igual: usa el SMAP corregido con lo aprendido en campos parecidos. El sensor mejora la precisión, no es obligatorio.

**¿Por qué no se pronostica la lluvia?** Porque no sabemos qué va a llover. En cambio mostramos qué habría pasado con el clima real de cada una de las últimas 39 zafras.

**¿Usamos CONEAT?** Sí, como módulo opcional y conectable. Cada campo del panel tiene su grupo CONEAT real (el del punto de su coordenada) y de él derivamos la textura y la capacidad de agua con reglas declaradas. El mapa completo no está en el repositorio. En otro país se conecta otro sistema de suelos con el mismo formato.

**¿Qué falta?** Parámetros de cultivo con fuente (hoy están `pending`, y por eso la soja "falla" en muchas zafras), la ingesta diaria, el planificador y las zafras malas nacionales reales para comparar con las simuladas.

---

## 13. Glosario

- **Agua útil:** el agua del suelo que las raíces pueden usar.
- **Zafra:** una campaña agrícola (por ejemplo 2022/23).
- **Escenarios:** el agua de hoy con el clima real de cada una de las 39 zafras pasadas. No es un pronóstico.
- **ET0 / Kc / p:** consumo de referencia, coeficiente del cultivo y fracción de agotamiento del agua.
- **SMAP:** satélite de la NASA que mide humedad del suelo en cuadrados de 9 km.
- **NDVI:** índice de verdor (MODIS). Valores bajos son suelo desnudo o cultivo seco.
- **Campos apartados:** campos enteros que no se usan para entrenar y sirven para medir si el modelo funciona con un productor nuevo.
- **Modelo publicado / candidata:** la versión que usa el pipeline, y una versión entrenada que todavía no mejoró lo anterior.
- **Retrospectiva:** qué habría dicho la herramienta antes de una zafra pasada, sin conocer esa zafra, y cómo fue la zafra.
- **Almacén de solo agregar:** guarda filas que nunca se editan; si llega una repetida, se saltea.
- **Simulado:** dato generado por el modelo con una semilla fija; nunca es una medición.
