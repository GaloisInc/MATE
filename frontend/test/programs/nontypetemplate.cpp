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

struct hey {
  int a, b, c;
};

enum kodes {
  EFOO,
  EBAR,
  EBAZ,
};

class Klass {
public:
  int ID;
};

struct hey jude = {0x1, 0x2, 0x3};
const char foo[] = "hello world";
int x = 10;

template <typename T, T x> class Foo {
public:
  void print() { std::cout << x << std::endl; }
};

template <int x> class Bar {
public:
  void print() { std::cout << x << std::endl; }
};

template <char x> class Baz {
public:
  void print() { std::cout << x << std::endl; }
};

template <const char x[]> class Quux {
public:
  void print() { std::cout << x << std::endl; }
};

template <std::nullptr_t x> class Zam {
public:
  void print() { std::cout << "(null)" << std::endl; }
};

int main(int argc, char const *argv[]) {
  Foo<int, 1> foo_int;
  Foo<char, 'b'> foo_char;
  Foo<struct hey *, &jude> foo_struct;
  Foo<const struct hey *, &jude> foo_const_struct;
  Foo<kodes, EFOO> foo_enum;
  Foo<int *, &x> foo_pointer;
  Foo<int Klass::*, &Klass::ID> foo_member_pointer;
  Bar<3> bar;
  Baz<'d'> baz;
  Quux<foo> quux;
  Zam<nullptr> zam;

  foo_int.print();
  foo_char.print();
  foo_struct.print();
  foo_const_struct.print();
  foo_enum.print();
  foo_pointer.print();
  foo_member_pointer.print();
  bar.print();
  baz.print();
  quux.print();
  zam.print();
  return 0;
}
