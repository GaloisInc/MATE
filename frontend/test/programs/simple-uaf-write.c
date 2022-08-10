#include <stdio.h>
#include <stdlib.h>

typedef struct list list_t;
typedef struct list {
  void *data;
  list_t *next;
} list_t;

int main(int argc, char const *argv[]) {
  int a = 1, b = 2, c = 3, d = 100;
  list_t *head = malloc(sizeof(list_t));

  head->data = &a;
  head->next = malloc(sizeof(list_t));

  head->next->data = &b;
  head->next->next = malloc(sizeof(list_t));

  head->next->next->data = &c;
  head->next->next->next = NULL;

  free(head->next->next);

  list_t *iter = head;
  while (iter != NULL) {
    iter->data = &d;
    iter = iter->next;
  }

  return 0;
}
