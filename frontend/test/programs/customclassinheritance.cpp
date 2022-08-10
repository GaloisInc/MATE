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
  void act() { cout << "pant" << endl; }
};

class Cat : public Animal {
public:
  void act() {
    if (COINFLIP()) {
      cout << "meow" << endl;
    } else {
      cout << "purr" << endl;
    }
  }
};

class Dog : public Animal {
public:
  void act() {
    if (COINFLIP()) {
      cout << "bark" << endl;
    } else {
      cout << "woof" << endl;
    }
  }
};

int main(int argc, char const *argv[]) {
  Cat c;
  Dog d;
  Animal *a = nullptr;

  if (COINFLIP()) {
    a = new Cat();
  } else {
    a = new Dog();
  }

  c.act();
  d.act();
  a->act();

  return 0;
}
