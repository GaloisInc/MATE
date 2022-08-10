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

typedef struct list list_t;
typedef struct list {
  void *data;
  list_t *next;
} list_t;

int main(int argc, char const *argv[]) {
  int a = 1, b = 2, c = 3;
  list_t head, next, tail;

  if (!COINFLIP()) {
    head.data = &a;
    head.next = &next;
    next.data = &b;
    next.next = &tail;
    tail.data = &c;
    tail.next = NULL;
  } else {
    head.data = &c;
    head.next = &next;
    next.data = &b;
    next.next = &tail;
    tail.data = &a;
    tail.next = NULL;
  }

  list_t *iter = &head;
  while (iter != NULL) {
    printf("%d\n", *(int *)iter->data);
    iter = iter->next;
  }

  return 0;
}
