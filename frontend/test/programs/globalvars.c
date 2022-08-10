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

int x, y, z;
static char *foo = "foo";
const char *bar = "bar";
float baz[] = {1, 2, 3, 4};

int main(int argc, char const *argv[]) {
  x = 0;
  y = COINFLIP();
  z = COINFLIP();

  printf("%d %d %d %s %s %f\n", x, y, z, foo, bar, baz[COINFLIP()]);
  return 0;
}
