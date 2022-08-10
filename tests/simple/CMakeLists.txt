cmake_minimum_required(VERSION 3.1.0)

project(Examples)

add_executable(guessing-game
               guessing-game/guessing-game.cpp)

add_executable(registration
               registration/registration.cpp)

set(CMAKE_CXX_STANDARD 17)  # enable C++17 standard

# Warnings
target_compile_options(guessing-game PRIVATE
    -Werror
    -pedantic-errors
    -Wall
    -Wextra
    -Wconversion
    -Wsign-conversion
)
