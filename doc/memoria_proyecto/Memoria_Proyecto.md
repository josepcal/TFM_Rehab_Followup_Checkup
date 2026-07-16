# Memoria del Proyecto — Plataforma de Seguimiento de Rehabilitación

> **En una frase:** una plataforma web donde pacientes registran sus ejercicios de rehabilitación y los profesionales médicos siguen su progreso a lo largo del tiempo, comparándolo con las pautas clínicas definidas para cada ejercicio.

Este documento está pensado para dos tipos de lector:

- **Lector no técnico** (clínico, gestor, tribunal): cada apartado empieza con una explicación en lenguaje llano.
- **Lector técnico** (desarrollador, arquitecto): tras la introducción llana, encontrará el detalle de arquitectura, componentes y decisiones.

Cuando veas el icono 🔧 empieza el detalle técnico de ese apartado.

---

## 1. Qué es la aplicación

Es una **plataforma de seguimiento de rehabilitación**. Su función es mostrar, de forma clara y a lo largo del tiempo, cómo evoluciona un paciente dentro de un programa de rehabilitación.

Imagine un cuaderno de ejercicios digital: el paciente anota (graba) cada ejercicio que realiza, y el profesional puede ver ese historial convertido en métricas y gráficas de progreso. En lugar de depender de la memoria o de notas sueltas, todo queda registrado y medido de forma consistente.

**Lo importante:** no es solo un repositorio de grabaciones — es una herramienta para **ver el progreso** frente a un objetivo clínico.

---

## 2. Qué problema resuelve

Hoy, el seguimiento de un programa de rehabilitación suele ser disperso: registros en papel, observaciones subjetivas y dificultad para comparar el estado del paciente entre una sesión y otra.

Esta plataforma resuelve dos problemas concretos:

| Problema | Cómo lo resuelve |
|----------|------------------|
| **Registros dispersos** | Ofrece un repositorio único con el historial de ejercicios de cada paciente. |
| **Progreso difícil de medir** | Convierte cada grabación en métricas objetivas y las compara contra las **pautas** (normas) definidas para ese ejercicio de rehabilitación. |

El resultado: el profesional puede responder con datos a la pregunta *"¿este paciente está mejorando según lo esperado?"*.

---

## 3. Arquitectura

**En lenguaje llano:** la aplicación está dividida en piezas independientes, cada una con una responsabilidad. Una se encarga de quién puede entrar y qué puede hacer, otra guarda las grabaciones, otra las analiza, y otra almacena los resultados para hacer reportes.

### 🔧 Componentes

| Componente | Responsabilidad |
|------------|-----------------|
| **Keycloak** | Autenticación y autorización (Auth/Auth). Gestiona identidades y permisos por rol (técnico, médico, paciente). |
| **UI + BFF** | Interfaz de usuario y su *Backend For Frontend*: el intermediario que adapta las peticiones de la UI hacia los servicios. |
| **S3 Storage** | Almacenamiento de las grabaciones de los ejercicios (objetos binarios). |
| **Worker** | Proceso asíncrono que calcula las métricas a partir de cada grabación. |
| **Base de datos** | Registro de resultados, métricas, normas, notas, reportes y seguimiento. |

### Diagrama de alto nivel

```
                 ┌─────────────┐
                 │  Keycloak   │  Auth/Auth (roles)
                 └──────┬──────┘
                        │
   ┌──────────┐    ┌────▼─────┐        ┌──────────────┐
   │    UI    │◄──►│   BFF    │◄──────►│ Base de datos│
   └──────────┘    └────┬─────┘        │ (resultados, │
                        │              │ normas,      │
              graba     │              │ reportes)    │
                        ▼              └──────▲───────┘
                 ┌─────────────┐              │
                 │  S3 Storage │              │ métricas
                 │ (grabación) │              │
                 └──────┬──────┘              │
                        │  lee grabación      │
                        ▼                     │
                 ┌─────────────┐              │
                 │   Worker    │──────────────┘
                 │ (métricas)  │
                 └─────────────┘
```

**Idea clave:** la grabación se guarda en S3, el Worker la procesa fuera de línea para no bloquear al usuario, y los resultados aterrizan en la base de datos, donde viven junto a las normas para poder comparar.

---

## 4. Cómo funciona (happy path)

Este es el recorrido ideal, de principio a fin, para un ejercicio de rehabilitación. Cada actor tiene su papel.

### Recorrido paso a paso

| # | Actor | Acción |
|---|-------|--------|
| 1 | **Técnico** | Registra en el código de la API las funciones que calculan las métricas del ejercicio y genera las **normas** de esas métricas en la base de datos. |
| 2 | **Médico** | Diagnostica al paciente y define su **programa de rehabilitación** asociado, con los ejercicios ya configurados en la base de datos. |
| 3 | **Paciente** | Otorga el **consentimiento** en su primera grabación y, a partir de ahí, registra sus ejercicios diariamente. Puede **subir y eliminar cuantas grabaciones quiera**, y es él quien **pide al Worker el análisis de métricas** de la grabación que elija. |
| 4 | **Médico** | Genera un **reporte por cada ejercicio** (semanal, mensual…). El reporte tiene granularidad **de ejercicio**. Tras generarlo, puede **escuchar las grabaciones** para añadir observaciones. |
| 5 | **Médico** | A partir de los reportes, elabora el **seguimiento a nivel de programa** — que agrupa los **1-N ejercicios** de ese programa de rehabilitación — en la ventana temporal que considere, con gráficas que visualizan el progreso de las métricas frente a las normas. |

### Flujo visual

```
Técnico          Médico              Paciente                Médico                  Médico
───────          ──────              ────────                ──────                  ──────
define      →    diagnostica    →    consiente + graba  →    genera reportes +  →    genera seguimiento
métricas +       + configura         + pide análisis         escucha grabaciones     (gráficas:
normas           programa            de métricas             (añade observaciones)   métrica vs norma)
```

> **📏 Granularidad — la diferencia entre reporte y seguimiento:**
> el **reporte** es **por ejercicio** (1 reporte : 1 ejercicio), mientras que el **seguimiento** es **por programa** y agrega los **1-N ejercicios** que lo componen (1 seguimiento : N ejercicios). Dicho simple: el reporte muestra un ejercicio a lo largo del tiempo; el seguimiento consolida los diferentes ejercicios del programa completo.

**Lo que hace valiosa la última etapa:** el seguimiento no muestra números sueltos, sino la métrica del paciente **contra la norma** del ejercicio, en la ventana de tiempo que el médico elija. Ahí es donde el progreso se vuelve visible.

**El dato objetivo y el juicio clínico conviven:** aunque el cálculo de métricas es un aspecto puramente objetivo, el médico puede añadir **observaciones y conclusiones en forma de texto**, tanto en los reportes como en los registros de seguimiento. Así la plataforma combina la medición automática con la interpretación profesional que un número, por sí solo, no puede aportar.

### 4.1. Condicionantes de GDPR implementados

**En lenguaje llano:** como la plataforma maneja grabaciones de voz —que son **datos de categoría especial (biométricos)**— el cumplimiento del [GDPR](https://gdpr-info.eu/) no es un extra, es un requisito. Estos son los condicionantes que se han implementado en el flujo anterior (cada uno enlaza al artículo correspondiente del reglamento):

| Condicionante GDPR | Qué exige | Cómo se ha implementado |
|--------------------|-----------|-------------------------|
| **Consentimiento explícito** ([Art. 9.2(a)](https://gdpr-info.eu/art-9-gdpr/)) | El interesado debe dar consentimiento **explícito** para tratar datos de categoría especial (biométricos). | El paciente otorga el **consentimiento en su primera grabación** (paso 3 del happy path); sin él no se registran ejercicios. |
| **Anonimización / seudonimización** ([Art. 4.5](https://gdpr-info.eu/art-4-gdpr/) · [Art. 32](https://gdpr-info.eu/art-32-gdpr/)) | Disociar los datos del paciente de su identidad directa y proteger su seguridad. | Dos mecanismos: (1) **seudonimización por mapa disociado** — una tabla `pseudonym_map` es el único punto que vincula paciente ↔ pseudónimo (UUID aleatorio), y las métricas se guardan solo contra el pseudónimo, sin enlace a la identidad; (2) **cifrado del `national_id`** con **Fernet** a nivel de aplicación, de modo que el identificador nacional nunca se almacena en claro. |
| **Control de acceso por rol** ([Art. 32](https://gdpr-info.eu/art-32-gdpr/)) | Minimizar el acceso: cada quien accede solo a lo que necesita. | **Keycloak** restringe el acceso según rol (técnico, médico, paciente, worker), aplicando el principio de mínimo privilegio. |
| **Restricción por usuario (RLS)** ([Art. 32](https://gdpr-info.eu/art-32-gdpr/)) | No basta con el rol: un usuario no debe ver los datos de otro con su mismo rol. | Doble capa: la **API** propaga la identidad del usuario a la sesión de Postgres, y **Row-Level Security en la propia BBDD** filtra las filas por usuario (políticas `_self`, p. ej. `patient_id = current_patient_id()`). La restricción se aplica **también a nivel de base de datos**, no solo en la API. |
| **Registro de auditoría** ([Art. 5.2](https://gdpr-info.eu/art-5-gdpr/)) | Poder demostrar quién accedió o modificó qué y cuándo, sobre datos sensibles (*accountability*). | **Monitorización de eventos** (FR-15 / UC-15): un `AuditMiddleware` registra automáticamente cada alta/modificación/borrado de entidad en la tabla `audit.event_log` —con actor, acción, entidad, diff y marca de tiempo—. El log es **accesible solo por el rol admin** (`GET /iam/audit-log`); ningún otro rol tiene acceso al esquema de auditoría. |
| **Cifrado de los datos en reposo** ([Art. 32.1(a)](https://gdpr-info.eu/art-32-gdpr/)) | Cifrar los datos personales almacenados, para que sean inaccesibles a quien no esté autorizado. | El volumen que contiene las grabaciones y las bases de datos está **cifrado con LUKS** (*Linux Unified Key Setup*) a nivel de bloque. El cifrado se realiza **dentro de la máquina virtual**, con una passphrase que solo existe cifrada y que se descifra en memoria durante el arranque: **el proveedor de cloud no posee la clave**. Ver apartado 5. |
| **Hosting solo en Europa** ([Art. 44–46](https://gdpr-info.eu/art-44-gdpr/)) | Los datos de categoría especial no deben transferirse fuera del ámbito de protección europeo (EEE). | El despliegue cloud se **restringe a proveedores y regiones europeas** (ver apartado 5). |

**Principio de fondo:** el cumplimiento se diseñó dentro del flujo, no como un parche posterior. El consentimiento condiciona la entrada de datos, el control de acceso condiciona quién los ve, el cifrado condiciona quién puede leerlos si se los lleva, y la localización condiciona dónde viven.

---

## 5. Despliegue

**En lenguaje llano:** la aplicación se puede levantar de dos formas — en el ordenador de un desarrollador para probarla, o en la nube para uso real.

| Entorno | Herramienta | Notas |
|---------|-------------|-------|
| **Local** | Docker | Levanta todos los componentes en contenedores para desarrollo y pruebas. |
| **Cloud** | Terraform | Infraestructura como código, desplegada en **Hetzner Cloud** (Núremberg). **Restringido a servidores en Europa por cumplimiento de GDPR.** |

### 🔧 Topología del despliegue cloud

El despliegue se organiza en **dos máquinas virtuales** con una separación deliberada: una VM **edge**, que es el único punto expuesto a Internet, y una VM **stack**, que contiene la aplicación y **todos los datos sensibles**. La clave del diseño es que **la VM stack no tiene dirección IP pública**: solo es alcanzable desde la edge, a través de una red privada.

```
                      Internet
                         │  HTTPS (443)
          ┌──────────────▼──────────────┐
          │  VM EDGE  ·  IP pública     │
          │  nginx (TLS) + UI estática  │
          │  10.0.1.10                  │
          └──────────────┬──────────────┘
                         │  red privada (10.0.1.0/24)
          ┌──────────────▼───────────────┐
          │  VM STACK  ·  SIN IP pública │
          │  10.0.1.20                   │
          │                              │
          │  BFF · Worker · Keycloak     │
          │  Postgres×2 · MinIO (S3)     │
          │                              │
          │  ▼ volumen cifrado (LUKS)    │
          └──────────────────────────────┘
```

**Idea clave:** no se trata de que los servicios estén "detrás de un proxy", sino de que **la máquina que custodia las grabaciones de voz no existe en Internet**. No tiene dirección pública que escanear ni contra la que dirigir un ataque. Aunque la VM edge fuera comprometida por completo, los datos residen en **otro servidor**, alcanzable únicamente por la red privada interna.

**Defensa en profundidad, no una única barrera.** Que la VM stack no tenga IP pública es una protección **topológica**: depende de que la red esté bien configurada. Si mañana se le adjuntara una IP por error, esa protección desaparecería sin más. Por eso hay una segunda capa **independiente**: el cortafuegos del stack solo acepta conexiones a los puertos del BFF (8000), Keycloak (8080) y MinIO (9000) **desde la IP privada del edge** (`10.0.1.10/32`). Ni siquiera otra máquina de la misma red privada podría hablar con la base de datos. Las **dos capas tienen que fallar a la vez** para que haya exposición.

**Los secretos nunca viven en claro.** Las **19 credenciales** del sistema —contraseñas de las dos bases de datos, credenciales de Keycloak y MinIO, la clave de API del LLM y la *passphrase* LUKS del volumen cifrado— están cifradas con **SOPS/age**. El fichero cifrado **sí se versiona** en el repositorio, porque lo que se versiona es el criptograma, no el valor; la clave privada `age` nunca entra en git y no sale de la máquina del operador. Al arrancar, los secretos se descifran a **tmpfs (memoria RAM)**, no a disco: si alguien robara el disco del servidor, no habría fichero de configuración que leer.

La infraestructura se divide en **tres capas de Terraform** con ciclos de vida independientes:

| Capa | Vida | Contiene |
|------|------|----------|
| **`persistent`** | Permanente (`prevent_destroy`) | IP flotante, **volumen de datos cifrado**, red privada. |
| **`edge`** | Siempre activa | VM nginx con TLS y pasarela NAT. |
| **`stack`** | Efímera | VM de aplicación y datos, sin IP pública. |

Separar las capas permite **destruir la aplicación sin perder los datos**: el volumen cifrado, la IP y el DNS sobreviven, y reconstruir el entorno es una sola orden de Terraform. Es una decisión de coste —la VM de aplicación solo se factura mientras está encendida— que además reduce la superficie de exposición cuando el sistema no se está usando.

Además, dentro de la VM stack existe una **segunda frontera**: las bases de datos y MinIO corren en una red Docker interna **sin salida a Internet**. Aunque uno de esos servicios fuera comprometido, no podría exfiltrar datos hacia el exterior por iniciativa propia.

> **⚖️ MVP vs. arquitectura objetivo:** la topología actual está **condicionada por el alcance MVP y los recursos disponibles**. Los servicios de aplicación y datos conviven en una única VM stack, autohospedados. La arquitectura objetivo, orientada a **resiliencia y escalabilidad**, evolucionaría así:
>
> - **Almacenamiento (S3)** → recurso gestionado del proveedor cloud (con residencia UE), consumido por BFF y Worker como servicio externo.
> - **Base de datos (Postgres)** → servicio gestionado con réplicas y copias de seguridad automáticas, para durabilidad y alta disponibilidad del dato.
> - **UI-BFF** → varias instancias tras un balanceador, para escalar horizontalmente ante la carga.
> - **Worker** → autoescalable según la cola de análisis pendientes (más grabaciones → más instancias de cálculo).
> - **Keycloak** → en alta disponibilidad o como *identity provider* gestionado; al ser el componente de Auth/Auth, su caída bloquearía todo el acceso.
>
> **El salto de fondo:** hoy tanto la VM edge como la stack son **puntos únicos de fallo** (*single point of failure*): si cae cualquiera de las dos, cae la plataforma. El aislamiento de red resuelve la **seguridad**, pero no la **disponibilidad**. La evolución no consiste solo en externalizar piezas, sino en pasar de dos nodos a **componentes distribuidos con redundancia y balanceo de carga**, de modo que el fallo de una parte no derribe el conjunto.

### 🔧 Sobre la restricción GDPR

Las grabaciones de voz son **datos de categoría especial** (biométricos). El despliegue en cloud se limita deliberadamente a proveedores y regiones europeas para cumplir el Reglamento General de Protección de Datos. Esto no es un detalle de configuración: es una **restricción de diseño** que condiciona dónde puede ejecutarse la plataforma.

La restricción se concreta en dos decisiones:

**1. El proveedor.** El despliegue final se realiza en **Hetzner Cloud** (región `nbg1`, Núremberg). La elección no fue por coste, sino por exposición jurídica: Hetzner es una empresa **alemana**, no sujeta a la *US CLOUD Act*. Los hiperescalares estadounidenses —AWS, Azure, GCP— sí lo están, y pueden verse obligados a entregar datos aunque estén alojados físicamente en Europa. Al no haber proveedor estadounidense en la cadena, no hay transferencia internacional que justificar bajo el marco posterior a **Schrems II**. La región está fijada en la propia infraestructura como código, no como convención: el volumen de datos está anclado a `nbg1` y la máquina de aplicación debe residir allí para poder montarlo.

**2. El cifrado en reposo, y por qué importa más de lo que parece.**

El volumen que contiene las grabaciones y las bases de datos está cifrado con **LUKS**. Conviene subrayar que **no es una función del proveedor**: Hetzner entrega un volumen de bloques crudo, y el cifrado se realiza dentro de la máquina virtual mediante `cryptsetup`. La passphrase solo existe cifrada (SOPS/age) y se descifra en memoria (*tmpfs*) durante el arranque, sin llegar nunca al disco. La consecuencia es directa: **el proveedor de cloud no puede leer las grabaciones de los pacientes**, ni aunque se le exigiera legalmente.

Esto satisface el [Art. 32.1(a)](https://gdpr-info.eu/art-32-gdpr/), que nombra el cifrado explícitamente entre las medidas técnicas apropiadas. Pero el beneficio práctico más relevante está en el [**Art. 34.3(a)**](https://gdpr-info.eu/art-34-gdpr/), a menudo pasado por alto:

> El artículo 34 obliga a **notificar a los interesados** cuando una violación de seguridad entrañe un riesgo alto para sus derechos. Su apartado 3(a) exime de esa notificación si el responsable había aplicado medidas que hagan los datos **ininteligibles** para cualquier persona no autorizada, *"como el cifrado"*.

Aplicado a esta plataforma: si un disco fuera sustraído físicamente, o si el proveedor reasignara el volumen sin borrarlo de forma segura, los bloques resultantes serían ruido criptográfico. **Existiría un incidente de seguridad, pero no la obligación de notificar a cada paciente que su voz ha sido expuesta.** Esa es la diferencia entre un incidente y una crisis reputacional, y es la razón por la que el cifrado en reposo no es un adorno técnico.

**Sus límites, que conviene explicitar.** LUKS protege el disco *en reposo*. Con la máquina encendida y el volumen montado, los datos son legibles para quien obtenga acceso privilegiado en ella; de ese escenario protege el aislamiento de red (la máquina de aplicación no tiene IP pública), no el cifrado. Tampoco cubre el [Art. 17](https://gdpr-info.eu/art-17-gdpr/) (derecho de supresión): borrar un dato es una operación de la aplicación, no del disco. El ciclo de vida completo de los datos —retención, exportación y borrado— queda fuera del alcance de este MVP y se recoge como deuda en el Anexo A.

Cada control responde, por tanto, a **una amenaza distinta**: el aislamiento de red frente al atacante remoto, el cifrado en reposo frente al acceso físico o al propio proveedor, la RLS frente al acceso indebido entre pacientes, y la seudonimización frente a la exposición de identidad ante terceros. No son redundantes: son capas complementarias.

---

## 6. Verificación de seguridad (OWASP Top 10)

**En lenguaje llano:** decir que un sistema es seguro no lo hace seguro. El sistema se auditó **dos veces** contra el estándar de la industria, buscando activamente cómo romperlo.

Los controles descritos en las secciones anteriores no se dan por buenos porque estén escritos: se sometieron a verificación. Se realizaron **dos auditorías de código** —la primera cubriendo OWASP Top 10, arquitectura hexagonal y RGPD; la segunda, OWASP Top 10 sobre web, API, Terraform y despliegue— con sus hallazgos, severidades y remediaciones registrados en `doc/audit/`.

### 🔧 Ejemplos de hallazgos y cómo se cerraron

| Hallazgo (OWASP) | Detectado | Cerrado |
|---|---|---|
| **A01 · Control de acceso** | **BOLA explotado contra el Postgres real:** un médico ajeno leyó (`200`) y modificó (`204`) informes y grabaciones de voz de pacientes de **otro** médico. La autorización por rol no bastaba: `medical` era `medical`. | Verificación de propiedad por objeto en el dominio, cableada en los 8 endpoints; responde `404` (no `403`) para no revelar la existencia del recurso ajeno. **224 líneas de test de aislamiento** contra base de datos real. |
| **A07 · Autenticación** | El `aud` del token **no se validaba**: cualquier token del *realm*, emitido para otro cliente, entraba a la API clínica. El algoritmo de firma se tomaba del propio token. | *Audience mapper* en Keycloak + `verify_aud`. RS256 fijo, nunca derivado del token. Re-verificado con un token real. |
| **A04 · Frontera de IA** | El aislamiento identidad↔métricas dependía de la **disciplina del programador**: cualquier consulta podía cruzarlo. | Rol `ftm_ai` con RLS: solo ve `v_ai_payload` (métricas seudonimizadas). **La base de datos lo impide, no el código.** |
| **A09 · Auditoría** | El registro de auditoría re-parseaba el JWT **sin validar la firma**: el propio rastro de trazabilidad era manipulable. Solo se registraban escrituras. | El `sub` validado es la única fuente. Auditoría de **lecturas** sensibles + registro de accesos **denegados** (detecta sondeo sistemático). |
| **A03 · Dependencias** | Sin escaneo de vulnerabilidades; dependencias sin fijar. | SCA en CI → **4 CVEs reales**: 2 cerrados al fijar versiones, 1 actualizado, 1 sin *fix* disponible documentado y aceptado. |
| **A05 · Configuración** | `/docs` y `/openapi.json` abiertos en producción. Consola de administración de Keycloak accesible desde internet. | Desactivados en producción. Consola retirada del proxy público; administración solo por red privada, **sin debilitar la CSP** de la SPA clínica. |

**Idea clave:** un control que **no se puede eludir aunque el código falle** —RLS, roles de base de datos— es más fuerte que uno que depende de recordar aplicarlo. La frontera de anonimización **pasó del papel al motor de base de datos**.

**Sobre el proceso, no solo el resultado.** El hallazgo A01 lo detectó la **segunda** auditoría: la primera lo había dado por cubierto, al leer que un módulo sí validaba el vínculo médico↔programa y generalizar indebidamente al resto. Es la observación más útil del ejercicio: la verificación también falla, y por eso se repite. Los hallazgos cerrados quedan cubiertos por tests de regresión —validados por sabotaje: al retirar el guard, el test se pone en rojo—.

---

## 7. Cómo se ha implementado

**En lenguaje llano:** el proyecto no se construyó improvisando. Se siguió una metodología dirigida por especificaciones y quedó documentado en cada capa.

### 🔧 Metodología y trazabilidad

El proyecto siguió **SDD (Spec-Driven Development)**: primero la especificación, después el código. La especificación no nació cerrada, sino que **evolucionó en dos fases**:

1. **Especificación inicial** — un documento madre (`doc/sdd/FTM_SDD_1_9.md`, v1.9) que definió el alcance y los casos de uso del sistema.
2. **Iteración por verticales** — sobre esa base, cada caso de uso (UC-1…UC-15) se desarrolló como un *vertical slice* usando **OpenSpec** y los **skills SDD de GentlemanProgramming**, generando sus propios artefactos de especificación, diseño y tareas.

| Aspecto | Enfoque | Dónde se documenta |
|---------|---------|--------------------|
| **Especificación inicial** | Documento madre SDD v1.9 (alcance + casos de uso) | `doc/sdd/FTM_SDD_1_9.md` |
| **Especificación iterada** | Verticales por caso de uso (specs · design · tasks, UC-1…15) vía OpenSpec + skills SDD | `openspec/` |
| **Decisiones de arquitectura** | ADR (Architecture Decision Records) derivados de la spec | `doc/architecture` |
| **Modelo de datos** | Diseño de base de datos | `doc/bbdd` |
| **Interfaz de usuario** | Construida con v0 | — |
| **Skills / asistencia IA** | Metodología GentlemanProgramming con modelos GPT y Claude | — |
| **Auditoría de código** | Dos auditorías cubriendo OWASP Top 10, arquitectura y RGPD (§6) | `doc/audit/` |

**Principio de fondo:** primero la especificación, después el código. La spec inicial fijó el rumbo; las iteraciones por vertical la refinaron caso a caso. Cada funcionalidad tiene así su rastro documental —de la spec madre al vertical concreto— lo que permite auditar por qué existe y cómo se decidió.

---

## 8. Extensiones del caso de uso

**En lenguaje llano:** aunque esta plataforma nació para rehabilitación, el mismo patrón sirve para cualquier ámbito donde haya que **analizar audio o vídeo y seguir un progreso en el tiempo**.

El caso de uso es transferible a plataformas con fines **pedagógicos o de estudio**, por ejemplo:

- Seguimiento del progreso de **lectura**.
- Seguimiento del progreso de **escritura**.
- Evaluación de **exposiciones orales**.
- Seguimiento de **interpretación musical**.

En todos ellos se repite el mismo esquema: **grabar → medir métricas → comparar con una norma → visualizar el progreso**. Cambia el dominio, no la arquitectura.

---

## Anexo A — Mejoras pendientes

**En lenguaje llano:** este anexo recoge mejoras **diseñadas o previstas pero no implementadas** en la versión actual. Se separan a propósito del resto del documento para no confundir lo entregado con lo que queda como evolución.

| Mejora | Qué aporta | Estado actual |
|--------|-----------|---------------|
| **Interacción con LLM (asistencia por IA)** | Incorporar un modelo de lenguaje que asista en tres puntos del flujo: **(1)** sugerir mejoras en el análisis —hoy los tips que se muestran son **preconfigurados a partir del resultado de la métrica**, no generados por IA—; **(2)** ayudar a redactar recomendaciones y el *summary* del informe de seguimiento a partir de los reportes de los ejercicios; **(3)** proponer nuevos ejercicios según el progreso del paciente. | **Diseñada y armada; falta conectar el servicio.** La frontera de seudonimización **no está solo diseñada: está en vigor y verificada** —el rol `ftm_ai` solo tiene acceso a la vista `v_ai_payload` (pseudónimo + métricas) y la base de datos le impide leer el mapa de identidades aunque el código lo intentase, con tests de integración que lo demuestran (§6, A04)—. La tabla `ai_insight` está lista para persistir la salida. Lo único pendiente es **el servicio que llama al LLM**. |
| **Cifrado Fernet respaldado por KMS** | En producción, la clave de cifrado del `national_id` no debería vivir en una variable de entorno, sino gestionarse mediante un KMS (Key Management Service). | **Pendiente.** El cifrado Fernet está implementado con clave por variable de entorno; el propio código anota que en producción debe sustituirse por una clave gestionada por KMS. |
| **S3 como recurso externo gestionado** | Delegar el almacenamiento de grabaciones en un servicio de objetos gestionado del proveedor cloud, en lugar de autohospedarlo detrás del reverse proxy. | **Pendiente (condicionado por MVP).** La topología actual autohospeda S3 por alcance y recursos (ver apartado 5); la arquitectura objetivo lo externaliza. |
| **Derecho al olvido** (Art. 17 GDPR) | Permitir la supresión efectiva de los datos personales del paciente a petición, en dos niveles: purgar el media crudo (el biométrico) de la grabación, y romper el vínculo identidad↔pseudónimo para dejar las métricas de facto anónimas. | **Diseñado, no implementado.** El esquema ya contempla el borrado lógico de la grabación (`is_deleted`, purga del media — UC-13) y el borrado del mapa de pseudónimos, pero **el flujo de supresión no está implementado** en la versión actual. |

**Principio de fondo:** cada mejora de este anexo tiene una **base ya sentada** en el diseño actual — no son ideas sueltas, sino la evolución natural de decisiones ya tomadas. Distinguir lo implementado de lo pendiente es parte de la honestidad de ingeniería del proyecto.

---
