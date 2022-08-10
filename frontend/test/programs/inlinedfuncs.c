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

static int __attribute__((always_inline)) foo(int x, int y, int z);
static float __attribute__((always_inline)) bar(int a, int b);
double __attribute__((always_inline)) baz(int c);

int main(int argc, char const *argv[]) {
  int r1 = foo(COINFLIP(), COINFLIP(), COINFLIP());
  float r2 = bar(COINFLIP(), COINFLIP());
  double r3 = 0;

  if (COINFLIP()) {
    r3 = baz(COINFLIP());
  }

  if (COINFLIP()) {
    double r4 = r1 + r2 + r3;
    printf("%f\n", r4);
  }

  return 0;
}

static int foo(int x, int y, int z) {
  if (COINFLIP()) {
    printf("%d %d %d\n", x, y, z);
  }

  return x + y + z;
}

static float bar(int a, int b) {
  if (COINFLIP()) {
    printf("%d %d\n", a, b);
  }

  return (float)(a + b) / 2;
}

double baz(int c) {
  if (COINFLIP()) {
    printf("%d\n", c);
  }

  return (double)(c * 3.14);
}
