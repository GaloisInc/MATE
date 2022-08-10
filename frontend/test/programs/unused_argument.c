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

__attribute__((noinline)) int noargs() { return COINFLIP(); }
__attribute__((noinline)) int withargs(int i) { return i; }

int main(int argc, char const *argv[]) {
  int (*f)(int);
  if (COINFLIP()) {
    f = noargs; // NOLINT
  } else {
    f = withargs;
  }
  printf("noargs = %d\n", f(42));
  return 0;
}
