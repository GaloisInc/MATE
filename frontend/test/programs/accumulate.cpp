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

__attribute__((noinline)) std::vector<std::vector<int>> build_vecs() {
  if (COINFLIP()) {
    return {
        {COINFLIP()},
        {COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP()},
    };
  } else {
    return {
        {COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP(), COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP(), COINFLIP()},
        {COINFLIP(), COINFLIP()},
        {COINFLIP()},
    };
  }
}

int main(int argc, char const *argv[]) {
  auto num_vecs = build_vecs();

  auto sizer = [](std::size_t accumulator, std::vector<int> &nums) {
    return accumulator + nums.size();
  };

  // At the default optimization level, LLVM produces a `std::accumulate`
  // instantiation that has three arguments instead of four: the `sizer`
  // functor is embedded into the instantiated function itself.
  auto count = std::accumulate(num_vecs.begin(), num_vecs.end(), 0, sizer);
  return count;
}
