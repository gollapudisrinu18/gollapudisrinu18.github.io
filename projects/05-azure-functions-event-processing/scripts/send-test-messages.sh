#!/usr/bin/env bash
# Sends the demo messages to the orders queue (Azurite locally or a real account).
# Messages are base64-encoded to match host.json "messageEncoding": "base64".
set -euo pipefail
CONN=${AZURE_STORAGE_CONNECTION_STRING:-UseDevelopmentStorage=true}
put() { az storage message put --connection-string "$CONN" -q orders --content "$(printf '%s' "$1" | base64 -w0)" -o none; }
az storage queue create --connection-string "$CONN" -n orders -o none
az storage queue create --connection-string "$CONN" -n orders-poison -o none
EVT='{"eventId":"evt-1","orderId":"ORD-1","amount":499.0,"currency":"INR"}'
put "$EVT"; put "$EVT"                                     # duplicate delivery
put '{"orderId":"ORD-3"}'                                  # malformed -> poison
echo "Sent 3 messages. Expect 1 'order processed', 1 'duplicate ignored', 1 poison."
