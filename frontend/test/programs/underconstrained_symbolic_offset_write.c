#include <inttypes.h>
#include <stdint.h>

struct data {
  unsigned int val;
  char array[10];
  struct data *next;
};

int func(struct data *d) {
  int i;
  // Init array to zeros
  for (i = 0; i < 10; i++)
    d->array[i] = 0;
  // Write 42 at symbolic offset
  d->array[d->next->val % 10] = 42; // Symbolic offset write
  if (d->array[6] == 42)            // Branch depends on symbolic write
    d->next->val = 0;
  else
    d->next->val = 1;
  return d->next->next->val; // Triple dereference
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}