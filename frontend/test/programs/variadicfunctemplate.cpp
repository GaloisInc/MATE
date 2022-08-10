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

template <typename T> T adder(T v) { return v; }

template <typename T, typename... Args> T adder(T first, Args... args) {
  return first + adder(args...);
}

int main(int argc, char const *argv[]) {
  int sum = adder(1, 2, COINFLIP(), COINFLIP());
  std::string ssum = adder(std::string("1"), std::string("2"), std::string("3"),
                           std::to_string(COINFLIP()));

  std::cout << "sum: " << sum << " ssum: " << ssum << std::endl;
  return 0;
}
