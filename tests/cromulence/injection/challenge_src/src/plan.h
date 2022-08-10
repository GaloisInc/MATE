#pragma once

#include "lex.h"
#include "db.h"

typedef enum script_op {
                        PUSH_TRUE,
                        PUSH_IDENTIFIER,
                        PUSH_PARAMETER,
                        PUSH_LITERAL,
                        OR,
                        AND,
                        NOT,
                        EQ,
                        NEQ,
                        LT,
                        LTEQ,
                        GT,
                        GTEQ
} script_op;

typedef struct script {
  script_op operation;
  char* operand;
  struct script* next;
  struct script* prev;
} script;

typedef struct query_plan {
  char* table_name;
  table* table;
  int column_count;
  char** columns;
  int* column_indexes;
  script* script;
  struct query_plan* next;
} query_plan;

query_plan* create_query_plan(ast* query, database* db);
void dump_plan(FILE* out, query_plan* first);
void dump_script(FILE* out, script* first);

void destroy_plan(query_plan* plan);

bool column_in_plan(int table_column_index, query_plan* plan);
