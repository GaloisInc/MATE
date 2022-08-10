#include <inttypes.h>
#include <stdint.h>

struct data {
  uint32_t val;
  int array[10];
  struct data *next;
};

int func(struct data *d) {
  int a = d->array[d->next->val % 10]; // Symbolic offset read
  if (a == 42)
    d->next->val = 0;
  else
    d->next->val = 1;
  return d->val;
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}