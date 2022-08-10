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

static void __attribute__((always_inline)) foo(int a, int b, int c, int d) {
  float inline_variable1 = 1.0, inline_variable2 = 2.0, inline_variable3 = 3.0;

  double inline_variable4 = a + b + c + d;

  if (COINFLIP()) {
    inline_variable4 += inline_variable4;
  } else {
    inline_variable4 += inline_variable1 + inline_variable2 + inline_variable3;
  }

  printf("%f\n", inline_variable4);
}

int main(int argc, char const *argv[]) {
  foo(COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP());
  return 0;
}
