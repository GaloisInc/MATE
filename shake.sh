#! /bin/sh
# Wrapper for the MATE build-system.
# Largely inspired by a similar script for GHC's Hadrian.

CABAL_FILE=shake/mate.cabal

if ! [ -f $CABAL_FILE ]
then
    echo "You should run this script from the root of the MATE source tree."
    exit 1
fi

(cd shake && cabal v2-run exe:mate -- -V --digest-and -C .. "$@")
