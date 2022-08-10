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
  auto lambda = []() {
    if (COINFLIP()) {
      std::cout << "foo" << '\n';

      auto lambda2 = []() { std::cout << "baz" << '\n'; };

      lambda2();
    } else {
      std::cout << "bar" << '\n';

      auto lambda3 = []() { std::cout << "quux" << '\n'; };

      lambda3();
    }
  };

  lambda();

  return 0;
}
