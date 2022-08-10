cmake_minimum_required(VERSION 3.10 FATAL_ERROR)

find_package(LLVM 10.0.1 REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

add_definitions(${LLVM_DEFINITIONS})
include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")

include(LLVMConfig)
include(HandleLLVMOptions)
include(AddLLVM)

add_llvm_library(LLVMNomina MODULE BUILDTREE_ONLY nomina.cpp)
