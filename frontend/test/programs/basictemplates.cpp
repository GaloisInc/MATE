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

using point = std::tuple<int, int>;

int main(int argc, char const *argv[]) {
  std::vector<int> foo = {1, 2, 3, 4, 5};
  std::vector<char> bar = {'a', 'b', 'c', 'd', 'e'};

  point a = std::make_tuple(rand() % foo.size(), rand() % bar.size());
  point b = std::make_tuple(rand() % foo.size(), rand() % bar.size());
  point c = std::make_tuple(rand() % foo.size(), rand() % bar.size());

  std::vector<point> pts = {a, b, c};

  for (const auto &p : pts) {
    std::cout << foo[std::get<0>(p)] << " " << bar[std::get<1>(p)] << std::endl;
  }
  return 0;
}
