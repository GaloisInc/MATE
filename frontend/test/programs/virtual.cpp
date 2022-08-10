// Thanks, Wikipedia: https://en.wikipedia.org/wiki/Virtual_function

// Use C headers to avoid code explosion from templates.
#include <cstdio>
#include <cstdlib>

class Animal {
public:
  virtual void eat(void) const = 0;
};

class Llama : public Animal {
public:
  void eat(void) const override { puts("Llama eat\n"); }
};

class Dog : public Animal {
public:
  void eat(void) const override { puts("Dog eat\n"); }
};

class Poodle : public Dog {
public:
  void eat(void) const override { puts("Poodle eat\n"); }
};

void everyone_eats(Animal **, unsigned int) __attribute__((noinline));
void everyone_eats(Animal **animals, unsigned int len) {
  for (int i = 0; i < len; i++) {
    animals[i]->eat();
  }
}

void someone_eats(Animal &) __attribute__((noinline));
void someone_eats(Animal &animal) { animal.eat(); }

int main(void) {
  Animal **animals = (Animal **)malloc(3 * sizeof(Animal *));
  Llama llama;
  Dog dog;
  Poodle poodle;
  animals[0] = &llama;
  animals[1] = &dog;
  animals[2] = &poodle;
  everyone_eats(animals, 3);
  someone_eats(poodle);
}
