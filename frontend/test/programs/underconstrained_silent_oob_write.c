#include <inttypes.h>
#include <stdint.h>

struct data {
  unsigned int val;
  char array[10];
  struct data *next;
};

int func(struct data *d) {
  // Write 42 at symbolic offset
  // This access can overwrite the 'next' field but
  // doesn't exceed the object bounds
  d->array[d->next->val % 18] = 42;
  return d->next->next->val; // d->next could be invalid now
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}