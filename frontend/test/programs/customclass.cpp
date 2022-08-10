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

using namespace std;

class Animal {
public:
  void act() {
    if (COINFLIP()) {
      cout << "woof" << endl;
    } else {
      cout << "meow" << endl;
    }
  }
};

int main(int argc, char const *argv[]) {
  Animal a, b, c;

  a.act();
  a.act();
  b.act();
  b.act();
  c.act();
  c.act();
  return 0;
}
