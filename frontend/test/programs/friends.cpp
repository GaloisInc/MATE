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

class BefriendedClass {
  int x;

  friend int friendly_function1(BefriendedClass &a);

  friend int friendly_function2(BefriendedClass &a, int x) {
    a.x = (COINFLIP() * x) + x;
    return COINFLIP();
  }

  template <typename T> friend T friendly_function3(BefriendedClass &a, T x);

  friend class FriendlyClass;

  template <typename T> friend class FriendlyGenericClass;
};

class FriendlyClass {
public:
  void getx(const BefriendedClass &a) { std::cout << a.x << std::endl; }
};

template <typename T> class FriendlyGenericClass {
public:
  void badda_bing(BefriendedClass &a, T x) { a.x = x * -x; }
};

int friendly_function1(BefriendedClass &a) {
  a.x++;
  return COINFLIP();
}

template <typename T> T friendly_function3(BefriendedClass &a, T x) {
  a.x = x * x * x + COINFLIP();
  return (T)COINFLIP();
}

int main(int argc, char const *argv[]) {
  BefriendedClass a;
  FriendlyClass b;
  FriendlyGenericClass<char> c;

  if (COINFLIP()) {
    friendly_function1(a);
    friendly_function1(a);
    friendly_function1(a);
    friendly_function1(a);
    c.badda_bing(a, 'a');
  } else {
    friendly_function2(a, COINFLIP());
    friendly_function3(a, 3.14);
    c.badda_bing(a, 'b');
  }

  b.getx(a);

  return 0;
}
