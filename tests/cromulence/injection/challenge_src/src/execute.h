#pragma once

#include "kvlist.h"
#include "plan.h"

typedef struct result_column {
  char* content;
  struct result_column* next;
} result_column;

typedef struct result_row {
  result_column* first;
  struct result_row* next;
} result_row;

typedef struct result {
  result_column* columns;
  result_row* rows;
} result;

result* execute_plan(query_plan* plan, kvlist* params);

void dump_results(FILE* out, result* results);

void destroy_results(result* results);
