#!/usr/bin/env bash
# Deploy a Helm release, run the smoke test, and roll back to the previous
# revision if the smoke test fails. Exits non-zero when a rollback happened,
# so the pipeline stage is marked failed and later stages do not run.
set -euo pipefail

usage() { echo "usage: $0 --release R --namespace N --chart DIR --values FILE --image REPO --tag TAG [--set k=v]"; exit 2; }

EXTRA_SET=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --release) RELEASE=$2; shift 2;;
    --namespace) NS=$2; shift 2;;
    --chart) CHART=$2; shift 2;;
    --values) VALUES=$2; shift 2;;
    --image) IMAGE=$2; shift 2;;
    --tag) TAG=$2; shift 2;;
    --set) EXTRA_SET+=(--set "$2"); shift 2;;
    *) usage;;
  esac
done
: "${RELEASE:?}" "${NS:?}" "${CHART:?}" "${VALUES:?}" "${IMAGE:?}" "${TAG:?}"

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
LOCAL_PORT=${LOCAL_PORT:-18080}

kubectl get namespace "$NS" >/dev/null 2>&1 || kubectl create namespace "$NS"

PREVIOUS_REVISION=$(helm history "$RELEASE" -n "$NS" --max 1 -o json 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[-1]["revision"] if d else "")' || true)
echo "Current revision before deploy: ${PREVIOUS_REVISION:-none}"

helm upgrade --install "$RELEASE" "$CHART" -n "$NS" \
  -f "$VALUES" --set image.repository="$IMAGE" --set image.tag="$TAG" \
  "${EXTRA_SET[@]}" --wait --timeout 5m

smoke() {
  local expected=$1
  kubectl -n "$NS" port-forward "svc/$RELEASE" "$LOCAL_PORT:80" >/tmp/port-forward.log 2>&1 &
  local pf=$!
  sleep 3
  set +e
  python3 "$SCRIPT_DIR/smoke_test.py" --base-url "http://127.0.0.1:$LOCAL_PORT" --expected-version "$expected"
  local rc=$?
  set -e
  kill "$pf" 2>/dev/null || true
  return $rc
}

if smoke "$TAG"; then
  echo "Release $RELEASE ($TAG) is healthy in $NS."
  exit 0
fi

echo "##vso[task.logissue type=error]Smoke test failed for $RELEASE:$TAG in $NS"
if [[ -z "${PREVIOUS_REVISION}" ]]; then
  echo "No previous revision to roll back to (first install). Uninstalling."
  helm uninstall "$RELEASE" -n "$NS"
  exit 1
fi

echo "Rolling back $RELEASE to revision $PREVIOUS_REVISION"
helm rollback "$RELEASE" "$PREVIOUS_REVISION" -n "$NS" --wait --timeout 5m
RESTORED_TAG=$(helm get values "$RELEASE" -n "$NS" -a -o json \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["image"]["tag"])')
if smoke "$RESTORED_TAG"; then
  echo "Rollback verified: $RELEASE is serving $RESTORED_TAG again."
else
  echo "##vso[task.logissue type=error]Rollback verification failed - page the on-call engineer"
fi
exit 1
