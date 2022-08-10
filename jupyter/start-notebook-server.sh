#!/bin/bash

# Prepopulate the notebook server with examples
mkdir -p ./examples
cp -R /root/notebook-examples/* ./examples/

# Start a notebook server at port 8889
jupyter notebook \
        --allow-root \
        --NotebookApp.token='' \
        --NotebookApp.disable_check_xsrf=true \
        --no-browser \
        --ip 0.0.0.0 \
        --port 8889
