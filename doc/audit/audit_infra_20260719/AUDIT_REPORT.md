# Auditoría de infraestructura y observabilidad del despliegue — FTM

## Anclaje de la auditoría

| Campo | Valor |
|---|---|
| **Commit auditado (short)** | `4836d7c` |
| **Commit auditado (full)** | `4836d7c34d6cfcaaad033f3f621cd9440ad5c87c` |
| **Branch** | `feature/auditoria` |
| **Fecha del commit** | 2026-07-18 13:28:20 +0200 |
| **Asunto del commit** | Añadir cambios en presentacion y actualizacion de bbdd en Runbook |
| **Fecha de la auditoría** | 2026-07-19 |
| **Entorno auditado** | Producción — `ftm-followup-checkup.duckdns.org` (Hetzner nbg1) |

> A diferencia de las auditorías `audit_67cfeb8` y `audit_85780d7`, que revisaron el
> **código**, esta auditoría revisa el **despliegue en ejecución**: la superficie
> expuesta, el estado de las tres capas y la capacidad de observarlas. Los hallazgos no
> se derivan de leer ficheros sino de sondear el sistema vivo.

---

### Nota de método

Toda la evidencia se recogió desde la máquina del operador contra el despliegue real, a
través del edge como *jump host*. No se instaló ningún agente ni servicio de
monitorización en las VMs: el objetivo era comprobar qué se puede observar **sin ampliar
la superficie de ataque**.

El instrumento resultante es `deploy/ftm-status.sh`, incluido en este mismo commit. Es a
la vez la herramienta de diagnóstico y el entregable de la auditoría.

---

## Por qué la consola de Hetzner no es suficiente

Punto de partida de la auditoría: ¿cuánto del estado del sistema es visible desde el
panel del proveedor? La respuesta condiciona todo lo demás.

| Métrica | ¿Visible en Hetzner UI? |
|---|---|
| CPU y tráfico de red por VM | Sí — gráficas nativas |
| Tamaño provisionado del volumen | Sí — pero solo el tamaño, no el uso |
| **Uso real dentro del volumen** | **No** — está cifrado con LUKS |
| Memoria disponible | Solo con el agente de Hetzner instalado |
| Tiempo de respuesta del health por DNS | No |
| Logs de nginx | No |
| Último login / intentos fallidos | No |
| Contenedores Docker y su salud | No |

Cuatro de doce, y con matices. **Esta opacidad no es una carencia: es una consecuencia
directa del diseño.** El stack no tiene IP pública y el volumen está cifrado con una
clave que Hetzner no posee. El proveedor no puede ver dentro de una máquina a la que no
llega ni de un disco que no puede descifrar — que es exactamente la garantía que el
proyecto defiende ante el RGPD.

La conclusión operativa es que la observabilidad **tiene que pasar por el edge**, por SSH,
y eso es lo que implementa `ftm-status.sh`.

---

## Hallazgos

### H-1 · CRÍTICO — SSH del edge abierto a Internet (`0.0.0.0/0`)

**Evidencia.** El sondeo del journal de `sshd` en el edge devolvió:

```
152.017 intentos de login fallidos / usuario inválido en los últimos 5 días
```

Aproximadamente **30.000 intentos diarios** de fuerza bruta sostenida. La regla del
firewall confirmó la causa:

```hcl
rule {
  direction  = "in"
  port       = "22"
  source_ips = ["0.0.0.0/0"]
}
```

**Impacto.** No hubo compromiso: `sshd` solo acepta clave pública y todos los accesos
aceptados corresponden a la IP del operador. Pero el puerto 22 abierto al mundo es
superficie de ataque innecesaria, consume recursos del edge y llena el journal.

**Corrección aplicada** (2026-07-19). El firewall se reaplicó restringiendo SSH a la IP
del operador, dejando 80/443 abiertos porque la aplicación es pública:

```bash
terraform -chdir=terraform/hetzner/edge apply \
  -var='operator_ssh_cidrs=["<ip-operador>/32"]' ...
```

Resultado del plan: `port = "22"`, `source_ips = ["<ip-operador>/32"]`. Los bots dejan de
alcanzar al `sshd`: los corta el firewall de Hetzner en el borde.

> **Nota sobre recuperación.** Restringir SSH no supone riesgo de bloqueo permanente: el
> firewall se gestiona por la **API de Hetzner**, no por SSH. Si la IP del operador cambia
> (es dinámica por DHCP), basta reaplicar Terraform con el nuevo CIDR. El plano de gestión
> y el plano de acceso son independientes — una ventaja directa de tener el firewall en IaC.

---

### H-2 · ALTO — Las migraciones de base de datos no se aplican en el despliegue

**Evidencia.** El filtro `read` del panel de auditoría devolvía 500. En los logs del `bff`:

```
sqlalchemy.exc.DataError: (psycopg2.errors.InvalidTextRepresentation)
invalid input value for enum audit.action: "read"
```

`alembic current` en producción devolvió `0016_audit_outcome`, mientras el código
desplegado ya requería `0017_audit_action_read`.

**Causa raíz.** El `cloud-init` del stack clona el repositorio, descifra los secretos y
ejecuta `docker compose up`. **No ejecuta migraciones.** Como el volumen de datos es
persistente y sobrevive a cada ciclo `destroy`/`apply`, su esquema se queda atrás respecto
al código desplegado. El `RUNBOOK` documentaba el despliegue del frontend (§2c) pero no
tenía paso equivalente para el esquema.

**Impacto real, más grave que el síntoma.** El middleware de auditoría escribe
`action='read'` para todo GET marcado con `Depends(audit_read)`. Con el enum sin ese valor,
**cada lectura auditada de datos clínicos fallaba al insertarse**. El rastro de auditoría
de lecturas —control frente a *clinical snooping*, OWASP A09— **estaba vacío en producción**
hasta que se aplicó la migración.

**Corrección aplicada** (2026-07-19).

1. Migración aplicada: `0016_audit_outcome -> 0017_audit_action_read`.
2. Añadida la sección **§3a "Aplicar las migraciones pendientes"** a `deploy/RUNBOOK.md` y
   `deploy/RUNBOOK_ES.md`, con los comandos verificados, la instantánea previa del volumen
   y el síntoma que delata el paso olvidado.

Detalle operativo no evidente: el contenedor `bff` se conecta como `ftm_app`, que **no
puede ni leer** `alembic_version`. Hay que sobrescribir `DATABASE_URL` con el rol
administrador.

**Riesgo residual.** Sigue siendo un paso manual. La corrección de fondo —ejecutar
`alembic upgrade head` desde `cloud-init` antes de arrancar el `bff`— queda pendiente.

---

### H-3 · INFORMATIVO — Escaneo automatizado de vulnerabilidades sobre la superficie pública

**Evidencia.** En `/var/log/nginx/error.log` del edge:

```
2026/07/19 05:48:57 [error] upstream timed out ... client: 31.132.90.3,
request: "GET /api/vendor/phpunit/phpunit/src/Util/PHP/eval-stdin.php HTTP/1.1"
```

Sondeo de **CVE-2017-9841** (ejecución remota de código en PHPUnit). El sistema no tiene
PHP, por lo que no hay exposición. Se documenta como evidencia de que la superficie
pública recibe tráfico hostil continuo y la arquitectura lo absorbe sin degradarse.

---

## Sospechas descartadas (verificadas y retiradas)

Se investigaron y se descartaron con medidas, no con suposiciones:

**Degradación de rendimiento de la aplicación.** Una primera medición dio 4,1 s de TTFB en
`/programs/`. Repetida seis veces sobre dos endpoints, el resultado fue estable en
**0,13–0,18 s**. Los 4,1 s correspondían al arranque en frío (primera conexión TCP+TLS y
apertura del *pool* a Postgres). No hay problema de rendimiento.

**Saturación de recursos de la VM del stack.** Hipótesis inicial: 8 GB insuficientes para
dos Postgres, Keycloak, MinIO, API y worker. Medición real: **1,7 GiB usados de 7,6 GiB,
sin swap, load average 0,00–0,09**. Sobra margen.

**Incidencia del proveedor.** El edge presentaba latencia de ~17 s en SSH con
`load average: 0.00` y 13 días de *uptime*. Máquina ociosa, luego no era carga. El 100 % de
pérdida en `ping` **no es un síntoma**: Hetzner filtra ICMP por defecto. La latencia de SSH
queda sin explicación concluyente (probablemente resolución de nombres en algún salto
intermedio), pero **no afecta a la aplicación**, solo al terminal del operador.

**Coste de la auditoría de lecturas.** Se sospechó que activar la escritura de eventos
`read` penalizaría el rendimiento. Comparados `/api/patients` (auditado, sin *join* nuevo) y
`/programs/` (auditado y con *join* añadido de paciente y dolencia), la diferencia fue de
~20 ms — ruido de medición.

---

## Estado del despliegue tras la auditoría

Salida de `deploy/ftm-status.sh` (2026-07-19):

| Capa | Comprobación | Estado |
|---|---|---|
| Público | API health / Keycloak realm / Frontend | 200 en ~0,13 s |
| Público | Registro DNS A → IP flotante | Correcto |
| Edge | Memoria / disco | 484 MiB de 3,7 GiB · 4 % de disco |
| Edge | nginx activo · certificado TLS | Activo · válido hasta 2026-10-03 |
| Stack | Memoria / disco raíz | 1,7 GiB de 7,6 GiB · 4 % |
| Stack | Volumen LUKS montado | Sí — 138 MiB de 20 GiB (1 %) |
| Stack | Contenedores | 6 arriba; los 3 con *healthcheck*, `healthy` |
| Stack | Sondas bff / keycloak / minio | 200 |
| Stack | Conexiones Postgres | app 12/100 · keycloak 8/100 |

---

## Instrumento resultante — `deploy/ftm-status.sh`

Script único, sin dependencias ni servicios añadidos, que recoge el estado de las tres
capas desde la máquina del operador. Decisiones de diseño relevantes:

- **Todo pasa por el edge.** El stack no es alcanzable de otro modo. La observabilidad
  respeta la topología en lugar de perforarla.
- **`known_hosts` desactivado solo para el stack.** Su clave de host cambia en cada ciclo
  de demo. El edge **sí** verifica la clave: es la única máquina expuesta y ahí la
  protección frente a *man-in-the-middle* importa.
- **Sondas de servicio además del estado de Docker.** `postgres-app`, `postgres-keycloak` y
  `minio` declaran `healthcheck` en el compose; `keycloak`, `bff` y `worker` no. Para esos
  tres se consulta su endpoint en lugar de confiar en la columna de estado de Docker.
- **Umbrales, no solo cifras.** El volumen de datos avisa al superar el 80 %; las
  conexiones de Postgres, al superar el 80 % de `max_connections`. Un número que nadie lee
  no es monitorización.
- **Credenciales nunca en tránsito.** Las consultas a Postgres expanden
  `$POSTGRES_USER`/`$POSTGRES_DB` **dentro** del contenedor; el script no las conoce.

### Decisión explícita: no instalar Prometheus/Grafana

Se descartó una pila de monitorización al uso. Razones: añade al menos un servicio más a
una VM que ya ejecuta seis, amplía la superficie de ataque de un sistema cuyo argumento
central es el aislamiento, y exige almacenamiento de series temporales que ningún hallazgo
de esta auditoría habría necesitado. Para un despliegue efímero de demostración, un script
de diagnóstico bajo demanda cubre el caso de uso completo.

---

## Veredicto

El despliegue está **sano y correctamente dimensionado**. Los tres hallazgos con impacto
—SSH abierto al mundo, migraciones sin aplicar e imagen de la API sin fijar— **están
corregidos** en producción y en la documentación operativa.

El patrón común a los tres es revelador: ninguno era un fallo de código. Los tres eran
**huecos en el procedimiento de despliegue** — algo que el IaC no cubría (el CIDR por
defecto, la variable de imagen) o que directamente no existía (el paso de migración). El
código llevaba semanas correcto; lo que fallaba era el camino desde el repositorio hasta la
máquina.

### H-4 · MEDIO — La imagen de la API no estaba fijada a una versión

**Evidencia.** `postgres`, `keycloak` y `minio` están fijadas por digest en
`docker-compose.stack.yaml`. La API no: se resolvía como
`${API_IMAGE:-...api:latest}`, sin que nada alimentara esa variable. El bloque
`image versions` de `ftm-status.sh` lo mostró en producción:

```
deploy-bff-1     ghcr.io/josepcal/tfm_rehab_followup_checkup/api:latest
                 sha256:61e0cb82987b279cb9b6ef440f0f1a47beb18c636fc1aa339cea48ad08e45e29
deploy-worker-1  ghcr.io/josepcal/tfm_rehab_followup_checkup/api:latest
                 sha256:61e0cb82987b279cb9b6ef440f0f1a47beb18c636fc1aa339cea48ad08e45e29
```

**Impacto.** La VM del stack se destruye y recrea en cada ciclo de demo, y cada arranque
descarga la imagen de nuevo. Con un tag mutable, un push a `main` entre dos `apply`
idénticos hace que se levante código distinto sin ningún aviso, y el despliegue no deja
constancia de qué versión se ejecutó.

**Corrección aplicada** (2026-07-19), en tres piezas:

1. Variable `api_image` en el módulo Terraform del stack (por defecto vacía, cambio
   aditivo: sin ella el comportamiento es el de antes).
2. `cloud-init` escribe `API_IMAGE` en el `.env` **solo si viene informada**; vacía, el
   compose aplica su valor por defecto.
3. El workflow de CI se dispara también con tags `v*` y publica `api:vX.Y.Z`, sin mover
   `latest` — para que reetiquetar una versión antigua no sobrescriba lo que apunta `main`.

Procedimiento documentado en el **Anexo B** de ambos `RUNBOOK`. Verificable con
`ftm-status.sh`, que muestra tag y digest resuelto por contenedor.

> **Advertencia operativa.** El disparador por tag debe estar en `main` **antes** de crear
> el tag: GitHub lee el workflow del commit al que este apunta. Etiquetar un commit anterior
> al disparador no produce ninguna ejecución — comprobado durante esta auditoría.

---

## Pendiente (no bloqueante para la entrega)

### P-1 · Migraciones automáticas en el arranque

Ejecutar `alembic upgrade head` desde `cloud-init` antes de arrancar el `bff`, eliminando el
paso manual de H-2. Un paso manual en un procedimiento que se repite en cada demo acabará
olvidándose otra vez.

### P-2 · Verificación de firma criptográfica de las imágenes (cosign / Sigstore)

El pin por digest o por tag de versión (H-4) garantiza **inmutabilidad**: que lo desplegado
es idéntico a lo validado. No garantiza **procedencia**: que la imagen la construyó
realmente este proyecto y no un tercero con acceso al registro.

Cerrar esa brecha requiere:

1. **Firmar en CI.** Paso `cosign sign` en `deploy.yml`, con firma *keyless* (OIDC de GitHub
   Actions + Sigstore) para no gestionar claves privadas.
2. **Verificar en el stack.** Instalar `cosign` vía `cloud-init` y ejecutar, antes del
   `docker compose up`, una verificación que ate la firma a la identidad del repositorio:

   ```bash
   cosign verify \
     --certificate-identity-regexp "https://github.com/josepcal/.*" \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com \
     ghcr.io/josepcal/tfm_rehab_followup_checkup/api:v1.0.2
   ```
3. **Abortar el arranque** si la verificación falla.

**Por qué no se ha implementado.** La verificación *keyless* consulta el log de
transparencia público de Sigstore (Rekor) por internet. El stack no tiene IP pública y sale
por NAT a través del edge: funcionaría, pero introduciría una **dependencia externa en el
camino de arranque**. Si Sigstore no está disponible, la demo no levanta. Puede evitarse con
verificación `--offline` y el *bundle* de firma adjunto, a costa de complicar
apreciablemente el `cloud-init`.

**Valoración.** El control mitiga compromiso del registro y ataques a la cadena de
suministro — amenazas relevantes en un entorno con varios equipos publicando imágenes. En
este proyecto, con un único publicador y el pin ya aplicado, el beneficio marginal no
justifica añadir un punto de fallo en el arranque a corto plazo. Queda como línea de trabajo
futuro, no como carencia de seguridad activa.
