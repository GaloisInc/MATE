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

int foo(int x) __attribute__((noinline));
int bar(int x) __attribute__((noinline));
int baz(int x) __attribute__((noinline));

int main(int argc, char const *argv[]) {
  srand(time(NULL));

  int (*table[])(int) = {
      foo,
      bar,
      baz,
  };

  table[rand() % 3](rand());
  return 0;
}

int foo(int x) {
  printf("foo %d\n", x);
  return COINFLIP();
}

int bar(int x) {
  printf("bar %d\n", x);
  return COINFLIP();
}

int baz(int x) {
  printf("baz %d\n", x);
  return COINFLIP();
}
