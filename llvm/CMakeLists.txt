cmake_minimum_required(VERSION 3.4.3 FATAL_ERROR)
project(mate-llvm LANGUAGES C CXX)

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(LLVM 10.0.1 REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

find_package(Boost 1.71 REQUIRED COMPONENTS system filesystem program_options
                                            iostreams)

find_package(OpenMP REQUIRED)

# Only allow the following two build configurations
set(CMAKE_CONFIGURATION_TYPES MATEDebug MATERelease)
set(CMAKE_CXX_FLAGS_MATEDEBUG "${CMAKE_CXX_FLAGS_DEBUG} -g -O1")
set(CMAKE_CXX_FLAGS_MATERELEASE
    "${CMAKE_CXX_FLAGS_RELWITHDEBINFO} -g -O2 -DNDEBUG")
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE
      MATEDebug
      CACHE STRING "Choose the type of build : MATEDebug MATERelease." FORCE)
endif(NOT CMAKE_BUILD_TYPE)

# Add clang-tidy target
find_program(
  CLANG_TIDY
  NAMES "clang-tidy"
  DOC "Path to clang-tidy executable.")

# Add clang-format target
find_program(
  CLANG_FORMAT
  NAMES "clang-format"
  DOC "Path to clang-format executable.")

add_subdirectory(PointerAnalysis)
add_subdirectory(MATE)
add_subdirectory(headache)
add_subdirectory(nomina)
