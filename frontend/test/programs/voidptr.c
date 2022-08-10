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

void voidptr(void *thing) {
  if (COINFLIP()) {
    printf("foo: %p\n", thing);
  } else {
    printf("bar: %p\n", thing);
  }
}

int main(int argc, char const *argv[]) {
  int x = COINFLIP();

  int y = COINFLIP();
  double z = COINFLIP() + 3.14;

  if (x) {
    voidptr(&y);
  } else {
    voidptr(&z);
  }
}
