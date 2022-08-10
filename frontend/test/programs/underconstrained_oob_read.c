#include <inttypes.h>
#include <stdint.h>

struct data {
  unsigned int val;
  char array[10];
  struct data *next;
};

int func(struct data *d) {
  return d->array[d->next->val]; // OOB read
}

int main(int argc, char const *argv[]) {
  struct data foo = {};
  return func(&foo);
}