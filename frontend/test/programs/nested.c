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

  if (COINFLIP()) {
    puts("foo");
    if (COINFLIP()) {
      puts("bar");
      if (COINFLIP()) {
        puts("baz");
        return 0;
      }
    }
  } else {
    puts("quux");
    if (COINFLIP()) {
      puts("bang");
    }
  }

  return 0;
}
