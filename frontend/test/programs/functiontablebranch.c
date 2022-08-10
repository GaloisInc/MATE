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

bool foo(void) __attribute__((noinline));
bool bar(void) __attribute__((noinline));

int main(int argc, char const *argv[]) {
  srand(time(NULL));

  bool (*table[])(void) = {
      foo,
      bar,
  };

  if (table[rand() % 2]()) {
    printf("random function call returned true\n");
  } else {
    printf("random function call returned false\n");
  }
  return 0;
}

bool foo(void) { return true; }

bool bar(void) { return false; }
