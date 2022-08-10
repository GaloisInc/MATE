#!/bin/sh
set -eu

: "${CI_CACHE_TAG?"Error: CI_CACHE_TAG should've been set in the .gitlab-ci.yml"}"
: "${CI_TAG?"Error: CI_TAG should've been set in the .gitlab-ci.yml"REGISTRY_HOST}"
: "${REGISTRY_HOST?"Error: REGISTRY_HOST should've been set in the .gltlab-ci.yml"}"

if [ -n "${CWD+x}" ]; then
  cd "${CWD}" || {
    r="${?}"
    echo "cd failed" > /dev/stderr
    exit "${r}"
  }
fi

build_img() {
  img="${REGISTRY_HOST}/${1}"
  master_img="${img}:master"
  cache_img="${img}:${CI_CACHE_TAG}"
  build_img="${img}:${CI_TAG}"
  unset img

  pids=""
  for i in "${master_img}" "${cache_img}" "${build_img}"; do
    docker pull "${i}" || true &
    pids="${pids} ${!}"
  done
  unset i

  for p in ${pids}; do
    wait "${p}"
  done
  unset pids p

  if [ ${#} -ge 2 ]; then
    docker build --build-arg BUILDKIT_INLINE_CACHE=1 --target "${2}" --cache-from "${master_img}" --cache-from "${cache_img}" --tag "${cache_img}" --tag "${build_img}" .
  else
    docker build --build-arg BUILDKIT_INLINE_CACHE=1 --cache-from "${master_img}" --cache-from "${cache_img}" --tag "${cache_img}" --tag "${build_img}" .
  fi

  pids=""
  for i in "${master_img}" "${cache_img}" "${build_img}"; do
    docker push "${i}" &
    pids="${pids} ${!}"
  done
  unset i

  for p in ${pids}; do
    wait "${p}"
  done
  unset pids p

  unset build_img cache_img master_img
}

# https://www.grymoire.com/Unix/Sh.html#uh-71
build_img ${1+"$@"}
