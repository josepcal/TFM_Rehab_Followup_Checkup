# Despliegue de FTM en producción — Runbook del operador

> 🇬🇧 [English version](RUNBOOK.md)

Despliegue efímero en Hetzner: una VM **edge** siempre encendida (nginx + IP flotante) más
una VM **stack** bajo demanda (keycloak, postgres×2, minio, bff, worker) **sin IP pública**,
unidas por una red privada. Los datos viven en un volumen cifrado persistente.

**Arquitectura y justificación de las capas:** [`../terraform/README_ES.md`](../terraform/README_ES.md).
Este runbook es el procedimiento operativo del día a día; si nunca has desplegado este
sistema, lee antes el documento de arquitectura.

Registros de diseño: `openspec/tfm-prod-rollout.md` (propuesta), `openspec/design/tfm-prod-rollout.md` (diseño).

---

## Valores de referencia del despliegue

Los comandos de abajo usan los **valores reales de producción**. Sustitúyelos por los tuyos
si despliegas un entorno distinto.

| Valor | Producción |
|---|---|
| Dominio | `ftm-followup-checkup.duckdns.org` |
| IP flotante (destino del registro DNS A) | `167.233.190.87` |
| IP privada del edge | `10.0.1.10` |
| IP privada del stack | `10.0.1.20` |

Las tres capas reciben `-var="domain=..."`. Mantén el mismo valor en todas: una discrepancia
rompe a la vez el TLS, el emisor de Keycloak y las firmas de las URL prefirmadas.

---

## 0. Requisitos previos (una sola vez)

Herramientas en la máquina del operador: `terraform`, `sops`, `age`, CLI de `hcloud`,
`node` 20+, `ssh`, `rsync`.

```bash
export TF_VAR_hcloud_token='<hetzner-api-token>'        # nunca se commitea
export TF_VAR_age_private_key="$(cat age.key)"          # tu clave privada age
```

- Genera un par de claves age: `age-keygen -o age.key` (imprime la clave pública `age1...`).
- Pon la clave pública en `deploy/.sops.yaml` (sustituye el marcador de posición).
- Necesitas un dominio cuyo registro A puedas apuntar a la IP flotante (p. ej. DuckDNS).

### Cifrar los secretos (una vez, y en cada rotación)

```bash
cp deploy/secrets.sops.yaml.example /tmp/secrets.plain.yaml
# edita /tmp/secrets.plain.yaml con los valores reales (incluida LUKS_PASSPHRASE)
sops --encrypt --age age1TUCLAVEPUBLICA /tmp/secrets.plain.yaml > deploy/secrets.sops.yaml
shred -u /tmp/secrets.plain.yaml
```

El fichero cifrado puede commitearse: SOPS cifra los valores. La **clave privada age** no
va nunca a git y no sale de la máquina del operador.

---

## 1. Capa persistente (se aplica UNA VEZ y se deja para siempre)

```bash
terraform -chdir=terraform/hetzner/persistent init
terraform -chdir=terraform/hetzner/persistent apply \
  -var="domain=ftm-followup-checkup.duckdns.org"
```

Crea: IP flotante, volumen de datos cifrable, red privada y subred. Todo con
`prevent_destroy` + `delete_protection`.

```bash
terraform -chdir=terraform/hetzner/persistent output floating_ip_address
```

### Apuntar el DNS a la IP flotante

Configura el registro A del dominio → IP flotante. Confirma antes de continuar, o certbot
fallará:

```bash
dig +short ftm-followup-checkup.duckdns.org    # debe imprimir la IP flotante
```

---

## 2. Capa edge (se aplica UNA VEZ, siempre encendida)

```bash
terraform -chdir=terraform/hetzner/edge init
terraform -chdir=terraform/hetzner/edge apply \
  -var='operator_ssh_cidrs=["<tu-ip>/32"]' \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="domain=ftm-followup-checkup.duckdns.org" \
  -var="ssl_cert_email=tu@ejemplo.com"
```

El edge arranca con nginx, un vhost provisional en el `:80` y NAT (masquerading) para que
la VM del stack —que no tiene IP pública— pueda salir a internet.

### 2a. Emitir el certificado TLS

Solo cuando el DNS ya resuelva a la IP flotante:

```bash
EDGE=167.233.190.87
ssh root@$EDGE /usr/local/bin/ftm-issue-cert.sh
```

El script es idempotente: si el certificado ya existe, termina sin hacer nada.

### 2b. Instalar el vhost de enrutado

El vhost de cloud-init es provisional. Sustitúyelo por el real, que hace de proxy de `/api`,
`/realms` y `/ftm-recordings/` hacia el stack por la red privada:

```bash
DOMAIN=ftm-followup-checkup.duckdns.org
STACK_IP=10.0.1.20
EDGE=167.233.190.87

sed -e "s|__DOMAIN__|$DOMAIN|g" \
    -e "s|__STACK_PRIVATE_IP__|$STACK_IP|g" \
    deploy/nginx/ftm.conf > /tmp/ftm.conf

scp /tmp/ftm.conf root@$EDGE:/etc/nginx/sites-available/ftm
ssh root@$EDGE 'nginx -t && systemctl reload nginx'
```

`nginx -t` debe pasar antes del reload. Si falla, el vhost anterior sigue activo: corrige la
configuración y reintenta, en lugar de forzar un restart.

### 2c. Compilar y desplegar el frontend

El edge sirve el `dist/` de Vite como ficheros estáticos desde `/var/www/ftm`. Compila con
la configuración de Keycloak **de producción**: la SPA habla con Keycloak a través del edge,
en el mismo origen, así que la URL es el dominio público, **no** la IP privada del stack.

```bash
cd web
npm ci
VITE_FTM_AUTH_MODE=pkce \
VITE_FTM_KEYCLOAK_URL=https://ftm-followup-checkup.duckdns.org \
VITE_FTM_KEYCLOAK_REALM=ftm \
VITE_FTM_KEYCLOAK_CLIENT_ID=ftm-web \
npm run build

rsync -av --delete dist/ root@167.233.190.87:/var/www/ftm/
cd ..
```

El `--delete` importa: sin él, los assets con hash de compilaciones anteriores se acumulan
en `/var/www/ftm`.

> Recompila y vuelve a sincronizar cada vez que cambie el frontend. El edge está siempre
> encendido, así que este paso es independiente del ciclo de levantar/bajar el stack.

---

## 3. Levantar una demo (capa stack)

```bash
terraform -chdir=terraform/hetzner/stack init
terraform -chdir=terraform/hetzner/stack apply \
  -var="ssh_public_key=$(cat ~/.ssh/id_ed25519.pub)" \
  -var="repo_url=<git-url>" \
  -var="repo_ref=<rama-o-tag>" \
  -var="domain=ftm-followup-checkup.duckdns.org"
```

La VM del stack arranca **sin IP pública**, monta el volumen cifrado con LUKS en
`/mnt/ftm-data`, descifra `secrets.sops.yaml` en tmpfs, genera el `.env` y arranca el
compose. Solo es alcanzable desde el edge, por la red privada.

Cloud-init tarda unos minutos (descarga de imágenes, importación del realm de Keycloak,
aprovisionamiento del bucket de MinIO). No des por hecho que está listo: pasa a la
verificación.

### 3a. Aplicar las migraciones pendientes

**Cloud-init NO ejecuta migraciones.** Solo clona el repo, descifra los secretos y levanta
el compose. Como el volumen de datos es persistente y sobrevive a cada ciclo
destroy/apply, su esquema se queda atrás respecto al código desplegado. Este paso es
manual y hay que hacerlo **cada vez que el despliegue incluya una migración nueva**.

Primero, una instantánea del volumen (§6) — ahí viven datos de pacientes reales:

```bash
hcloud volume create-snapshot ftm-prod-data --description "pre-migracion $(date +%F)"
```

El contenedor `bff` se conecta como `ftm_app`, que **no puede ni leer** `alembic_version`.
Hay que sobrescribir `DATABASE_URL` con el rol administrador (credenciales en
`/run/ftm-secrets/.env` de la VM del stack):

```bash
export ADMIN_DB_USER=<usuario-admin>
export PASSWORD=<contrasena-admin>
export APP_DB_NAME=<nombre-bbdd>

# Comprobar la revisión actual
ssh -J root@167.233.190.87 root@10.0.1.20 \
  "docker exec -w /app/db-migrations \
     -e DATABASE_URL='postgresql://$ADMIN_DB_USER:$PASSWORD@postgres-app:5432/$APP_DB_NAME' \
     deploy-bff-1 alembic current"

# Aplicar las pendientes
ssh -J root@167.233.190.87 root@10.0.1.20 \
  "docker exec -w /app/db-migrations \
     -e DATABASE_URL='postgresql://$ADMIN_DB_USER:$PASSWORD@postgres-app:5432/$APP_DB_NAME' \
     deploy-bff-1 alembic upgrade head"
```

Usa **comillas dobles por fuera** (para que bash expanda las variables en local) y
**simples por dentro**. Con comillas simples por fuera, las variables no se expanden y la
URL llega sin credenciales.

> Síntoma de saltarse este paso: errores 500 con
> `invalid input value for enum ...` o columnas que no existen. No es un fallo del código:
> es el esquema desfasado.

---

## 4. Verificar el despliegue

### 4a. Desde la máquina del operador (superficie pública)

```bash
DOMAIN=ftm-followup-checkup.duckdns.org

# Salud de la API a través del edge
curl -fsS https://$DOMAIN/api/health          # -> {"status":"ok"}

# Realm de Keycloak a través del edge
curl -fsS https://$DOMAIN/realms/ftm | head -c 200

# Frontend
curl -fsS -o /dev/null -w '%{http_code}\n' https://$DOMAIN/    # -> 200
```

### 4b. Aislamiento de red (la comprobación relevante para el RGPD)

```bash
nmap 167.233.190.87        # solo debe verse el 80 (redirección) y el 443
```

La VM del stack no tiene IP pública, así que no hay dirección que escanear. Confirma que
Terraform opina lo mismo:

```bash
terraform -chdir=terraform/hetzner/stack output has_public_ip   # debe ser false
```

Postgres (5432), la API S3 de MinIO (9000), la consola de MinIO (9001), Keycloak (8080) y el
BFF (8000) **nunca** deben ser alcanzables desde internet. El compose los publica únicamente
en la IP privada del stack.

### 4c. En la VM del stack (usando el edge como salto)

El stack no tiene IP pública, así que hay que entrar por SSH a través del edge:

```bash
ssh -J root@167.233.190.87 root@10.0.1.20

# ya dentro del stack:
cd /opt/ftm/deploy
docker compose -f docker-compose.stack.yaml ps        # todos los servicios Up / healthy
docker compose -f docker-compose.stack.yaml logs -f worker
docker compose -f docker-compose.stack.yaml logs keycloak | tail -50
```

`minio-init` es un job de una sola ejecución: `Exited (0)` es su estado **correcto**, no un
fallo.

### 4d. Prueba funcional (en el navegador)

Entra en `https://ftm-followup-checkup.duckdns.org` como `paciente1` / `paciente1` y recorre
el flujo completo: **login (PKCE S256) → aceptar consentimiento → grabar → subir → métricas
→ informe**. Es la única comprobación que ejercita el ciclo de las URL prefirmadas a través
del edge, que es la parte más frágil de la topología.

---

## 5. Bajar una demo (los datos, la IP, el DNS y el edge sobreviven)

```bash
terraform -chdir=terraform/hetzner/stack destroy
```

Solo se destruye la VM del stack. El volumen, la IP flotante, el DNS, la red privada y la VM
edge permanecen (guardas `prevent_destroy` + estados de Terraform separados). Coste en
reposo: volumen + IP flotante + VM edge (~5–7 €/mes).

Volver a levantarla es de nuevo el paso 3: el volumen de datos se reengancha y se remonta,
así que los pacientes, las grabaciones y las métricas sobreviven al ciclo.

---

## 6. Copias de seguridad

Hetzner no tiene programación nativa de snapshots de volumen en Terraform. Haz un snapshot
manual antes y después de cada demo relevante:

```bash
hcloud volume create-snapshot ftm-prod-data --description "pre-demo $(date +%F)"
hcloud image list --type snapshot            # revisar
```

Esta es la salvaguarda real frente a una pérdida accidental de datos, NO el multi-AZ. Mantén
una retención corta (p. ej. los 3 últimos) y elimina los antiguos.

---

## 7. Resolución de problemas

### Certbot falla: "unauthorized" o "DNS problem"

El dominio todavía no resuelve a la IP flotante. `dig +short <dominio>` debe devolver la IP
flotante. La propagación de DuckDNS puede tardar unos minutos. Vuelve a ejecutar
`/usr/local/bin/ftm-issue-cert.sh`: es idempotente.

### El login redirige y falla / "Invalid parameter: redirect_uri"

El `frontendUrl` del realm de Keycloak y las URI de redirección del cliente `ftm-web` siguen
apuntando al dominio antiguo. `KC_HOSTNAME` se toma de `${DOMAIN}` en el compose, así que el
*servidor* sí conoce el dominio; pero la configuración del cliente vive en
**realm-export.json**, y ese fichero solo se importa en el primer arranque contra una base de
datos vacía.

Arréglalo con `kcadm.sh`, o corrige `deploy/keycloak/realm-export.json` y reimpórtalo sobre
un volumen limpio. Por tanto, cambiar de dominio implica siempre: actualizar la variable
`domain` en las tres capas → reemitir el certificado → actualizar el realm. Para parchear
el cliente en caliente, abre primero una shell `kcadm` autenticada (§8) y luego:

```bash
$KC update clients/<CLIENT_ID> -r ftm \
  -s 'redirectUris=["https://<nuevo-dominio>/*"]' \
  -s 'webOrigins=["https://<nuevo-dominio>"]' \
  -s 'rootUrl=https://<nuevo-dominio>' -s 'baseUrl=https://<nuevo-dominio>'
```

### 502 Bad Gateway en `/api` o `/realms`

El edge no llega al stack por la red privada. Comprueba, en este orden:

```bash
ssh root@167.233.190.87
curl -fsS http://10.0.1.20:8000/health          # ¿el BFF responde desde el edge?
curl -fsS http://10.0.1.20:8080/realms/ftm      # ¿y Keycloak?
```

Si fallan, el stack sigue arrancando (cloud-init, descarga de imágenes) o hay un servicio en
bucle de reinicio: revisa `docker compose ps` en el stack (§4c). Si nginx está haciendo proxy
a la dirección equivocada, comprueba que `__STACK_PRIVATE_IP__` se sustituyó de verdad:
`ssh root@$EDGE 'grep proxy_pass /etc/nginx/sites-available/ftm'`.

### La VM del stack arranca pero el volumen no se monta

La contraseña LUKS de `secrets.sops.yaml` no coincide con la que cifró el volumen, o falló el
descifrado de SOPS (`TF_VAR_age_private_key` ausente o incorrecta). Revisa cloud-init en el
stack:

```bash
ssh -J root@167.233.190.87 root@10.0.1.20 'cloud-init status --long; journalctl -u cloud-final --no-pager | tail -40'
```

**Nunca reformatees el volumen** para "arreglar" esto: destruirías los datos de los pacientes.

### La subida de una grabación devuelve 403 en `/ftm-recordings/`

Las firmas prefirmadas S3v4 se calculan sobre el host y la ruta públicos exactos
(`S3_PUBLIC_ENDPOINT_URL = https://<dominio>`). El bloque `location /ftm-recordings/` de nginx
debe reenviar **sin reescribir la ruta**: cualquier rewrite invalida la firma. Si lo que falta
es el bucket o el usuario acotado, vuelve a lanzar el job de inicialización:
`docker compose -f docker-compose.stack.yaml up minio-init`.

---

## 8. Administración de Keycloak — usa `kcadm.sh`, no la consola web

Keycloak se administra con la CLI oficial (`kcadm.sh`) desde dentro del contenedor, **no**
con la consola web de administración. Es una decisión de arquitectura deliberada en este
despliegue:

- La consola de administración (`/admin`) **no** la publica el edge: es superficie de
  ataque, y además sus scripts inline los bloquea la CSP estricta del edge
  (`default-src 'self'`), lo que se manifiesta como un "Loading the Administration
  Console" permanente.
- Ni siquiera funciona por un túnel SSH: `keycloak.js` carga un *login-status-iframe*
  oculto de OIDC que intenta enmarcar el frontend público, y el edge lo bloquea con
  `frame-ancestors 'none'` (protección anti-clickjacking correcta para la SPA clínica).
  Ese iframe es una opción de inicialización de `keycloak.js` incrustada en el bundle de
  la consola —no un ajuste de servidor ni de realm—, así que no se puede desactivar por
  configuración.

`kcadm.sh` esquiva todo eso: habla con Keycloak por localhost dentro del contenedor, sin
edge, sin CSP, sin iframe y sin túnel de navegador.

**Abre una shell en el contenedor y autentícate una vez por sesión:**

```bash
# En la VM del stack
cd /opt/ftm/deploy
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml exec keycloak bash

# Dentro del contenedor — define el atajo que usan todos los comandos de esta sección
KC=/opt/keycloak/bin/kcadm.sh

# Autentícate — usa KC_ADMIN_USER / KC_ADMIN_PASSWORD de secrets.sops.yaml
$KC config credentials \
  --server http://localhost:8080 --realm master \
  --user <KC_ADMIN_USER> --password '<KC_ADMIN_PASSWORD>'
```

El atajo `$KC` y la sesión autenticada viven solo en esa shell del contenedor: si sales y
vuelves a entrar, repite ambos pasos. Todos los comandos siguientes apuntan al realm
**`ftm`** (`-r ftm`).

**Usuarios — crear, borrar, listar:**

```bash
# Listar usuarios (id + username + email)
$KC get users -r ftm --fields id,username,email

# Crear un usuario (habilitado, con email)
$KC create users -r ftm \
  -s username=nuevo.medico -s email=nuevo.medico@ftm.local \
  -s enabled=true -s emailVerified=true

# Borrar un usuario (necesita el id del listado anterior)
$KC delete users/<USER_ID> -r ftm
```

**Resetear una contraseña:**

```bash
# Temporary=false → al usuario NO se le obliga a cambiarla en el próximo login
$KC set-password -r ftm --username medico1 --new-password 'NewStrongPass123' --temporary=false
```

**Roles — asignar / quitar roles de realm:**

```bash
# Listar los roles de realm disponibles
$KC get-roles -r ftm --available --uusername medico1

# Asignar un rol de realm (p. ej. medical)
$KC add-roles -r ftm --uusername medico1 --rolename medical

# Quitar un rol de realm
$KC remove-roles -r ftm --uusername medico1 --rolename medical

# Ver los roles de realm efectivos de un usuario
$KC get-roles -r ftm --uusername medico1 --effective
```

**Clientes — revisar:**

```bash
# Listar clientes (id + clientId)
$KC get clients -r ftm --fields id,clientId

# Inspeccionar un cliente (p. ej. ftm-web) — URI de redirección, mappers, flags
$KC get clients -r ftm -q clientId=ftm-web
```

> Para resetear la contraseña del **admin de master** (la cuenta de arriba), usa
> `$KC set-password -r master --username <KC_ADMIN_USER> --new-password '...' --temporary=false`.

**Trampa — el admin de bootstrap solo aplica sobre una BD vacía.** `KC_BOOTSTRAP_ADMIN_*`
solo se tienen en cuenta la primera vez que Keycloak arranca contra un volumen
`pg-keycloak` vacío. Sobre un volumen persistente, cambiar la contraseña en SOPS **no**
actualiza el admin existente. Para resetearlo (solo destruye la BD de Keycloak: los datos
de la aplicación y MinIO están en volúmenes separados, y el realm `ftm` se reimporta desde
`realm-export.json` en el siguiente arranque):

```bash
# En la VM del stack, en /opt/ftm/deploy. El .env vive en tmpfs — pásalo explícitamente.
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml stop keycloak postgres-keycloak
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml rm -f keycloak postgres-keycloak
rm -rf /mnt/ftm-data/pg-keycloak/*
docker compose --env-file /run/ftm-secrets/.env -f docker-compose.stack.yaml up -d keycloak
```

> Cualquier `docker compose` manual en la VM del stack **debe** pasar
> `--env-file /run/ftm-secrets/.env`. Los secretos descifrados viven en tmpfs (RAM), no en
> el directorio del compose; sin el flag todas las variables resuelven a cadena vacía y el
> comando falla con `invalid ip address:` al enlazar el puerto de MinIO.

---

## Notas de seguridad

- **El tfstate es sensible.** El estado de la capa stack contiene la clave age (se pasa por
  metadatos). Está en `.gitignore`; para una operación real, migra a un backend remoto
  cifrado (ver `terraform/hetzner/persistent/backend.tf`). No compartas el fichero de estado.
- **Rota los secretos** volviendo a cifrar `secrets.sops.yaml` y recreando la VM del stack.
  Hazlo una vez entregado el proyecto, ya que el fichero cifrado queda en el historial del
  repositorio.
- **Nunca publiques los servicios del stack en `0.0.0.0`.** El compose los enlaza a
  `${STACK_PRIVATE_IP}`; la consola de MinIO (`:9001`) no se publica en absoluto.
- **La consola de administración de Keycloak no es pública.** El edge solo hace proxy de
  `/realms`, `/resources` y `/js`; administra con `kcadm.sh` dentro del contenedor (§8). No
  vuelvas a añadir `/admin` al regex de nginx, ni añadas
  `'unsafe-inline'` ni relajes `frame-ancestors` en la CSP para que cargue la consola: eso
  debilita la protección contra XSS / clickjacking de toda la SPA clínica.
- **Las grabaciones de voz son datos de categoría especial (RGPD).** Dos controles distintos,
  contra amenazas distintas: el stack sin IP pública y el acceso exclusivo por red privada las
  mantienen **fuera del alcance de internet**; el volumen cifrado con LUKS las protege **en
  reposo**, frente a un acceso físico al disco o a la reasignación del volumen por parte del
  proveedor. La clave LUKS no la tiene Hetzner. No debilites ninguno de los dos por comodidad.
