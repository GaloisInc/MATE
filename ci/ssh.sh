#!/bin/sh

# This script sets up an SSH agent with access to a key that the CI runner can
# use to clone submodules from private repos and push documentation to the
# webserver.

set -eu

eval "$(ssh-agent -s)"
echo "${STOCKFISH_PKEY}" | tr -d '\r' | ssh-add -
mkdir -p ~/.ssh
chmod 700 ~/.ssh
if [ -f /.dockerenv ]; then
  printf '%s\n\t%s\n\n' 'Host *' 'StrictHostKeyChecking no' > ~/.ssh/config
fi
chmod 600 ~/.ssh/config
