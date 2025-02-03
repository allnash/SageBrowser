#!/bin/bash
# Start Path: install_packages.sh
CMAKE_ARGS="-DGGML_BLAS=ON -DGGML_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python="==0.2.90"
pipenv install
# End Path: install_packages.sh
