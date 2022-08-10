#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __cplusplus
#include <exception>
#include <functional>
#include <iostream>
#include <numeric>
#include <string>
#include <system_error>
#include <vector>
#endif

#define COINFLIP() (rand() % 2)

struct point32 {
  uint32_t x;
  uint32_t y;
};

struct point64 {
  uint64_t x;
  uint64_t y;
};

// At the default optimization level, LLVM turns the by-value point32
// argument into a single i64, which it then unpacks into two 32-bit
// fields.
// `define dso_local i32 @by_value32(i64 %0)`
__attribute__((noinline)) int by_value32(struct point32 foo) {
  return COINFLIP() + foo.x - foo.y;
}

// At the default optimization level, LLVM turns the by-value point64
// argument into two separate i64 arguments.
// `define dso_local i32 @by_value64(i64 %0, i64 %1)`
__attribute__((noinline)) int by_value64(struct point64 bar) {
  return COINFLIP() + bar.x - bar.y;
}

int main(int argc, char const *argv[]) {
  struct point32 foo = {};
  struct point64 bar = {};

  if (COINFLIP()) {
    foo.x = COINFLIP() + COINFLIP();
    foo.y = COINFLIP() + COINFLIP();
    bar.x = COINFLIP() + COINFLIP();
    bar.y = COINFLIP() + COINFLIP();
  } else {
    foo.x = COINFLIP() + COINFLIP();
    foo.y = COINFLIP() + COINFLIP();
    bar.x = COINFLIP() + COINFLIP();
    bar.y = COINFLIP() + COINFLIP();
  }

  return by_value32(foo) + by_value64(bar);
}
