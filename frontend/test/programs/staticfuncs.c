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

static int foo();
static void __attribute__((always_inline)) bar();

int main(int argc, char const *argv[]) {
  if (foo()) {
    bar();
  } else {
    bar();
    bar();
    bar();
  }
  return 0;
}

static int foo() { return COINFLIP(); }

static void bar() {
  if (COINFLIP() && COINFLIP()) {
    puts("bar");
  } else {
    switch (COINFLIP()) {
    default: {
      puts("default?");
      break;
    }
    case 0:
    case 1: {
      puts("flipped a coin");
      break;
    }
    }
  }
}
