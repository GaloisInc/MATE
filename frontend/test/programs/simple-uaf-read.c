#include <stdio.h>
#include <stdlib.h>

typedef struct list list_t;
typedef struct list {
  void *data;
  list_t *next;
} list_t;

int main(int argc, char const *argv[]) {
  int a = 1, b = 2, c = 3;
  list_t *head = malloc(sizeof(list_t));

  head->data = &c;
  head->next = malloc(sizeof(list_t));
  head->next->data = &b;
  head->next->next = malloc(sizeof(list_t));
  head->next->next->data = &a;
  head->next->next->next = NULL;
  free(head->next);

  list_t *iter = head;
  while (iter != NULL) {
    printf("%d\n", *(int *)iter->data);
    iter = iter->next;
  }

  return 0;
}
