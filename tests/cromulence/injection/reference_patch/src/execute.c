#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "execute.h"
#include "kvlist.h"
#include "stack.h"

result* execute_plan_step(query_plan* plan, result* results, kvlist* params);

kvlist* row_to_kvlist(table* table, row* row);

int stkcmp(stack* stk);

result* execute_plan(query_plan* plan, kvlist* params) {
  result* blank_results = calloc(sizeof(result), 1);
  assert(blank_results);

  return execute_plan_step(plan, blank_results, params);
}

result* execute_plan_step(query_plan* plan, result* results, kvlist* params) {
  if (NULL == plan) return results;

  if (NULL == results->columns) {
    result_column* prev_col_header = NULL;
    for (int i = 0; i < plan->table->col_count; i++) {
      if (! column_in_plan(i, plan)) continue;

      result_column* cur_col_header = calloc(1, sizeof(result_column));
      if (NULL != prev_col_header) prev_col_header->next = cur_col_header;
      if (NULL == prev_col_header) results->columns = cur_col_header;

      cur_col_header->content = plan->table->cols[i].contents; 
      prev_col_header = cur_col_header;
    }
  }

  for (uint32_t r = 0; r < plan->table->row_count; r++) {
    row* row = plan->table->rows + r;

    kvlist* row_kv = row_to_kvlist(plan->table, row);

    script* cur = plan->script;

    stack* stk = stack_create();

    while (NULL != cur) {

      switch (cur->operation) {
      case PUSH_TRUE: {
        stack_push_bool(stk, true);
        break;
      }
      case PUSH_IDENTIFIER: {
        char* content = kvlist_get(row_kv, cur->operand);
        assert(content);
        stack_push_string(stk, content);
        break;
      }
      case PUSH_PARAMETER: {
        char* param = kvlist_get(params, cur->operand);
        assert(param);
        stack_push_string(stk, param);
        break;
      }
      case PUSH_LITERAL: {
        stack_push_string(stk, cur->operand);
        break;
      }
      case OR: {
        bool first = stack_pop_bool(stk);
        bool second = stack_pop_bool(stk);
        stack_push_bool(stk, (first || second));
        break;
      }
      case AND: {
        bool first = stack_pop_bool(stk);
        bool second = stack_pop_bool(stk);
        stack_push_bool(stk, (first && second));
        break;
      }
      case NOT: {
        bool first = stack_pop_bool(stk);
        stack_push_bool(stk, !first);
        break;
      }
      case EQ: {
        bool got = (0 == stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      case NEQ: {
        bool got = (0 != stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      case LT: {
        
        bool got = (0 > stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      case LTEQ: {
        bool got = (0 >= stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      case GT: {
        bool got = (0 < stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      case GTEQ: {
        bool got = (0 <= stkcmp(stk));
        stack_push_bool(stk, got);
        break;
      }
      }

      cur = cur->next;
    }

    bool include_row = stack_pop_bool(stk);
    if (include_row) {
      result_row* new_result_row = calloc(1, sizeof(result_row));
      new_result_row->next = results->rows;
      results->rows = new_result_row;
      result_column* prev = NULL;

      for (uint8_t c = 0; c < plan->table->col_count; c++) {
        if (! column_in_plan(c, plan)) {
          continue;
        }
        result_column* cur = calloc(1, sizeof(result_column));

        if (NULL == prev) new_result_row->first = cur;
        if (NULL != prev) prev->next = cur;

        cur->content = row->cols[c].contents; 
        prev = cur;
      }
    }
    stack_destroy(stk);
    kvlist_destroy(row_kv);
  }

  return execute_plan_step(plan->next, results, params);
}

kvlist* row_to_kvlist(table* table, row* row) {
  kvlist* list = NULL;
  for (uint8_t c = 0; c < table->col_count; c++) {
    list = kvlist_set(list,
                      table->cols[c].contents,
                      row->cols[c].contents);
  }

  return list;
}

int stkcmp(stack* stk) {
  stack_entry* first = stack_pop(stk);
  stack_entry* second = stack_pop(stk);
  int got = strcmp(first->string, second->string);
  free_stack_entry(first);
  free_stack_entry(second);
  return got;
}

void dump_results(FILE* out, result* results) {
  fprintf(out, "columns:\n");
  result_column* col = results->columns;
  while (NULL != col) {
    fprintf(out, "\t%s\n", col->content);
    col = col->next;
  }

  fprintf(out, "rows:\n");
  result_row* r = results->rows;
  while(NULL != r) {
    fprintf(out, "\t");
    col = r->first;
    while (NULL != col) {
      fprintf(out, "%s\t", col->content);
      col = col->next;
    }
    r = r->next;
    fprintf(out, "\n");
  }
}

void destroy_result_cols(result_column* cur_col) {
  if (NULL == cur_col) return;

  result_column* next_col = cur_col->next;
  free(cur_col);
  destroy_result_cols(next_col);
}

void destroy_result_rows(result_row* cur_row) {
  if (NULL == cur_row) return;

  result_row* next_row = cur_row->next;

  destroy_result_cols(cur_row->first);
  destroy_result_rows(next_row);
}

void destroy_results(result* results) {
  destroy_result_cols(results->columns);
  destroy_result_rows(results->rows);
  free(results);
}
