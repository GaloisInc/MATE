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

void countdown(int x) __attribute__((noinline));

int main(int argc, char const *argv[]) {
  countdown(10);
  return 0;
}

void countdown(int x) {
  if (x <= 0) {
    printf("done\n");
    return;
  }

  printf("%d\n", x);
  countdown(x - 1);
}
