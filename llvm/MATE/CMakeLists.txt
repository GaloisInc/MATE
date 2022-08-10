find_package(LLVM 10.0.1 REQUIRED CONFIG)
message(STATUS "Found LLVM ${LLVM_PACKAGE_VERSION}")
message(STATUS "Using LLVMConfig.cmake in: ${LLVM_DIR}")

add_definitions(${LLVM_DEFINITIONS})
include_directories(SYSTEM ${LLVM_INCLUDE_DIRS})
link_directories(${LLVM_LIBRARY_DIRS})
list(APPEND CMAKE_MODULE_PATH "${LLVM_CMAKE_DIR}")

add_library(
  MATE MODULE
  # List your source files here.
  ASTGraphWriter.cpp
  ControlDependenceGraph.cpp
  Nodes.cpp
  Serialize/Types.cpp
  Serialize/Nodes.cpp
  TraceLogger.cpp
  Utils.cpp)

# Use C++17 to compile our pass (i.e., supply -std=c++17).
target_compile_features(MATE PUBLIC cxx_std_17)

# LLVM is (typically) built with no C++ RTTI. We need to match that; otherwise,
# we'll get linker errors about missing RTTI data.
if(NOT LLVM_ENABLE_RTTI)
  target_compile_options(MATE PRIVATE -fno-rtti)
endif()

# Warnings
target_compile_options(
  MATE
  PRIVATE -Werror
          -pedantic-errors
          -Wall
          -Wextra
          -Wconversion
          -Wsign-conversion
          -Wreturn-type
          -Wimplicit-fallthrough)

target_link_libraries(MATE PRIVATE PAPassInterface)

# Get proper shared-library behavior (where symbols are not necessarily resolved
# when the shared library is linked) on OS X.
if(APPLE)
  target_link_options(MATE PRIVATE -undefined dynamic_lookup)
endif(APPLE)

get_target_property(MATE_SOURCES MATE SOURCES)
foreach(mate_source ${MATE_SOURCES})
  get_filename_component(ABSOLUTE_MATE_SOURCE ${mate_source} ABSOLUTE)
  list(APPEND ABSOLUTE_MATE_SOURCES ${ABSOLUTE_MATE_SOURCE})
endforeach()

if(CLANG_TIDY)
  add_custom_target(
    mate-tidy
    COMMAND ${CLANG_TIDY} -fix -p=${CMAKE_BINARY_DIR} -quiet
            ${ABSOLUTE_MATE_SOURCES}
    COMMENT "Linting with clang-tidy...")
endif()

if(CLANG_FORMAT)
  add_custom_target(
    mate-format
    COMMAND ${CLANG_FORMAT} -i ${ABSOLUTE_MATE_SOURCES}
    COMMENT "Formatting with clang-format...")
endif()
