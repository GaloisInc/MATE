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
void baz(void) __attribute__((noinline));

int main(int argc, char const *argv[]) {
  srand(time(NULL));

  void (*table[])(void) = {
      foo,
      bar,
      baz,
  };

  table[rand() % 3]();
  return 0;
}

void foo(void) { printf("foo\n"); }

void bar(void) { printf("bar\n"); }

void baz(void) { printf("baz\n"); }
