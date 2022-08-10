#!/bin/sh

# Test script to see if we're in a CI pipeline that should run integration
# tests, optimize heavily, etc.
#
# Specifically, will exit 0 (true) if:
#
# 1. this is a MR into stable,
# 2. this is a commit on stable, or
# 3. this is a pipeline inside a schedule (indicating a once-a-day pipeline on
#    master).
#
# This script should be kept in sync with the "rules:" clause of the
# ".on-stable:" configuration in .gitlab-ci.yml.

set -x

if [ "${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-fake}" = "stable" ] \
  || [ "${CI_COMMIT_BRANCH:-fake}" = "stable" ] \
  || [ -n "${SCHEDULE}" ]; then
  exit 0
fi
exit 1
