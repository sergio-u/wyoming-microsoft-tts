#!/usr/bin/with-contenv bashio

set -e

# CONFIG_PATH=/data/options.json

bashio::log.info "Loading parameters"
SUBSCRIPTION_KEY="$(bashio::config 'subscription_key')"
SERVICE_REGION="$(bashio::config 'service_region')"
LANGUAGE="$(bashio::config 'language')"

bashio::log.info "Sub: ${SUBSCRIPTION_KEY}"
bashio::log.info "Reg: ${SERVICE_REGION}"
bashio::log.info "Lang: ${LANGUAGE}"

python3 ./__main__.py --uri "tcp://0.0.0.0:10200" --subscription-key "${SUBSCRIPTION_KEY}" --service-region "${SERVICE_REGION}" --download-dir /data --language "${LANGUAGE}"
