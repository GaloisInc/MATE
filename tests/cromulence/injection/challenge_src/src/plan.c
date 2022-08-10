#include <assert.h>
#include <stdlib.h>
#include <string.h>

#include "db.h"
#include "lex.h"
#include "log.h"
#include "plan.h"
#include "query_parser.h"

query_plan* create_query_term_plan(query_term* qt, database* db);
void set_columns(query_term* term, query_plan* plan);
void build_script(query_term* term, query_plan* plan);
int find_column_index(table* table, char* column_name);

typedef struct traverse_state {
  script* first;
  script* last;
} traverse_state;

traverse_state traverse_script(ast* where);

query_plan* create_query_plan(ast* query, database* db) {
  if (NULL == query) return NULL;
  query_plan* plan = create_query_term_plan((query_term*)(void*)query->l, db);
  plan->next = create_query_plan(query->r, db);

  if (NULL != plan->next) {
    assert(plan->column_count == plan->next->column_count);
  }

  return plan;
}

query_plan* create_query_term_plan(query_term* qt, database* db) {
  query_plan* plan = calloc(sizeof(query_plan), 1);
  plan->table_name = qt->from;
  plan->table = db_get_table(plan->table_name, db);
  set_columns(qt, plan);
  build_script(qt, plan);
  return plan;
}

void set_columns(query_term* term, query_plan* plan) {
  ast* select_list = term->select;
  table* table = plan->table;

  assert(table);

  if (ASTERISK_SELECT == (ast_nodetype)(select_list->nodetype)) {
    plan->column_count = table->col_count;
    plan->columns = calloc(sizeof(char*), table->col_count);
    assert(plan->columns);
    plan->column_indexes = calloc(sizeof(int), table->col_count);
    assert(plan->column_indexes);

    for (uint8_t c = 0; c < table->col_count; c++) {
      plan->columns[c] = strdup(table->cols[c].contents);
      plan->column_indexes[c] = c;
    }
    return;
  }

  plan->column_count = 0;
  ast* cur_sublist = select_list;
  do {
    assert(SELECT_SUBLIST == (ast_nodetype)(cur_sublist->nodetype));
    plan->column_count++;

    cur_sublist = cur_sublist->r;
  } while (NULL != cur_sublist);

  plan->columns = calloc(sizeof(char*), plan->column_count);
  plan->column_indexes = calloc(sizeof(int), table->col_count);

  cur_sublist = select_list;
  for (uint8_t c = 0; c < plan->column_count; c++) {
    assert(SELECT_SUBLIST == (ast_nodetype)(cur_sublist->nodetype));
    plan->columns[c] = strdup((char*)(void*)(cur_sublist->l));
    plan->column_indexes[c] = find_column_index(plan->table, plan->columns[c]);

    cur_sublist = cur_sublist->r;
  } while (NULL != cur_sublist);
}

int find_column_index(table* table, char* column_name) {
  for (uint8_t c = 0; c < table->col_count; c++) {
    if (0 == strcmp(column_name, table->cols[c].contents)) return c;
  }

  assert(false);
}

void build_script(query_term* term, query_plan* plan) {
  ast* where = term->where;
  if (NULL == where) {
    script* scr = calloc(sizeof(script), 1);
    scr->operation = PUSH_TRUE;
    plan->script = scr;
    return;
  }

  traverse_state t = traverse_script(where);
  plan->script = t.first;
}

traverse_state traverse_script_value(ast* where);
traverse_state traverse_script_binary(ast* where);
traverse_state traverse_script_unary(ast* where);

traverse_state traverse_script(ast* where) {
  if (NULL == where) return (traverse_state){NULL, NULL};

  lll("where %p (%c %p %p)",
      where, (char)where->nodetype,
      where->l, where->r);

  switch((ast_nodetype)where->nodetype) {
  case IDENTIFIER_NODE:
  case CHAR_LITERAL_NODE:
  case PARAMETER_NODE:
    lll(" %s\n", (char*)(void*)where->l);
    break;
  default:
    lll("\n");
  }

  switch((ast_nodetype)where->nodetype) {
  case IDENTIFIER_NODE:
  case CHAR_LITERAL_NODE:
  case PARAMETER_NODE:
    return traverse_script_value(where);
  case BOOLEAN_OR:
  case BOOLEAN_AND:
  case COMP_EQ:
  case COMP_NEQ:
  case COMP_LT:
  case COMP_LTEQ:
  case COMP_GT:
  case COMP_GTEQ:
    return traverse_script_binary(where);
  case BOOLEAN_NOT:
    return traverse_script_unary(where);
  default:
    assert(false);
  }
}

traverse_state traverse_script_value(ast* where) {
  script* cmd = calloc(sizeof(script), 1);

  switch((ast_nodetype)where->nodetype) {
  case IDENTIFIER_NODE:
    cmd->operation = PUSH_IDENTIFIER;
    break;
  case CHAR_LITERAL_NODE:
    cmd->operation = PUSH_LITERAL;
    break;
  case PARAMETER_NODE:
    cmd->operation = PUSH_PARAMETER;
    break;
  default:
    assert(false);
  }

  cmd->operand = (char*)where->l;

  return (traverse_state){cmd, cmd};
}

traverse_state traverse_script_binary(ast* where) {
  script* cmd = calloc(sizeof(script), 1);

  switch((ast_nodetype)where->nodetype) {
  case BOOLEAN_OR:
    cmd->operation = OR;
    break;
  case BOOLEAN_AND:
    cmd->operation = AND;
    break;
  case COMP_EQ:
    cmd->operation = EQ;
    break;
  case COMP_NEQ:
    cmd->operation = NEQ;
    break;
  case COMP_LT:
    cmd->operation = LT;
    break;
  case COMP_LTEQ:
    cmd->operation = LTEQ;
    break;
  case COMP_GT:
    cmd->operation = GT;
    break;
  case COMP_GTEQ:
    cmd->operation = GTEQ;
    break;
  default:
    assert(false);
  }


  traverse_state left_side = traverse_script(where->l);
  traverse_state right_side = traverse_script(where->r);

  traverse_state new_state;
  new_state.first = left_side.first;

  left_side.last->next = right_side.first;
  right_side.first->prev = left_side.last;

  right_side.last->next = cmd;
  cmd->prev = right_side.last;

  new_state.last = cmd;

  return new_state;
}

traverse_state traverse_script_unary(ast* where) {
  script* cmd = calloc(sizeof(script), 1);

  switch((ast_nodetype)where->nodetype) {
  case BOOLEAN_NOT:
    cmd->operation = NOT;
    break;
  default:
    assert(false);
  }

  traverse_state inside = traverse_script(where->l);

  traverse_state new_state;

  new_state.first = inside.first;

  inside.last->next = cmd;
  cmd->prev = inside.last;

  new_state.last = cmd;

  return new_state;
}

void dump_plan(FILE* out, query_plan* first) {
  if (NULL == first) return;

  fprintf(out, "plan %p\n", first);
  fprintf(out, "\ttable\t%s\n", first->table_name);
  fprintf(out, "\t%d columns:\n", first->column_count);
  for(int c = 0; c < first->column_count; c++) {
    fprintf(out, "\t\t%s\n", first->columns[c]);
  }
  fprintf(out, "\tscript:\n");
  dump_script(out, first->script);

  dump_plan(out, first->next);
}

void dump_script(FILE* out, script* first) {
  if (NULL == first) return;

  switch(first->operation) {
  case (PUSH_TRUE):
    fprintf(out, "PUSH_TRUE\n");
    break;
  case (PUSH_IDENTIFIER):
    fprintf(out, "PUSH_IDENTIFIER(%s)\n", first->operand);
    break;
  case (PUSH_PARAMETER):
    fprintf(out, "PUSH_PARAMETER(%s)\n", first->operand);
    break;
  case (PUSH_LITERAL):
    fprintf(out, "PUSH_LITERAL(%s)\n", first->operand);
    break;
  case (OR):
    fprintf(out, "OR\n");
    break;
  case (AND):
    fprintf(out, "AND\n");
    break;
  case (NOT):
    fprintf(out, "NOT\n");
    break;
  case (EQ):
    fprintf(out, "EQ\n");
    break;
  case (NEQ):
    fprintf(out, "NEQ\n");
    break;
  case (LT):
    fprintf(out, "LT\n");
    break;
  case (LTEQ):
    fprintf(out, "LTEQ\n");
    break;
  case (GT):
    fprintf(out, "GT\n");
    break;
  case (GTEQ):
    fprintf(out, "GTEQ\n");
    break;
  default:
    assert(false);
  }

  dump_script(out, first->next);
}

void destroy_script(script* scr) {
  if (NULL == scr) return;

  script* next = scr->next;
  free(scr);
  return destroy_script(next);
}

void destroy_plan(query_plan* plan) {
  if (NULL == plan) return;

  for (int c = 0; c < plan->column_count; c++) {
    free(plan->columns[c]);
  }

  free(plan->columns);
  free(plan->column_indexes);
  destroy_script(plan->script);
  query_plan* next_plan = plan->next;
  free(plan);
  return destroy_plan(next_plan);
}

bool column_in_plan(int table_column_index, query_plan* plan) {
  for (uint8_t plan_column_index = 0;
       plan_column_index < plan->column_count;
       plan_column_index++) {
    if (table_column_index == plan->column_indexes[plan_column_index]) {
      return true;
    }
  }

  return false;
}
