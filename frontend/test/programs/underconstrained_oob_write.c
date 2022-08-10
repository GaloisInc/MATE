#include <inttypes.h>
#include <stdint.h>

struct data {
  unsigned int val;
  char array[10];
  struct data *next;
};

int func(struct data *d) {
  // Write 42 at symbolic offset
  d->array[d->next->val] = 42; // OOB write
  return 0;
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}