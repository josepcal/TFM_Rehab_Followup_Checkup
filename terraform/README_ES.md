# Despliegue de FTM en Hetzner

> 🇬🇧 [English version](README.md)

Despliegue de producción efímero y económico del sistema de seguimiento de rehabilitación
FTM sobre Hetzner Cloud. Son tres capas de Terraform que aplicás en orden; el **stack**
(la app + los datos biométricos) **no tiene IP pública** y solo es alcanzable a través de
una VM **edge** siempre encendida. Las grabaciones de voz son datos de categoría especial
(RGPD) — la arquitectura las mantiene fuera de internet por construcción.

> Este README cubre las capas de Terraform y los pasos manuales posteriores al apply.
> Para el flujo operativo del día a día (levantar/bajar demos) y el cifrado de secretos,
> mirá [`../deploy/RUNBOOK.md`](../deploy/RUNBOOK.md).

## La arquitectura de un vistazo

```
Internet ──HTTPS──> VM edge (IP pública, nginx+TLS)  ──red privada──> VM stack (SIN IP pública)
                    167.233.190.87  10.0.1.10                          10.0.1.20
                    · sirve el frontend                                · keycloak, postgres×2,
                    · proxy /api, /realms, /ftm-recordings             ·   minio, bff, worker
                    · gateway NAT para la salida del stack             · volumen cifrado LUKS
```

| Capa | Vida | Contiene | ¿Destruible? |
|------|------|----------|--------------|
| `persistent` | para siempre | IP flotante, volumen de datos, red privada, ruta NAT | **No** (`prevent_destroy`) |
| `edge` | siempre encendida | VM nginx (cpx22), certificado TLS, gateway NAT | Sí, pero rara vez |
| `stack` | efímera | contenedores de la app (cpx32), sin IP pública | Sí — esta es la capa "up/down" |

## Requisitos previos

- Un proyecto de Hetzner Cloud + un token de API (lectura/escritura).
- `terraform >= 1.5`, la CLI `hcloud`, `sops` + `age` instalados localmente.
- Un par de claves SSH (`ssh-keygen -t ed25519`).
- Un dominio apuntando a la IP flotante (DuckDNS sirve; ver paso 4).
- Secretos cifrados: `deploy/secrets.sops.yaml` (ver [`../deploy/RUNBOOK.md`](../deploy/RUNBOOK.md)).

```bash
export TF_VAR_hcloud_token='<tu-token-de-hetzner>'
```

## Ruta rápida

Aplicá las capas **en orden**. Cada una depende de la anterior mediante estado remoto de solo lectura.

```bash
DOMAIN=ftm-followup-checkup.duckdns.org
SSH_PUB="$(cat ~/.ssh/id_ed25519.pub)"

# 1. persistent — IP flotante, volumen, red, ruta NAT (se aplica UNA sola vez)
terraform -chdir=hetzner/persistent init
terraform -chdir=hetzner/persistent apply -var="domain=$DOMAIN"

# 2. Apuntá el DNS a la IP flotante (mirá el output floating_ip_address), luego:

# 3. edge — VM nginx siempre encendida + gateway NAT
terraform -chdir=hetzner/edge init
terraform -chdir=hetzner/edge apply \
  -var="domain=$DOMAIN" \
  -var="ssh_public_key=$SSH_PUB" \
  -var='operator_ssh_cidrs=["<tu-ip>/32"]' \
  -var="ssl_cert_email=vos@ejemplo.com"

# 4. stack — la app efímera (repetí este destroy/apply en cada demo)
terraform -chdir=hetzner/stack init
terraform -chdir=hetzner/stack apply \
  -var="domain=$DOMAIN" \
  -var="ssh_public_key=$SSH_PUB" \
  -var="age_private_key=$(cat ~/ruta/a/age.key)" \
  -var="repo_url=https://github.com/josepcal/TFM_Rehab_Followup_Checkup.git"
```

## Variables requeridas por capa

Todo lo demás tiene un valor por defecto sensato (tipos de server, IPs, ubicación `nbg1`).

| Capa | `-var` requeridas |
|------|-------------------|
| `persistent` | `hcloud_token`*, `domain` |
| `edge` | `hcloud_token`*, `domain`, `ssh_public_key`, `operator_ssh_cidrs`, `ssl_cert_email` |
| `stack` | `hcloud_token`*, `domain`, `ssh_public_key`, `age_private_key`, `repo_url` |

\* `hcloud_token` se lee de `TF_VAR_hcloud_token` — nunca lo pases por línea de comandos.

## Pasos manuales tras el primer apply del stack

El cloud-init del stack instala y levanta todo, pero **tres cosas son pasos manuales de
una sola vez** sobre un volumen *nuevo* (persisten entre destroy/apply posteriores del stack):

1. **Emitir el certificado TLS** en la edge (una vez que el DNS resuelva a la IP flotante):
   ```bash
   ssh root@<ip-flotante> /usr/local/bin/ftm-issue-cert.sh
   ```
   Después subí por scp `deploy/nginx/ftm.conf` (con `__DOMAIN__`/`__STACK_PRIVATE_IP__`
   sustituidos) a `/etc/nginx/sites-available/ftm` y hacé `systemctl reload nginx`.
   Copiá el `web/dist/*` compilado a `/var/www/ftm`.

2. **Correr las migraciones** como el *owner* de la BD (no como el rol de runtime del bff),
   leyendo las credenciales del `.env` renderizado en la VM del stack:
   ```bash
   ssh -J root@<ip-flotante> root@10.0.1.20 'docker exec \
     -e DATABASE_URL=postgresql://$ADMIN_U:$ADMIN_P@postgres-app:5432/$DB \
     -e FTM_APP_DB_PASSWORD=$APP_P \
     deploy-bff-1 sh -c "cd /app/db-migrations && alembic upgrade head"'
   ```
   El contenedor `minio-init` crea el bucket + el usuario acotado automáticamente.

3. **Verificar** de punta a punta (ver checklist abajo).

> Esto se corre a mano hoy. Cablearlo de forma idempotente en el cloud-init del stack es
> el siguiente paso documentado hacia un `terraform apply` totalmente automático.

## Trampas (aprendidas a las malas)

| Síntoma | Causa | Solución (ya en el código) |
|---------|-------|----------------------------|
| El stack no puede `apt install` / `git clone` | La VM sin IP pública no tiene internet | NAT: ruta de red en `persistent` → edge; la edge hace masquerade de la salida |
| `Network is unreachable` desde el stack | El DHCP de Hetzner no da ruta por defecto | `bootcmd` del cloud-init: `ip route ... via 10.0.0.1 onlink` (el gateway es el primer host de la **red** `10.0.0.1`, no el de la subred) |
| `Could not resolve host` | systemd-resolved sin uplink | un drop-in fija el DNS de Hetzner `185.12.64.1` |
| Las vars de docker-compose salen vacías | `sops -d` emitía YAML | descifrar con `--output-type dotenv` |
| Keycloak/MinIO no publican el puerto | contenedor solo en red `internal:true` | adjuntar también `egress_net`; bind a `${STACK_PRIVATE_IP}` |
| Subida presignada 403/502 | MinIO firma con host interno / falta bucket+usuario | `S3_PUBLIC_ENDPOINT_URL` vía proxy de la edge; `minio-init` crea bucket+usuario |
| Riesgo de que un paciente vea datos de otro | el bff conectaba como **owner** de las tablas (bypasea RLS) | owner = `ADMIN_DB_USER`; el bff conecta como `ftm_app` (no-owner) |
| `server type cx22 not found` | Hetzner retiró los `cx*` | usar `cpx22`/`cpx32` |

## Checklist de verificación post-despliegue

- [ ] `terraform -chdir=hetzner/persistent apply` muestra el volumen con
      `delete_protection = true` (protege los datos biométricos).
- [ ] `ssh -J root@<ip-flotante> root@10.0.1.20 'ping -c2 1.1.1.1'` funciona (el NAT anda).
- [ ] `docker compose ... ps` muestra 6 contenedores arriba; postgres×2 + minio healthy.
- [ ] Navegador: login (Keycloak) → el paciente ve solo sus datos (RLS).
- [ ] Navegador: grabar → subir (200) → analizar → aparecen las métricas.
- [ ] `nmap <ip-flotante>` muestra solo 80/443; la VM del stack no tiene IP pública que escanear.
- [ ] Firewall SSH de la edge restringido de `0.0.0.0/0` a la IP del operador.

## Bajar una demo

```bash
terraform -chdir=hetzner/stack destroy -var="domain=$DOMAIN" -var=...   # mismas vars que el apply
```

Solo se destruye la VM del stack. El volumen, la IP flotante, el DNS, la red y la edge
sobreviven. Volver a levantarla = re-ejecutar el apply del stack; los datos persisten en el volumen.
