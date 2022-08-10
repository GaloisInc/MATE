#include <cstdio>
#include <cstdlib>

#define COINFLIP() (rand() % 2)

class B1 {
public:
  virtual ~B1() {}
  void f0() {}
  virtual void f1() {}
  int int_in_b1;
};

class B2 {
public:
  virtual ~B2() {}
  virtual void f2() {}
  int int_in_b2;
};

class D : public B1, public B2 {
public:
  void d() {}
  void f2() override {}
  int int_in_d;
};

int main(int argc, char const *argv[]) {
  if (COINFLIP()) {
    B2 b2{};
    printf("%p\n", &b2);
  } else {
    D d{};
    printf("%p\n", &d);
  }

  return 0;
}
