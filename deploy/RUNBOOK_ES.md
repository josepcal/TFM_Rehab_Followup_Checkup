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

Arréglalo desde la consola de administración de Keycloak (`https://<dominio>/admin`,
credenciales en `secrets.sops.yaml`), o corrige `deploy/keycloak/realm-export.json` y
reimpórtalo sobre un volumen limpio. Por tanto, cambiar de dominio implica siempre:
actualizar la variable `domain` en las tres capas → reemitir el certificado → actualizar el
realm.

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

## Notas de seguridad

- **El tfstate es sensible.** El estado de la capa stack contiene la clave age (se pasa por
  metadatos). Está en `.gitignore`; para una operación real, migra a un backend remoto
  cifrado (ver `terraform/hetzner/persistent/backend.tf`). No compartas el fichero de estado.
- **Rota los secretos** volviendo a cifrar `secrets.sops.yaml` y recreando la VM del stack.
  Hazlo una vez entregado el proyecto, ya que el fichero cifrado queda en el historial del
  repositorio.
- **Nunca publiques los servicios del stack en `0.0.0.0`.** El compose los enlaza a
  `${STACK_PRIVATE_IP}`; la consola de MinIO (`:9001`) no se publica en absoluto.
- **Las grabaciones de voz son datos de categoría especial (RGPD).** El stack sin IP pública,
  el volumen cifrado con LUKS y el acceso exclusivo por red privada son los controles que las
  mantienen fuera de internet. No los debilites por comodidad.
