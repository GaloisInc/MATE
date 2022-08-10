#pragma once

#include <stdbool.h>

typedef struct stack_entry {
  enum {
        STRING,
        BOOL
  } type;
  char* string;
  bool b;
  struct stack_entry* next;

} stack_entry;

typedef struct stack {
  stack_entry* top;
} stack;

stack* stack_create();

void stack_push_string(stack* stack, char* string);
void stack_push_bool(stack* stack, bool b);

stack_entry* stack_pop(stack* stack);
bool stack_pop_bool(stack* stack);

void free_stack_entry(stack_entry* entry);
void stack_destroy(stack* stack);
