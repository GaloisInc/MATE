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
  int x = 100;

  if (COINFLIP()) {
    auto lambda = [x]() {
      std::cout << "x=" << x << '\n';
      if (COINFLIP()) {
        std::cout << "foo" << '\n';
      } else {
        std::cout << "bar" << '\n';
      }
    };

    lambda();
  }
  return 0;
}
