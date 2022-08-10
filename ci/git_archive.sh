#!/bin/sh

set -eu

# https://ttboj.wordpress.com/2015/07/23/git-archive-with-submodules-and-tar-magic/
# https://reproducible-builds.org/docs/archives/
# NB: tar's --sort=name is locale independent, so LC_ALL=C is not required for deterministic sort order

# OUTPUT must be relative to the git root
OUTPUT="${1?"Error: Output file missing"}"
OUTPUT="$(git rev-parse --show-toplevel)/${OUTPUT}"
ARCHIVE_VERSION="${ARCHIVE_VERSION:-HEAD}"
echo "${OUTPUT}" > /tmp/.output-filename

git archive --prefix=mate-code-drop/ "${ARCHIVE_VERSION}" | tar -xf -
tar --sort=name \
  --owner=0 --group=0 --numeric-owner \
  --mtime="@${SOURCE_DATE_EPOCH}" \
  --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  -cf "${OUTPUT}" mate-code-drop
rm -rf mate-code-drop

git submodule --quiet foreach "$(
  cat << 'EOF'
git archive --prefix=mate-code-drop/"${sm_path}"/ HEAD > "${toplevel}/${sha1}.tar" && \
tar --sort=name \
  --owner=0 --group=0 --numeric-owner \
  --mtime="@${SOURCE_DATE_EPOCH}" \
  --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  --concatenate --file="$(cat /tmp/.output-filename)" "${toplevel}/${sha1}.tar"
rm "${toplevel}/${sha1}.tar"
EOF
)"

bzip2 -z9 "${OUTPUT}"
rm /tmp/.output-filename
