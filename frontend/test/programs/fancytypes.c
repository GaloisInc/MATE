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

typedef struct {
  char *tag;
  struct {
    int a, b, c;
  };
  union {
    int integral;
    float floating;
  };
} foo;

const foo *frobulate(const foo *bar, const char *baz) {
  if (COINFLIP()) {
    return NULL;
  }

  return bar;
}

int main(int argc, char const *argv[]) {
  const volatile int x = COINFLIP();
  volatile int y = COINFLIP();
  const volatile int *z = NULL;
  const volatile int *volatile q = NULL;

  z = &x;
  q = &y;

  if (COINFLIP()) {
    const volatile int *volatile n = z;
    z = q;
    q = n;
  }

  typeof(frobulate) *__frobulate = frobulate;

  printf("%p %p %p\n", z, q, __frobulate);
  return 0;
}
