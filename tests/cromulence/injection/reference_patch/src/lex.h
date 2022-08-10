#pragma once

#include <stdbool.h>

typedef struct ast {
  int nodetype;
  struct ast *l;
  struct ast *r;
} ast;

ast* ast_create(int nt, ast* l, ast* r);

typedef struct query_term {
  ast* select;
  char* from;
  ast* where;
} query_term;

query_term* qt_create(ast* select_list, query_term* table_expression);
query_term* te_create(char* from, ast* where_clause);

void yyerror (char const *msg);
int yylex();


ast* parsed_query;

ast* parse(char* query);
