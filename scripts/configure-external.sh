#!/usr/bin/env bash
# configure-external.sh — point the pipestream dev stack at EXTERNAL infra
# (OpenSearch, Redis, DJL serving, Docling, optionally Kafka/Apicurio) so the
# JVM services can run on a memory-constrained box (e.g. a 24 GB laptop) while
# the heavy/stateful pieces live on a NAS / remote host.
#
# For each endpoint it: prompts (with a default) -> LIVE-TESTS it -> on failure
# lets you retry / use-anyway / skip. At the end it writes a delimited block
# into ~/.pipeline/dev/.env. Idempotent: re-running replaces just that block,
# leaving CORE_SERVICES_DIR / MODULES_DIR / etc. untouched.
#
# Defaults are generic (localhost). To pre-fill YOUR hosts without committing
# them, copy templates/external-defaults.env.example to
# ~/.pipeline/dev/external-defaults.env and set DEFAULT_* there — this script
# sources it automatically.
#
# Portable: bash 3.2 + curl + /dev/tcp (no redis-cli / nc / gnu-isms).

set -uo pipefail
ENV_FILE="${ENV_FILE:-$HOME/.pipeline/dev/.env}"
DEFAULTS_FILE="${EXTERNAL_DEFAULTS:-$HOME/.pipeline/dev/external-defaults.env}"
[ -f "$DEFAULTS_FILE" ] && . "$DEFAULTS_FILE"

# Generic fallbacks (override via external-defaults.env or the prompts).
: "${DEFAULT_OPENSEARCH_URL:=http://localhost:9200}"
: "${DEFAULT_OPENSEARCH_USER:=}"
: "${DEFAULT_OPENSEARCH_PASS:=}"
: "${DEFAULT_REDIS_HOST:=localhost}"
: "${DEFAULT_REDIS_PORT:=6379}"
: "${DEFAULT_DJL_URL:=http://localhost:8090}"
: "${DEFAULT_DOCLING_URL:=http://localhost:5001}"
: "${DEFAULT_DOCLING_KEY:=}"
: "${DEFAULT_KAFKA_HOST:=localhost}"
: "${DEFAULT_KAFKA_PORT:=9094}"
: "${DEFAULT_APICURIO_URL:=http://localhost:8081/apis/registry/v3}"

BEGIN="# >>> external-endpoints (configure-external.sh) >>>"
END="# <<< external-endpoints <<<"
BLOCK=""

ok()   { printf '  \033[32m\xe2\x9c\x93\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m\xe2\x9c\x97\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
hdr()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
add()  { BLOCK="${BLOCK}$1
"; }

http_alive() { # http_alive URL [match]
  local url="$1" match="${2:-}" body code
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 6 "$url" 2>/dev/null)
  [ -n "$code" ] && [ "$code" != "000" ] || return 1
  [ -z "$match" ] && return 0
  body=$(curl -sk --max-time 6 "$url" 2>/dev/null); printf '%s' "$body" | grep -qi "$match"
}
tcp_alive()  { ( exec 3<>"/dev/tcp/$1/$2" ) >/dev/null 2>&1; }
redis_ping() { local r; r=$( { exec 3<>"/dev/tcp/$1/$2"; printf 'PING\r\n' >&3; head -c 16 <&3; } 2>/dev/null ); printf '%s' "$r" | grep -qi PONG; }

ask() { local v="$1" p="$2" d="$3" in; printf '%s [%s]: ' "$p" "$d" >&2; read -r in; printf -v "$v" '%s' "${in:-$d}"; }
parse_url() { local u="$1" rest; U_SCHEME="${u%%://*}"; [ "$U_SCHEME" = "$u" ] && U_SCHEME="http"; rest="${u#*://}"; rest="${rest%%/*}"; U_HOST="${rest%%:*}"; if [ "$rest" = "$U_HOST" ]; then [ "$U_SCHEME" = "https" ] && U_PORT=443 || U_PORT=80; else U_PORT="${rest##*:}"; fi; }
confirm() { local label="$1"; shift; if "$@"; then ok "$label reachable"; return 0; fi; bad "$label NOT reachable"; local a; printf '    [u]se anyway / [s]kip / [r]etry? [r]: ' >&2; read -r a; case "$a" in u|U) warn "using unverified $label"; return 0;; s|S) warn "skipping $label (keeps default)"; return 1;; *) return 2;; esac; }

hdr "pipestream external-infra configurator"
echo "Writes external endpoint overrides to: $ENV_FILE"
[ -f "$DEFAULTS_FILE" ] && echo "Pre-filled from: $DEFAULTS_FILE"
echo "Leave a prompt blank to accept the [default]."

while :; do
  hdr "OpenSearch"
  ask OS_URL "Full URL (scheme://host:port)" "$DEFAULT_OPENSEARCH_URL"
  ask OS_USER "Username (blank if none)" "$DEFAULT_OPENSEARCH_USER"
  ask OS_PASS "Password (blank if none)" "$DEFAULT_OPENSEARCH_PASS"
  parse_url "$OS_URL"; rc=0
  confirm "OpenSearch ($OS_URL)" http_alive "$OS_URL/_cluster/health" "status" || rc=$?
  [ $rc -eq 2 ] && continue
  if [ $rc -eq 0 ]; then add "OPENSEARCH_PROTOCOL=$U_SCHEME"; add "OPENSEARCH_HOST=$U_HOST"; add "OPENSEARCH_PORT=$U_PORT"; add "OPENSEARCH_USERNAME=$OS_USER"; add "OPENSEARCH_PASSWORD=$OS_PASS"; fi
  break
done

while :; do
  hdr "Redis"
  ask R_HOST "Host" "$DEFAULT_REDIS_HOST"; ask R_PORT "Port" "$DEFAULT_REDIS_PORT"; rc=0
  confirm "Redis ($R_HOST:$R_PORT)" redis_ping "$R_HOST" "$R_PORT" || rc=$?
  [ $rc -eq 2 ] && continue
  [ $rc -eq 0 ] && { add "REDIS_HOST=$R_HOST"; add "REDIS_PORT=$R_PORT"; }
  break
done

while :; do
  hdr "DJL Serving (embeddings)"
  ask DJL_URL "URL" "$DEFAULT_DJL_URL"; rc=0
  confirm "DJL ($DJL_URL)" http_alive "$DJL_URL/ping" || rc=$?
  [ $rc -eq 2 ] && continue
  [ $rc -eq 0 ] && add "EMBEDDER_DJL_SERVING_URL=$DJL_URL"
  break
done

while :; do
  hdr "Docling (document parser backend)"
  ask DOC_URL "Base URL" "$DEFAULT_DOCLING_URL"; ask DOC_KEY "API key (blank for default)" "$DEFAULT_DOCLING_KEY"; rc=0
  confirm "Docling ($DOC_URL)" http_alive "$DOC_URL/health" || rc=$?
  [ $rc -eq 2 ] && continue
  if [ $rc -eq 0 ]; then add "DOCLING_BASE_URL=$DOC_URL"; [ -n "$DOC_KEY" ] && add "DOCLING_API_KEY=$DOC_KEY"; fi
  break
done

printf '\nExternalize Kafka + Apicurio too (saves ~1.5GB; adds LAN latency)? [y/N]: '; read -r EXTRA
case "$EXTRA" in y|Y)
  while :; do hdr "Kafka"; ask K_HOST "Bootstrap host" "$DEFAULT_KAFKA_HOST"; ask K_PORT "Bootstrap port" "$DEFAULT_KAFKA_PORT"; rc=0
    confirm "Kafka ($K_HOST:$K_PORT)" tcp_alive "$K_HOST" "$K_PORT" || rc=$?; [ $rc -eq 2 ] && continue; [ $rc -eq 0 ] && add "KAFKA_BOOTSTRAP_SERVERS=$K_HOST:$K_PORT"; break; done
  while :; do hdr "Apicurio registry"; ask AP_URL "Registry v3 URL" "$DEFAULT_APICURIO_URL"; rc=0
    confirm "Apicurio ($AP_URL)" http_alive "$AP_URL" || rc=$?; [ $rc -eq 2 ] && continue; [ $rc -eq 0 ] && add "APICURIO_REGISTRY_URL=$AP_URL"; break; done ;;
esac

hdr "Writing $ENV_FILE"
if [ -z "$BLOCK" ]; then warn "nothing verified/accepted — .env left unchanged"; exit 0; fi
mkdir -p "$(dirname "$ENV_FILE")"; touch "$ENV_FILE"
awk -v b="$BEGIN" -v e="$END" '$0==b{skip=1} skip&&$0==e{skip=0;next} !skip{print}' "$ENV_FILE" > "$ENV_FILE.tmp"
{ cat "$ENV_FILE.tmp"; printf '\n%s\n' "$BEGIN"; printf '%s' "$BLOCK"; printf '%s\n' "$END"; } > "$ENV_FILE"
rm -f "$ENV_FILE.tmp"
ok "external-endpoints block written"
echo; echo "Block contents:"; printf '%s' "$BLOCK" | sed 's/^/    /'
echo; echo "Next: restart process-compose so services pick up the new env:"
echo "    process-compose down && process-compose -f ~/.pipeline/dev/process-compose.yaml up"
