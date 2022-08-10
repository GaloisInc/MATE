#pragma once

typedef struct kvlist {
  char* key;
  char* value;
  struct kvlist* next;
} kvlist;

kvlist* kvlist_set(kvlist* list, char* key, char* value);
char* kvlist_get(kvlist* list, char* key);

void kvlist_destroy(kvlist* list);
