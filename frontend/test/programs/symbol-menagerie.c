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

int __attribute__((weak)) foo(int x) {
  printf("foo\n");
  return COINFLIP();
}

static int bar(int y, int z) {
  printf("bar\n");
  return COINFLIP() + COINFLIP();
}

static __typeof__(bar) *barp;
int barp_result;

int baz(int x, int y, int z) {
  printf("baz\n");

  if (barp != NULL) {
    printf("calling function pointer and resetting\n");

    barp_result = barp(COINFLIP() + COINFLIP(), COINFLIP());
    barp = NULL;
    return COINFLIP() + COINFLIP() + foo(COINFLIP()) + barp_result;
  } else {
    printf("calling bar directly\n");
    return COINFLIP() + COINFLIP() + foo(COINFLIP()) +
           bar(COINFLIP() + COINFLIP(), COINFLIP());
  }
}

int baz_alias() __attribute__((alias("baz")));
int baz_weak_alias() __attribute__((weak, alias("baz")));

__typeof__(malloc) *my_malloc = malloc;

__thread int quux = 0xcafecafe;

static __thread int quux2;

int quux3;

int main(int argc, char const *argv[]) {
  if (COINFLIP()) {
    foo(COINFLIP());
    printf("store: quux2, quux\n");
    quux2 = 1;
    quux = quux2 + COINFLIP();
  } else {
    barp = bar;
    barp(COINFLIP(), COINFLIP());
    printf("store: quux, quux2\n");
    quux = 2;
    quux2 = quux * quux * COINFLIP();
  }

  if (COINFLIP()) {
    foo(COINFLIP());
    printf("store: quux2, quux, quux3\n");
    quux2 = 1;
    quux = quux2 + COINFLIP();
    quux3 = quux + quux2;
  } else {
    barp = bar;
    barp(COINFLIP(), COINFLIP());
    printf("store: quux, quux2, quux3\n");
    quux = 2;
    quux2 = quux * quux * COINFLIP();
    quux3 = quux * quux2;
  }

  baz(COINFLIP(), COINFLIP(), quux);
  baz(COINFLIP(), COINFLIP(), quux2);
  baz(quux, quux2, quux3);
  return 0;
}
