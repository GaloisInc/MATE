All scripts in this folder are expected to be POSIX sh compliant.
The reasoning is that they may be executed on very minimal systems such as alpine containers or NixOS that only have `/bin/sh`.

NB: This directory really should be named `scripts` and not `ci`, but the code churn required will have to wait for another day.  
see: https://gitlab-ext.galois.com/mate/MATE/-/issues/1117
