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
| **Hosting solo en Europa** ([Art. 44–46](https://gdpr-info.eu/art-44-gdpr/)) | Los datos de categoría especial no deben transferirse fuera del ámbito de protección europeo (EEE). | El despliegue cloud se **restringe a proveedores y regiones europeas** (ver apartado 5). |

**Principio de fondo:** el cumplimiento se diseñó dentro del flujo, no como un parche posterior. El consentimiento condiciona la entrada de datos, el control de acceso condiciona quién los ve, y la localización condiciona dónde viven.

---

## 5. Despliegue

**En lenguaje llano:** la aplicación se puede levantar de dos formas — en el ordenador de un desarrollador para probarla, o en la nube para uso real.

| Entorno | Herramienta | Notas |
|---------|-------------|-------|
| **Local** | Docker | Levanta todos los componentes en contenedores para desarrollo y pruebas. |
| **Cloud** | Terraform | Infraestructura como código. **Restringido a servidores en Europa por cumplimiento de GDPR.** |

### 🔧 Topología del despliegue cloud

En cloud, un **reverse proxy nginx** actúa como único punto de entrada: sirve la **UI** y enruta el tráfico hacia los servicios de detrás — **BFF**, **Keycloak**, **Postgres**, **S3** y **Worker**.

```
                Internet
                   │
        ┌──────────▼──────────┐
        │  nginx (reverse     │
        │  proxy) + UI        │
        └──────────┬──────────┘
                   │  enruta hacia
   ┌───────┬───────┼──────────┬─────────┐
   ▼       ▼       ▼          ▼         ▼
 BFF   Keycloak  Postgres    S3      Worker
```

**Idea clave:** el nginx concentra la exposición pública (UI + enrutado). El resto de servicios queda detrás del proxy, reduciendo la superficie expuesta a Internet.

> **⚖️ MVP vs. arquitectura objetivo:** esta topología está **condicionada por el alcance MVP y los recursos disponibles**: todos los servicios se autohospedan detrás de un mismo proxy, en un único nodo. La arquitectura objetivo, orientada a **resiliencia y escalabilidad**, evolucionaría así:
>
> - **Almacenamiento (S3)** → recurso externo gestionado del proveedor cloud, consumido por BFF y Worker como servicio externo (deja de estar "detrás del nginx").
> - **Base de datos (Postgres)** → servicio gestionado con réplicas y copias de seguridad automáticas, para durabilidad y alta disponibilidad del dato.
> - **UI-BFF** → desplegado en cloud con varias instancias tras un balanceador, para escalar horizontalmente ante la carga.
> - **Worker** → autoescalable según la cola de análisis pendientes (más grabaciones → más instancias de cálculo).
> - **Keycloak** → en alta disponibilidad o como *identity provider* gestionado; al ser el componente de Auth/Auth, su caída bloquearía todo el acceso.
>
> **El salto de fondo:** hoy el nginx es un **único punto de entrada y de fallo** (*single point of failure*): si cae el nodo, cae la plataforma entera. La evolución no consiste solo en externalizar piezas, sino en pasar de **un nodo** a **componentes distribuidos con redundancia y balanceo de carga**, de modo que el fallo de una parte no derribe el conjunto.

### 🔧 Sobre la restricción GDPR

Las grabaciones de voz son **datos de categoría especial** (biométricos). El despliegue en cloud se limita deliberadamente a proveedores y regiones europeas para cumplir el Reglamento General de Protección de Datos. Esto no es un detalle de configuración: es una **restricción de diseño** que condiciona dónde puede ejecutarse la plataforma.

---

## 6. Cómo se ha implementado

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

**Principio de fondo:** primero la especificación, después el código. La spec inicial fijó el rumbo; las iteraciones por vertical la refinaron caso a caso. Cada funcionalidad tiene así su rastro documental —de la spec madre al vertical concreto— lo que permite auditar por qué existe y cómo se decidió.

---

## 7. Extensiones del caso de uso

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
| **Interacción con LLM (asistencia por IA)** | Incorporar un modelo de lenguaje que asista en tres puntos del flujo: **(1)** sugerir mejoras en el análisis —hoy los tips que se muestran son **preconfigurados a partir del resultado de la métrica**, no generados por IA—; **(2)** ayudar a redactar recomendaciones y el *summary* del informe de seguimiento a partir de los reportes de los ejercicios; **(3)** proponer nuevos ejercicios según el progreso del paciente. | **Diseñada, no conectada.** La base de datos ya tiene la tabla `ai_insight` para persistir la salida de la IA y la **frontera de seudonimización** que la habilitaría de forma segura —vista `v_ai_payload` (solo pseudónimo + métricas) y un rol de IA sin acceso al mapa de identidades—, pero **el servicio que llama al LLM no está implementado**. |
| **Cifrado Fernet respaldado por KMS** | En producción, la clave de cifrado del `national_id` no debería vivir en una variable de entorno, sino gestionarse mediante un KMS (Key Management Service). | **Pendiente.** El cifrado Fernet está implementado con clave por variable de entorno; el propio código anota que en producción debe sustituirse por una clave gestionada por KMS. |
| **S3 como recurso externo gestionado** | Delegar el almacenamiento de grabaciones en un servicio de objetos gestionado del proveedor cloud, en lugar de autohospedarlo detrás del reverse proxy. | **Pendiente (condicionado por MVP).** La topología actual autohospeda S3 por alcance y recursos (ver apartado 5); la arquitectura objetivo lo externaliza. |
| **Derecho al olvido** (Art. 17 GDPR) | Permitir la supresión efectiva de los datos personales del paciente a petición, en dos niveles: purgar el media crudo (el biométrico) de la grabación, y romper el vínculo identidad↔pseudónimo para dejar las métricas de facto anónimas. | **Diseñado, no implementado.** El esquema ya contempla el borrado lógico de la grabación (`is_deleted`, purga del media — UC-13) y el borrado del mapa de pseudónimos, pero **el flujo de supresión no está implementado** en la versión actual. |

**Principio de fondo:** cada mejora de este anexo tiene una **base ya sentada** en el diseño actual — no son ideas sueltas, sino la evolución natural de decisiones ya tomadas. Distinguir lo implementado de lo pendiente es parte de la honestidad de ingeniería del proyecto.

---
