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

class test_exception : public std::exception {
public:
  test_exception(const std::string &msg) : m_msg(msg){};
  ~test_exception(){};
  virtual const char *what() const throw() { return m_msg.c_str(); }
  const std::string m_msg;
};

__attribute__((noinline)) int may_throw(int x, int y) __attribute__((optnone)) {
  x /= (y - y);
  return x;
}

__attribute__((noinline)) void must_throw() __attribute__((optnone)) {
  throw test_exception("oops");
}

__attribute__((noinline)) int catch_test(int x, int y) {
  try {
    must_throw();
  } catch (test_exception &e) {
    printf("caught!");
    throw;
  }
  try {
    return may_throw(x, y);
  } catch (test_exception &e) {
    printf("unreachable?");
    return 0;
  }
}

int main(int argc, char const *argv[]) {
  if (!COINFLIP()) {
    int x = 5;
    int y = 5;

    try {
      may_throw(x, y);
    } catch (std::exception &e) {
      std::cout << e.what() << '\n';
    }
  } else {
    try {
      std::string foo("foobar");
      foo.at(1000);
    } catch (std::out_of_range &e) {
      std::cout << e.what() << '\n';
    }
  }
  catch_test(42, 42);
  return 0;
}
