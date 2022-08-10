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

int foo() {
  printf("%s\n", "inside foo!");
  return COINFLIP();
}

int bar() __attribute__((alias("foo")));

int main(int argc, char const *argv[]) {
  if (COINFLIP()) {
    printf("%s\n", "called foo!");
    printf("%d\n", foo());
  } else {
    printf("%s\n", "called bar, but...");
    printf("%d\n", bar());
  }

  if (COINFLIP()) {
    printf("%s\n", "called foo!");
    printf("%d\n", foo());
  } else {
    printf("%s\n", "called bar, but...");
    printf("%d\n", bar());
  }

  if (COINFLIP()) {
    printf("%s\n", "called foo!");
    printf("%d\n", foo());
  } else {
    printf("%s\n", "called bar, but...");
    printf("%d\n", bar());
  }
  return 0;
}
