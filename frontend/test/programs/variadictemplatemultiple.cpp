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

template <typename... Args1, typename... Args2>
double foo(std::tuple<Args1...> args1, std::tuple<Args2...> args2) {
  return std::get<0>(args1) + std::get<0>(args2);
}

template <typename... Args> size_t bar(Args... args) {
  const auto v = {args...};
  return v.size();
}

template <typename T, typename... Args> size_t baz(T x, Args... args) {
  const auto v = {args...};
  return x + v.size();
}

int main(int argc, char const *argv[]) {
  std::cout << "foo: "
            << foo(std::make_tuple(0.1 + COINFLIP(), 0.2 + COINFLIP(),
                                   0.3 + COINFLIP()),
                   std::make_tuple(COINFLIP(), COINFLIP(), COINFLIP()))
            << std::endl;

  std::cout << "bar: "
            << bar(COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(),
                   COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(),
                   COINFLIP(), COINFLIP(), COINFLIP())
            << std::endl;

  std::cout << "baz: " << baz(COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP())
            << std::endl;

  return 0;
}
