 

 

 

#ifndef YY_YY_SRC_PARSE_TAB_H_INCLUDED
# define YY_YY_SRC_PARSE_TAB_H_INCLUDED
 
#ifndef YYDEBUG
# define YYDEBUG 0
#endif
#if YYDEBUG
extern int yydebug;
#endif

 
#ifndef YYTOKENTYPE
# define YYTOKENTYPE
  enum yytokentype
  {
    SELECT = 258,
    FROM = 259,
    WHERE = 260,
    UNION = 261,
    LPAREN = 262,
    RPAREN = 263,
    PLUS = 264,
    MINUS = 265,
    ASTERISK = 266,
    SOLIDUS = 267,
    EQ = 268,
    NEQ = 269,
    LT = 270,
    LTEQ = 271,
    GT = 272,
    GTEQ = 273,
    NOT = 274,
    OR = 275,
    AND = 276,
    CHARACTER_LITERAL = 277,
    IDENTIFIER = 278,
    PARAMETER = 279,
    COMMA = 280,
    SEMICOLON = 281
  };
#endif

 
#if ! defined YYSTYPE && ! defined YYSTYPE_IS_DECLARED

union YYSTYPE
{
#line 14 "priv/parse.y"  

    int intval;
    char* str;
    ast* a;
    query_term* qt;

#line 88 "src/parse.tab.h"  
};

typedef union YYSTYPE YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define YYSTYPE_IS_DECLARED 1
#endif


extern YYSTYPE yylval;

int yyparse (void);

#endif  
