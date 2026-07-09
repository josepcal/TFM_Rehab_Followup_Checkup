Actúa como auditor de seguridad y arquitectura senior. Vas a auditar ESTE repositorio
(checkout local de master) de FTM: monolito modular FastAPI + worker async, auth Keycloak
(OIDC/PKCE), Postgres con RLS, frontera de anonimización ante un LLM, y voz = dato biométrico
(RGPD art. 9). La guía completa está en AUDIT_FTM.md: síguela punto por punto.

REGLAS DE MÉTODO (obligatorias):
- No asumas que la memoria/el plan describe lo implementado. Localiza el código real y trázalo
  entre ficheros antes de afirmar nada. Si algo de la guía no existe en el código, márcalo como
  "GAP de implementación vs. memoria".
- Usa herramientas, no memoria: rg/grep para imports cruzados y patrones, lee las migraciones
  Alembic y las políticas RLS, corre pip-audit/npm audit (SCA) y bandit/semgrep/ruff si están.
- Cita evidencia siempre: fichero:línea. Nada de hallazgos genéricos sin ubicación.

EJECUCIÓN EN 3 PASADAS SEPARADAS (no las mezcles):
  Pasada 1 → sección A: arquitectura limpia/hexagonal (pureza de dominio, puertos/adaptadores,
             dirección de dependencias, fronteras entre módulos).
  Pasada 2 → sección B: OWASP Top 10:2025, mapeado a la superficie real (prioriza A01, A04, A06, A10).
  Pasada 3 → sección C: RGPD (conformidad código ↔ memoria).

INVARIANTES CRÍTICOS que debes verificar explícitamente a nivel de código/BD, no por convención:
  1. La frontera de anonimización: el rol/conexión del módulo `ai` NO puede alcanzar el schema
     `clinical` ni `pseudonym_map` (compruébalo en las políticas RLS y en la config de conexión,
     no solo en el código Python).
  2. La región de procesamiento del LLM: verifica que la llamada saliente al proveedor no sale
     de la UE (endpoint/config).
  3. Doble capa de autorización: RLS Y dependencia RBAC presentes en cada endpoint sensible, no una sola.
  4. Resolución de function_name: lookup en whitelist contra el registry, nunca eval/getattr/import dinámico.

FORMATO DE SALIDA por hallazgo:
  [Severidad: Crítico/Alto/Medio/Bajo/Info] · Eje · Categoría · fichero:línea ·
  Qué está mal · Por qué importa EN ESTE DOMINIO (salud/biométrico/legal) · Remediación concreta.

Al final de cada pasada, entrega una tabla resumen ordenada por severidad. Tras las 3 pasadas,
da un TOP 10 priorizado de acción inmediata y señala qué hallazgos tienen impacto legal (RGPD)
además de técnico. No propongas remediaciones que rompan la separación de datos clínicos/identidad.