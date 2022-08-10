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

int main(int argc, char const *argv[]) {
  int x = COINFLIP();

  switch (x) {
  case 0: {
    puts("foo");
    break;
  }
  case 1: {
    puts("bar");
    break;
  }
  case 2: {
    /* Dead case w/fallthrough, COINFLIP always returns 0 or 1 */
    int y = 100;
    printf("quux %d\n", y);
  }
  default: {
    /* Dead case, see above */
    return 1;
  }
  }
  return 0;
}
