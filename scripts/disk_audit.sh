#!/usr/bin/env bash
set -euo pipefail

# Registra espacio libre en disco en CSV y genera alertas locales por umbral.
#
# Variables de entorno opcionales:
#   DISK_AUDIT_MOUNT=/
#   DISK_AUDIT_CSV_PATH=/var/log/osemosys/disk_audit.csv
#   DISK_ALERT_LOG_PATH=/var/log/osemosys/disk_alerts.log
#   DISK_ALERT_THRESHOLDS_GB=60,50,40

DISK_AUDIT_MOUNT="${DISK_AUDIT_MOUNT:-/}"
DISK_AUDIT_CSV_PATH="${DISK_AUDIT_CSV_PATH:-/var/log/osemosys/disk_audit.csv}"
DISK_ALERT_LOG_PATH="${DISK_ALERT_LOG_PATH:-/var/log/osemosys/disk_alerts.log}"
DISK_ALERT_THRESHOLDS_GB="${DISK_ALERT_THRESHOLDS_GB:-60,50,40}"

IFS=',' read -r WARN_60_GB WARN_50_GB CRIT_40_GB <<<"${DISK_ALERT_THRESHOLDS_GB}"

if [[ -z "${WARN_60_GB}" || -z "${WARN_50_GB}" || -z "${CRIT_40_GB}" ]]; then
  echo "DISK_ALERT_THRESHOLDS_GB inválido. Usa formato: 60,50,40" >&2
  exit 1
fi

if ! [[ "${WARN_60_GB}" =~ ^[0-9]+$ && "${WARN_50_GB}" =~ ^[0-9]+$ && "${CRIT_40_GB}" =~ ^[0-9]+$ ]]; then
  echo "Los umbrales de DISK_ALERT_THRESHOLDS_GB deben ser enteros positivos." >&2
  exit 1
fi

timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
host="$(hostname -s 2>/dev/null || hostname)"

# df output normalizado en GB y porcentaje usado sin sufijos.
read -r total_gb _used_gb free_gb used_pct mount_point < <(
  df -BG --output=size,used,avail,pcent,target "${DISK_AUDIT_MOUNT}" \
    | tail -n 1 \
    | awk '{gsub(/G/,"",$1); gsub(/G/,"",$2); gsub(/G/,"",$3); gsub(/%/,"",$4); print $1, $2, $3, $4, $5}'
)

severity="OK"
if (( free_gb < CRIT_40_GB )); then
  severity="CRIT_40"
elif (( free_gb < WARN_50_GB )); then
  severity="WARN_50"
elif (( free_gb < WARN_60_GB )); then
  severity="WARN_60"
fi

mkdir -p "$(dirname "${DISK_AUDIT_CSV_PATH}")"
mkdir -p "$(dirname "${DISK_ALERT_LOG_PATH}")"

if [[ ! -f "${DISK_AUDIT_CSV_PATH}" ]]; then
  echo "timestamp,host,mount,free_gb,total_gb,used_pct,severity" >"${DISK_AUDIT_CSV_PATH}"
fi

echo "${timestamp},${host},${mount_point},${free_gb},${total_gb},${used_pct},${severity}" >>"${DISK_AUDIT_CSV_PATH}"

if [[ "${severity}" != "OK" ]]; then
  echo "${timestamp} ${severity} free_gb=${free_gb} total_gb=${total_gb} used_pct=${used_pct} mount=${mount_point}" >>"${DISK_ALERT_LOG_PATH}"
fi

