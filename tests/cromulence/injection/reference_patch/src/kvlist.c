#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "kvlist.h"

kvlist* kvlist_set(kvlist* list, char* key, char* value) {
  kvlist* new_elem = calloc(sizeof(kvlist), 1);
  assert(new_elem);

  new_elem->key = strdup(key);
  new_elem->value = strdup(value);
  new_elem->next = list;

  return new_elem;
}

char* kvlist_get(kvlist* list, char* key) {
  if (NULL == list) return NULL;
  if (0 == strcmp(key, list->key)) return list->value;

  return kvlist_get(list->next, key);
}

void kvlist_destroy(kvlist* list) {
  if (NULL == list) return;
  kvlist* next = list->next;
  free(list->key);
  list->key = NULL;
  free(list->value);
  list->value = NULL;
  free(list);
  return kvlist_destroy(next);
}
