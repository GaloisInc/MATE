#pragma once

#include <stdio.h>

#include "lex.h"

typedef enum ast_nodetype {
                           QUERY_TERM = 't',
                           ASTERISK_SELECT = '*',
                           SELECT_SUBLIST = 's',

                           IDENTIFIER_NODE = 'i',
                           CHAR_LITERAL_NODE = 'l',
                           PARAMETER_NODE = 'p',

                           BOOLEAN_OR = '|',
                           BOOLEAN_AND = '&',
                           BOOLEAN_NOT = '!',

                           COMP_EQ = '=',
                           COMP_NEQ = '\\',
                           COMP_LT = '<',
                           COMP_LTEQ = ',',
                           COMP_GT = '>',
                           COMP_GTEQ = '.'
} ast_nodetype;

ast* parse_query(char* query);
