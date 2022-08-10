#include <exception>

// Use C headers to avoid code explosion from templates.
#include <cstdio>
#include <cstdlib>

class Animal {
public:
  virtual void eat(void) const = 0;
};

class Dog : public Animal {
public:
  void eat(void) const override { puts("Dog eat\n"); }
};

class Llama : public Animal {
public:
  void eat(void) const override { puts("Llama eat\n"); }
};

int main(int argc, char **argv) {
  Animal *animals = (Animal *)malloc(8 * sizeof(Animal));
  for (int i = 0; i < 8; i++) {
    if (i % 2 == argc % 2) {
      animals[i] = Dog();
    } else {
      animals[i] = Llama();
    }
  }
  for (int i = 0; i < 32; i++) { // relatively high to prevent unrolling
    try {
      dynamic_cast<Llama *>(&animals[i])->eat();
    } catch (std::exception &e) {
      puts("Not a Llama.");
      return 1;
    }
  }
  return 0;
}
