#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "stack.h"


stack* stack_create() {
  stack* stack = calloc(sizeof(stack), 1);
  assert(stack);

  return stack;
}

void stack_push_string(stack* stack, char* string) {
  stack_entry* entry = calloc(sizeof(stack_entry), 1);
  entry->type = STRING;
  entry->string = strdup(string);
  assert(entry->string);
  entry->next = stack->top;
  stack->top = entry;
}

void stack_push_bool(stack* stack, bool b) {
  stack_entry* entry = calloc(sizeof(stack_entry), 1);
  entry->type = BOOL;
  entry->b = b;
  entry->next = stack->top;
  stack->top = entry;
}

stack_entry* stack_pop(stack* stack) {
  stack_entry* entry = stack->top;
  stack->top = entry->next;
  entry->next = NULL;
  return entry;
}

bool stack_pop_bool(stack* stack) {
  stack_entry* e = stack_pop(stack);
  bool got = e->b;
  free_stack_entry(e);
  return got;
}

void free_stack_entry(stack_entry* entry) {
  if (NULL == entry) return;

  if (NULL != entry->string) free(entry->string);

  stack_entry* next = entry->next;

  free(entry);

  if (NULL != next) free_stack_entry(next);
}

void stack_destroy(stack* stack) {
  free_stack_entry(stack->top);
  free(stack);
}
