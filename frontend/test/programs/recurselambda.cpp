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
  std::function<void(int)> countdown;
  countdown = [&countdown](int x) {
    if (x <= 0) {
      std::cout << "done\n";
      return;
    }

    std::cout << x << '\n';
    countdown(x - 1);
  };

  countdown(10);

  return 0;
}
