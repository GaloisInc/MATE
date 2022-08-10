#include <assert.h>
#include <stdio.h>
#include <string.h>

#include "lex.h"
#include "log.h"
#include "plan.h"
#include "query_parser.h"

void dump_ast(FILE* out, ast* ast);

ast* parse_query(char* query) {
  ast* got = parse(query);
  assert(got);
  assert((ast_nodetype)(got->nodetype) == QUERY_TERM);

  return got;
}

void dump_ast(FILE* out, ast* ast) {
    fprintf(out, "ast(%c, %p, %p) = %p\n",
            (char)ast->nodetype, ast->l, ast->r, ast);
}
