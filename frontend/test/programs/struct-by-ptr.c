#include <inttypes.h>
#include <stdint.h>

struct data {
  uint32_t val;
  int array[10];
  struct data *next;
};

int func(struct data *d) {
  d->array[1] = d->array[2]; // Read/write, simple indirection
  if (d->next->val % 2 == 0) // Double indirection variable access
    d->next->array[1] = 0;
  else
    d->next->array[1] = 1;
  return d->val;
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}
