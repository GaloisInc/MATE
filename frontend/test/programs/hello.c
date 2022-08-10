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

void foo(void) __attribute__((noinline));
void bar(void) __attribute__((noinline));

int main(int argc, char const *argv[]) {
  printf("hello!\n");

  int x = COINFLIP();

  if (x) {
    printf("x != 0\n");
    foo();
  } else {
    printf("x == 0\n");
    bar();
  }
  return 0;
}

void foo(void) {
  printf("foo!\n");

  int y = COINFLIP();

  if (y) {
    printf("y != 0\n");
  } else {
    printf("y == 0\n");
  }
}

void bar(void) {
  printf("bar!\n");

  int z = COINFLIP();

  if (z) {
    printf("z != 0\n");
  } else {
    printf("z == 0\n");
  }
}
