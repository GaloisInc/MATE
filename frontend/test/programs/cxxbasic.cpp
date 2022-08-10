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
  std::string foo = "bar";

  if (COINFLIP()) {
    std::cout << "foo=" << foo << '\n';
  } else {
    foo = "baz";
  }

  std::cout << "foo=" << foo << '\n';

  return 0;
}
