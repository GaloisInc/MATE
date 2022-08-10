#!/bin/sh
set -eu
: "${REGISTRY_PASSWORD?"Error - Missing"}" "${REGISTRY_USER?Error - Missing}" "${REGISTRY_HOST?Error - Missing}"
echo "${REGISTRY_PASSWORD}" | docker login -u "${REGISTRY_USER}" --password-stdin "${REGISTRY_HOST}" || true
