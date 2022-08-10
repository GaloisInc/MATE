 

 

 

 

 

 
#define YYBISON 1

 
#define YYBISON_VERSION "3.0.4"

 
#define YYSKELETON_NAME "yacc.c"

 
#define YYPURE 0

 
#define YYPUSH 0

 
#define YYPULL 1




 
#line 1 "priv/parse.y"  

#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

#include "lex.h"
#include "log.h"

#define YYPARSE_PARAM scanner
#define YYLEX_PARAM   scanner

#line 78 "src/parse.tab.c"  

# ifndef YY_NULLPTR
#  if defined __cplusplus && 201103L <= __cplusplus
#   define YY_NULLPTR nullptr
#  else
#   define YY_NULLPTR 0
#  endif
# endif

 
#ifdef YYERROR_VERBOSE
# undef YYERROR_VERBOSE
# define YYERROR_VERBOSE 1
#else
# define YYERROR_VERBOSE 0
#endif

 
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

#line 152 "src/parse.tab.c"  
};

typedef union YYSTYPE YYSTYPE;
# define YYSTYPE_IS_TRIVIAL 1
# define YYSTYPE_IS_DECLARED 1
#endif


extern YYSTYPE yylval;

int yyparse (void);

#endif  

 

#line 169 "src/parse.tab.c"  

#ifdef short
# undef short
#endif

#ifdef YYTYPE_UINT8
typedef YYTYPE_UINT8 yytype_uint8;
#else
typedef unsigned char yytype_uint8;
#endif

#ifdef YYTYPE_INT8
typedef YYTYPE_INT8 yytype_int8;
#else
typedef signed char yytype_int8;
#endif

#ifdef YYTYPE_UINT16
typedef YYTYPE_UINT16 yytype_uint16;
#else
typedef unsigned short int yytype_uint16;
#endif

#ifdef YYTYPE_INT16
typedef YYTYPE_INT16 yytype_int16;
#else
typedef short int yytype_int16;
#endif

#ifndef YYSIZE_T
# ifdef __SIZE_TYPE__
#  define YYSIZE_T __SIZE_TYPE__
# elif defined size_t
#  define YYSIZE_T size_t
# elif ! defined YYSIZE_T
#  include <stddef.h>  
#  define YYSIZE_T size_t
# else
#  define YYSIZE_T unsigned int
# endif
#endif

#define YYSIZE_MAXIMUM ((YYSIZE_T) -1)

#ifndef YY_
# if defined YYENABLE_NLS && YYENABLE_NLS
#  if ENABLE_NLS
#   include <libintl.h>  
#   define YY_(Msgid) dgettext ("bison-runtime", Msgid)
#  endif
# endif
# ifndef YY_
#  define YY_(Msgid) Msgid
# endif
#endif

#ifndef YY_ATTRIBUTE
# if (defined __GNUC__                                               \
      && (2 < __GNUC__ || (__GNUC__ == 2 && 96 <= __GNUC_MINOR__)))  \
     || defined __SUNPRO_C && 0x5110 <= __SUNPRO_C
#  define YY_ATTRIBUTE(Spec) __attribute__(Spec)
# else
#  define YY_ATTRIBUTE(Spec)  
# endif
#endif

#ifndef YY_ATTRIBUTE_PURE
# define YY_ATTRIBUTE_PURE   YY_ATTRIBUTE ((__pure__))
#endif

#ifndef YY_ATTRIBUTE_UNUSED
# define YY_ATTRIBUTE_UNUSED YY_ATTRIBUTE ((__unused__))
#endif

#if !defined _Noreturn \
     && (!defined __STDC_VERSION__ || __STDC_VERSION__ < 201112)
# if defined _MSC_VER && 1200 <= _MSC_VER
#  define _Noreturn __declspec (noreturn)
# else
#  define _Noreturn YY_ATTRIBUTE ((__noreturn__))
# endif
#endif

 
#if ! defined lint || defined __GNUC__
# define YYUSE(E) ((void) (E))
#else
# define YYUSE(E)  
#endif

#if defined __GNUC__ && 407 <= __GNUC__ * 100 + __GNUC_MINOR__
 
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN \
    _Pragma ("GCC diagnostic push") \
    _Pragma ("GCC diagnostic ignored \"-Wuninitialized\"")\
    _Pragma ("GCC diagnostic ignored \"-Wmaybe-uninitialized\"")
# define YY_IGNORE_MAYBE_UNINITIALIZED_END \
    _Pragma ("GCC diagnostic pop")
#else
# define YY_INITIAL_VALUE(Value) Value
#endif
#ifndef YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
# define YY_IGNORE_MAYBE_UNINITIALIZED_END
#endif
#ifndef YY_INITIAL_VALUE
# define YY_INITIAL_VALUE(Value)  
#endif


#if ! defined yyoverflow || YYERROR_VERBOSE

 

# ifdef YYSTACK_USE_ALLOCA
#  if YYSTACK_USE_ALLOCA
#   ifdef __GNUC__
#    define YYSTACK_ALLOC __builtin_alloca
#   elif defined __BUILTIN_VA_ARG_INCR
#    include <alloca.h>  
#   elif defined _AIX
#    define YYSTACK_ALLOC __alloca
#   elif defined _MSC_VER
#    include <malloc.h>  
#    define alloca _alloca
#   else
#    define YYSTACK_ALLOC alloca
#    if ! defined _ALLOCA_H && ! defined EXIT_SUCCESS
#     include <stdlib.h>  
       
#     ifndef EXIT_SUCCESS
#      define EXIT_SUCCESS 0
#     endif
#    endif
#   endif
#  endif
# endif

# ifdef YYSTACK_ALLOC
    
#  define YYSTACK_FREE(Ptr) do {  ; } while (0)
#  ifndef YYSTACK_ALLOC_MAXIMUM
     
#   define YYSTACK_ALLOC_MAXIMUM 4032  
#  endif
# else
#  define YYSTACK_ALLOC YYMALLOC
#  define YYSTACK_FREE YYFREE
#  ifndef YYSTACK_ALLOC_MAXIMUM
#   define YYSTACK_ALLOC_MAXIMUM YYSIZE_MAXIMUM
#  endif
#  if (defined __cplusplus && ! defined EXIT_SUCCESS \
       && ! ((defined YYMALLOC || defined malloc) \
             && (defined YYFREE || defined free)))
#   include <stdlib.h>  
#   ifndef EXIT_SUCCESS
#    define EXIT_SUCCESS 0
#   endif
#  endif
#  ifndef YYMALLOC
#   define YYMALLOC malloc
#   if ! defined malloc && ! defined EXIT_SUCCESS
void *malloc (YYSIZE_T);  
#   endif
#  endif
#  ifndef YYFREE
#   define YYFREE free
#   if ! defined free && ! defined EXIT_SUCCESS
void free (void *);  
#   endif
#  endif
# endif
#endif  


#if (! defined yyoverflow \
     && (! defined __cplusplus \
         || (defined YYSTYPE_IS_TRIVIAL && YYSTYPE_IS_TRIVIAL)))

 
union yyalloc
{
  yytype_int16 yyss_alloc;
  YYSTYPE yyvs_alloc;
};

 
# define YYSTACK_GAP_MAXIMUM (sizeof (union yyalloc) - 1)

 
# define YYSTACK_BYTES(N) \
     ((N) * (sizeof (yytype_int16) + sizeof (YYSTYPE)) \
      + YYSTACK_GAP_MAXIMUM)

# define YYCOPY_NEEDED 1

 
# define YYSTACK_RELOCATE(Stack_alloc, Stack)                           \
    do                                                                  \
      {                                                                 \
        YYSIZE_T yynewbytes;                                            \
        YYCOPY (&yyptr->Stack_alloc, Stack, yysize);                    \
        Stack = &yyptr->Stack_alloc;                                    \
        yynewbytes = yystacksize * sizeof (*Stack) + YYSTACK_GAP_MAXIMUM; \
        yyptr += yynewbytes / sizeof (*yyptr);                          \
      }                                                                 \
    while (0)

#endif

#if defined YYCOPY_NEEDED && YYCOPY_NEEDED
 
# ifndef YYCOPY
#  if defined __GNUC__ && 1 < __GNUC__
#   define YYCOPY(Dst, Src, Count) \
      __builtin_memcpy (Dst, Src, (Count) * sizeof (*(Src)))
#  else
#   define YYCOPY(Dst, Src, Count)              \
      do                                        \
        {                                       \
          YYSIZE_T yyi;                         \
          for (yyi = 0; yyi < (Count); yyi++)   \
            (Dst)[yyi] = (Src)[yyi];            \
        }                                       \
      while (0)
#  endif
# endif
#endif  

 
#define YYFINAL  9
 
#define YYLAST   39

 
#define YYNTOKENS  27
 
#define YYNNTS  16
 
#define YYNRULES  32
 
#define YYNSTATES  47

 
#define YYUNDEFTOK  2
#define YYMAXUTOK   281

#define YYTRANSLATE(YYX)                                                \
  ((unsigned int) (YYX) <= YYMAXUTOK ? yytranslate[YYX] : YYUNDEFTOK)

 
static const yytype_uint8 yytranslate[] =
{
       0,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     2,     2,     2,     2,
       2,     2,     2,     2,     2,     2,     1,     2,     3,     4,
       5,     6,     7,     8,     9,    10,    11,    12,    13,    14,
      15,    16,    17,    18,    19,    20,    21,    22,    23,    24,
      25,    26
};

#if YYDEBUG
   
static const yytype_uint8 yyrline[] =
{
       0,    63,    63,    64,    68,    69,    73,    77,    78,    82,
      85,    91,    95,    99,   100,   104,   105,   111,   112,   118,
     119,   123,   124,   128,   132,   133,   134,   138,   139,   140,
     141,   142,   143
};
#endif

#if YYDEBUG || YYERROR_VERBOSE || 0
 
static const char *const yytname[] =
{
  "$end", "error", "$undefined", "SELECT", "FROM", "WHERE", "UNION",
  "LPAREN", "RPAREN", "PLUS", "MINUS", "ASTERISK", "SOLIDUS", "EQ", "NEQ",
  "LT", "LTEQ", "GT", "GTEQ", "NOT", "OR", "AND", "CHARACTER_LITERAL",
  "IDENTIFIER", "PARAMETER", "COMMA", "SEMICOLON", "$accept", "input",
  "query", "query_term", "select_list", "select_sublist",
  "table_expression", "from_clause", "where_clause", "boolean_expression",
  "boolean_term", "boolean_factor", "boolean_test", "comparison_predicate",
  "value", "comparison", YY_NULLPTR
};
#endif

# ifdef YYPRINT
 
static const yytype_uint16 yytoknum[] =
{
       0,   256,   257,   258,   259,   260,   261,   262,   263,   264,
     265,   266,   267,   268,   269,   270,   271,   272,   273,   274,
     275,   276,   277,   278,   279,   280,   281
};
# endif

#define YYPACT_NINF -11

#define yypact_value_is_default(Yystate) \
  (!!((Yystate) == (-11)))

#define YYTABLE_NINF -1

#define yytable_value_is_error(Yytable_value) \
  0

   
static const yytype_int8 yypact[] =
{
       7,   -10,    11,    -2,    19,   -11,     1,    23,   -11,   -11,
     -11,     7,     5,     6,   -11,    25,   -11,   -11,   -11,    -7,
     -11,    -7,    -4,   -11,   -11,   -11,    12,    10,   -11,   -11,
     -11,    -9,    -6,   -11,    -7,    -7,   -11,   -11,   -11,   -11,
     -11,   -11,    -1,   -11,    10,   -11,   -11
};

   
static const yytype_uint8 yydefact[] =
{
       0,     0,     0,     3,     4,     7,     9,     0,     8,     1,
       2,     0,     0,     0,     6,    13,     5,    10,    12,     0,
      11,     0,     0,    25,    24,    26,    14,    15,    17,    19,
      21,     0,     0,    20,     0,     0,    27,    28,    29,    30,
      31,    32,     0,    22,    16,    18,    23
};

   
static const yytype_int8 yypgoto[] =
{
     -11,   -11,    22,   -11,   -11,    24,   -11,   -11,   -11,    13,
       3,     0,    16,   -11,    -3,   -11
};

   
static const yytype_int8 yydefgoto[] =
{
      -1,     2,     3,     4,     7,     8,    14,    15,    20,    26,
      27,    28,    29,    30,    31,    42
};

   
static const yytype_uint8 yytable[] =
{
      21,     5,    43,    21,    36,    37,    38,    39,    40,    41,
       1,     9,    22,     6,    34,    23,    24,    25,    23,    24,
      25,    23,    24,    25,    10,    11,    12,    13,     6,    18,
      19,    35,    34,    16,    32,    45,    17,    44,    33,    46
};

static const yytype_uint8 yycheck[] =
{
       7,    11,     8,     7,    13,    14,    15,    16,    17,    18,
       3,     0,    19,    23,    20,    22,    23,    24,    22,    23,
      24,    22,    23,    24,    26,     6,    25,     4,    23,    23,
       5,    21,    20,    11,    21,    35,    12,    34,    22,    42
};

   
static const yytype_uint8 yystos[] =
{
       0,     3,    28,    29,    30,    11,    23,    31,    32,     0,
      26,     6,    25,     4,    33,    34,    29,    32,    23,     5,
      35,     7,    19,    22,    23,    24,    36,    37,    38,    39,
      40,    41,    36,    39,    20,    21,    13,    14,    15,    16,
      17,    18,    42,     8,    37,    38,    41
};

   
static const yytype_uint8 yyr1[] =
{
       0,    27,    28,    28,    29,    29,    30,    31,    31,    32,
      32,    33,    34,    35,    35,    36,    36,    37,    37,    38,
      38,    39,    39,    40,    41,    41,    41,    42,    42,    42,
      42,    42,    42
};

   
static const yytype_uint8 yyr2[] =
{
       0,     2,     2,     1,     1,     3,     3,     1,     1,     1,
       3,     2,     2,     0,     2,     1,     3,     1,     3,     1,
       2,     1,     3,     3,     1,     1,     1,     1,     1,     1,
       1,     1,     1
};


#define yyerrok         (yyerrstatus = 0)
#define yyclearin       (yychar = YYEMPTY)
#define YYEMPTY         (-2)
#define YYEOF           0

#define YYACCEPT        goto yyacceptlab
#define YYABORT         goto yyabortlab
#define YYERROR         goto yyerrorlab


#define YYRECOVERING()  (!!yyerrstatus)

#define YYBACKUP(Token, Value)                                  \
do                                                              \
  if (yychar == YYEMPTY)                                        \
    {                                                           \
      yychar = (Token);                                         \
      yylval = (Value);                                         \
      YYPOPSTACK (yylen);                                       \
      yystate = *yyssp;                                         \
      goto yybackup;                                            \
    }                                                           \
  else                                                          \
    {                                                           \
      yyerror (YY_("syntax error: cannot back up")); \
      YYERROR;                                                  \
    }                                                           \
while (0)

 
#define YYTERROR        1
#define YYERRCODE       256



 
#if YYDEBUG

# ifndef YYFPRINTF
#  include <stdio.h>  
#  define YYFPRINTF fprintf
# endif

# define YYDPRINTF(Args)                        \
do {                                            \
  if (yydebug)                                  \
    YYFPRINTF Args;                             \
} while (0)

 
#ifndef YY_LOCATION_PRINT
# define YY_LOCATION_PRINT(File, Loc) ((void) 0)
#endif


# define YY_SYMBOL_PRINT(Title, Type, Value, Location)                    \
do {                                                                      \
  if (yydebug)                                                            \
    {                                                                     \
      YYFPRINTF (stderr, "%s ", Title);                                   \
      yy_symbol_print (stderr,                                            \
                  Type, Value); \
      YYFPRINTF (stderr, "\n");                                           \
    }                                                                     \
} while (0)


 

static void
yy_symbol_value_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep)
{
  FILE *yyo = yyoutput;
  YYUSE (yyo);
  if (!yyvaluep)
    return;
# ifdef YYPRINT
  if (yytype < YYNTOKENS)
    YYPRINT (yyoutput, yytoknum[yytype], *yyvaluep);
# endif
  YYUSE (yytype);
}


 

static void
yy_symbol_print (FILE *yyoutput, int yytype, YYSTYPE const * const yyvaluep)
{
  YYFPRINTF (yyoutput, "%s %s (",
             yytype < YYNTOKENS ? "token" : "nterm", yytname[yytype]);

  yy_symbol_value_print (yyoutput, yytype, yyvaluep);
  YYFPRINTF (yyoutput, ")");
}

 

static void
yy_stack_print (yytype_int16 *yybottom, yytype_int16 *yytop)
{
  YYFPRINTF (stderr, "Stack now");
  for (; yybottom <= yytop; yybottom++)
    {
      int yybot = *yybottom;
      YYFPRINTF (stderr, " %d", yybot);
    }
  YYFPRINTF (stderr, "\n");
}

# define YY_STACK_PRINT(Bottom, Top)                            \
do {                                                            \
  if (yydebug)                                                  \
    yy_stack_print ((Bottom), (Top));                           \
} while (0)


 

static void
yy_reduce_print (yytype_int16 *yyssp, YYSTYPE *yyvsp, int yyrule)
{
  unsigned long int yylno = yyrline[yyrule];
  int yynrhs = yyr2[yyrule];
  int yyi;
  YYFPRINTF (stderr, "Reducing stack by rule %d (line %lu):\n",
             yyrule - 1, yylno);
   
  for (yyi = 0; yyi < yynrhs; yyi++)
    {
      YYFPRINTF (stderr, "   $%d = ", yyi + 1);
      yy_symbol_print (stderr,
                       yystos[yyssp[yyi + 1 - yynrhs]],
                       &(yyvsp[(yyi + 1) - (yynrhs)])
                                              );
      YYFPRINTF (stderr, "\n");
    }
}

# define YY_REDUCE_PRINT(Rule)          \
do {                                    \
  if (yydebug)                          \
    yy_reduce_print (yyssp, yyvsp, Rule); \
} while (0)

 
int yydebug;
#else  
# define YYDPRINTF(Args)
# define YY_SYMBOL_PRINT(Title, Type, Value, Location)
# define YY_STACK_PRINT(Bottom, Top)
# define YY_REDUCE_PRINT(Rule)
#endif  


 
#ifndef YYINITDEPTH
# define YYINITDEPTH 200
#endif

 

#ifndef YYMAXDEPTH
# define YYMAXDEPTH 10000
#endif


#if YYERROR_VERBOSE

# ifndef yystrlen
#  if defined __GLIBC__ && defined _STRING_H
#   define yystrlen strlen
#  else
 
static YYSIZE_T
yystrlen (const char *yystr)
{
  YYSIZE_T yylen;
  for (yylen = 0; yystr[yylen]; yylen++)
    continue;
  return yylen;
}
#  endif
# endif

# ifndef yystpcpy
#  if defined __GLIBC__ && defined _STRING_H && defined _GNU_SOURCE
#   define yystpcpy stpcpy
#  else
 
static char *
yystpcpy (char *yydest, const char *yysrc)
{
  char *yyd = yydest;
  const char *yys = yysrc;

  while ((*yyd++ = *yys++) != '\0')
    continue;

  return yyd - 1;
}
#  endif
# endif

# ifndef yytnamerr
 
static YYSIZE_T
yytnamerr (char *yyres, const char *yystr)
{
  if (*yystr == '"')
    {
      YYSIZE_T yyn = 0;
      char const *yyp = yystr;

      for (;;)
        switch (*++yyp)
          {
          case '\'':
          case ',':
            goto do_not_strip_quotes;

          case '\\':
            if (*++yyp != '\\')
              goto do_not_strip_quotes;
             
          default:
            if (yyres)
              yyres[yyn] = *yyp;
            yyn++;
            break;

          case '"':
            if (yyres)
              yyres[yyn] = '\0';
            return yyn;
          }
    do_not_strip_quotes: ;
    }

  if (! yyres)
    return yystrlen (yystr);

  return yystpcpy (yyres, yystr) - yyres;
}
# endif

 
static int
yysyntax_error (YYSIZE_T *yymsg_alloc, char **yymsg,
                yytype_int16 *yyssp, int yytoken)
{
  YYSIZE_T yysize0 = yytnamerr (YY_NULLPTR, yytname[yytoken]);
  YYSIZE_T yysize = yysize0;
  enum { YYERROR_VERBOSE_ARGS_MAXIMUM = 5 };
   
  const char *yyformat = YY_NULLPTR;
   
  char const *yyarg[YYERROR_VERBOSE_ARGS_MAXIMUM];
   
  int yycount = 0;

   
  if (yytoken != YYEMPTY)
    {
      int yyn = yypact[*yyssp];
      yyarg[yycount++] = yytname[yytoken];
      if (!yypact_value_is_default (yyn))
        {
           
          int yyxbegin = yyn < 0 ? -yyn : 0;
           
          int yychecklim = YYLAST - yyn + 1;
          int yyxend = yychecklim < YYNTOKENS ? yychecklim : YYNTOKENS;
          int yyx;

          for (yyx = yyxbegin; yyx < yyxend; ++yyx)
            if (yycheck[yyx + yyn] == yyx && yyx != YYTERROR
                && !yytable_value_is_error (yytable[yyx + yyn]))
              {
                if (yycount == YYERROR_VERBOSE_ARGS_MAXIMUM)
                  {
                    yycount = 1;
                    yysize = yysize0;
                    break;
                  }
                yyarg[yycount++] = yytname[yyx];
                {
                  YYSIZE_T yysize1 = yysize + yytnamerr (YY_NULLPTR, yytname[yyx]);
                  if (! (yysize <= yysize1
                         && yysize1 <= YYSTACK_ALLOC_MAXIMUM))
                    return 2;
                  yysize = yysize1;
                }
              }
        }
    }

  switch (yycount)
    {
# define YYCASE_(N, S)                      \
      case N:                               \
        yyformat = S;                       \
      break
      YYCASE_(0, YY_("syntax error"));
      YYCASE_(1, YY_("syntax error, unexpected %s"));
      YYCASE_(2, YY_("syntax error, unexpected %s, expecting %s"));
      YYCASE_(3, YY_("syntax error, unexpected %s, expecting %s or %s"));
      YYCASE_(4, YY_("syntax error, unexpected %s, expecting %s or %s or %s"));
      YYCASE_(5, YY_("syntax error, unexpected %s, expecting %s or %s or %s or %s"));
# undef YYCASE_
    }

  {
    YYSIZE_T yysize1 = yysize + yystrlen (yyformat);
    if (! (yysize <= yysize1 && yysize1 <= YYSTACK_ALLOC_MAXIMUM))
      return 2;
    yysize = yysize1;
  }

  if (*yymsg_alloc < yysize)
    {
      *yymsg_alloc = 2 * yysize;
      if (! (yysize <= *yymsg_alloc
             && *yymsg_alloc <= YYSTACK_ALLOC_MAXIMUM))
        *yymsg_alloc = YYSTACK_ALLOC_MAXIMUM;
      return 1;
    }

   
  {
    char *yyp = *yymsg;
    int yyi = 0;
    while ((*yyp = *yyformat) != '\0')
      if (*yyp == '%' && yyformat[1] == 's' && yyi < yycount)
        {
          yyp += yytnamerr (yyp, yyarg[yyi++]);
          yyformat += 2;
        }
      else
        {
          yyp++;
          yyformat++;
        }
  }
  return 0;
}
#endif  

 

static void
yydestruct (const char *yymsg, int yytype, YYSTYPE *yyvaluep)
{
  YYUSE (yyvaluep);
  if (!yymsg)
    yymsg = "Deleting";
  YY_SYMBOL_PRINT (yymsg, yytype, yyvaluep, yylocationp);

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  YYUSE (yytype);
  YY_IGNORE_MAYBE_UNINITIALIZED_END
}




 
int yychar;

 
YYSTYPE yylval;
 
int yynerrs;


 

int
yyparse (void)
{
    int yystate;
     
    int yyerrstatus;

     

     
    yytype_int16 yyssa[YYINITDEPTH];
    yytype_int16 *yyss;
    yytype_int16 *yyssp;

     
    YYSTYPE yyvsa[YYINITDEPTH];
    YYSTYPE *yyvs;
    YYSTYPE *yyvsp;

    YYSIZE_T yystacksize;

  int yyn;
  int yyresult;
   
  int yytoken = 0;
   
  YYSTYPE yyval;

#if YYERROR_VERBOSE
   
  char yymsgbuf[128];
  char *yymsg = yymsgbuf;
  YYSIZE_T yymsg_alloc = sizeof yymsgbuf;
#endif

#define YYPOPSTACK(N)   (yyvsp -= (N), yyssp -= (N))

   
  int yylen = 0;

  yyssp = yyss = yyssa;
  yyvsp = yyvs = yyvsa;
  yystacksize = YYINITDEPTH;

  YYDPRINTF ((stderr, "Starting parse\n"));

  yystate = 0;
  yyerrstatus = 0;
  yynerrs = 0;
  yychar = YYEMPTY;  
  goto yysetstate;

 
 yynewstate:
   
  yyssp++;

 yysetstate:
  *yyssp = yystate;

  if (yyss + yystacksize - 1 <= yyssp)
    {
       
      YYSIZE_T yysize = yyssp - yyss + 1;

#ifdef yyoverflow
      {
         
        YYSTYPE *yyvs1 = yyvs;
        yytype_int16 *yyss1 = yyss;

         
        yyoverflow (YY_("memory exhausted"),
                    &yyss1, yysize * sizeof (*yyssp),
                    &yyvs1, yysize * sizeof (*yyvsp),
                    &yystacksize);

        yyss = yyss1;
        yyvs = yyvs1;
      }
#else  
# ifndef YYSTACK_RELOCATE
      goto yyexhaustedlab;
# else
       
      if (YYMAXDEPTH <= yystacksize)
        goto yyexhaustedlab;
      yystacksize *= 2;
      if (YYMAXDEPTH < yystacksize)
        yystacksize = YYMAXDEPTH;

      {
        yytype_int16 *yyss1 = yyss;
        union yyalloc *yyptr =
          (union yyalloc *) YYSTACK_ALLOC (YYSTACK_BYTES (yystacksize));
        if (! yyptr)
          goto yyexhaustedlab;
        YYSTACK_RELOCATE (yyss_alloc, yyss);
        YYSTACK_RELOCATE (yyvs_alloc, yyvs);
#  undef YYSTACK_RELOCATE
        if (yyss1 != yyssa)
          YYSTACK_FREE (yyss1);
      }
# endif
#endif  

      yyssp = yyss + yysize - 1;
      yyvsp = yyvs + yysize - 1;

      YYDPRINTF ((stderr, "Stack size increased to %lu\n",
                  (unsigned long int) yystacksize));

      if (yyss + yystacksize - 1 <= yyssp)
        YYABORT;
    }

  YYDPRINTF ((stderr, "Entering state %d\n", yystate));

  if (yystate == YYFINAL)
    YYACCEPT;

  goto yybackup;

 
yybackup:

   

   
  yyn = yypact[yystate];
  if (yypact_value_is_default (yyn))
    goto yydefault;

   

   
  if (yychar == YYEMPTY)
    {
      YYDPRINTF ((stderr, "Reading a token: "));
      yychar = yylex ();
    }

  if (yychar <= YYEOF)
    {
      yychar = yytoken = YYEOF;
      YYDPRINTF ((stderr, "Now at end of input.\n"));
    }
  else
    {
      yytoken = YYTRANSLATE (yychar);
      YY_SYMBOL_PRINT ("Next token is", yytoken, &yylval, &yylloc);
    }

   
  yyn += yytoken;
  if (yyn < 0 || YYLAST < yyn || yycheck[yyn] != yytoken)
    goto yydefault;
  yyn = yytable[yyn];
  if (yyn <= 0)
    {
      if (yytable_value_is_error (yyn))
        goto yyerrlab;
      yyn = -yyn;
      goto yyreduce;
    }

   
  if (yyerrstatus)
    yyerrstatus--;

   
  YY_SYMBOL_PRINT ("Shifting", yytoken, &yylval, &yylloc);

   
  yychar = YYEMPTY;

  yystate = yyn;
  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END

  goto yynewstate;


 
yydefault:
  yyn = yydefact[yystate];
  if (yyn == 0)
    goto yyerrlab;
  goto yyreduce;


 
yyreduce:
   
  yylen = yyr2[yyn];

   
  yyval = yyvsp[1-yylen];


  YY_REDUCE_PRINT (yyn);
  switch (yyn)
    {
        case 2:
#line 63 "priv/parse.y"  
    { parsed_query = (yyvsp[-1].a); }
#line 1274 "src/parse.tab.c"  
    break;

  case 3:
#line 64 "priv/parse.y"  
    { parsed_query = (yyvsp[0].a); }
#line 1280 "src/parse.tab.c"  
    break;

  case 4:
#line 68 "priv/parse.y"  
    { (yyval.a) = ast_create('t', (ast*)(void*)(yyvsp[0].qt), NULL); }
#line 1286 "src/parse.tab.c"  
    break;

  case 5:
#line 69 "priv/parse.y"  
    { (yyval.a) = ast_create('t', (ast*)(void*)(yyvsp[-2].qt), (ast*)(void*)(yyvsp[0].a)); }
#line 1292 "src/parse.tab.c"  
    break;

  case 6:
#line 73 "priv/parse.y"  
    { (yyval.qt) = qt_create((yyvsp[-1].a), (yyvsp[0].qt)); }
#line 1298 "src/parse.tab.c"  
    break;

  case 7:
#line 77 "priv/parse.y"  
    { (yyval.a) = ast_create('*', NULL, NULL); }
#line 1304 "src/parse.tab.c"  
    break;

  case 8:
#line 78 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1310 "src/parse.tab.c"  
    break;

  case 9:
#line 82 "priv/parse.y"  
    {
                    (yyval.a) = ast_create('s', (ast*)(void*) (yyvsp[0].str), NULL);
                }
#line 1318 "src/parse.tab.c"  
    break;

  case 10:
#line 85 "priv/parse.y"  
    {
            (yyval.a) = ast_create('s', (ast*)(void*) (yyvsp[-2].str), (yyvsp[0].a));
                }
#line 1326 "src/parse.tab.c"  
    break;

  case 11:
#line 91 "priv/parse.y"  
    { (yyval.qt) = te_create((yyvsp[-1].str), (yyvsp[0].a)); }
#line 1332 "src/parse.tab.c"  
    break;

  case 12:
#line 95 "priv/parse.y"  
    { (yyval.str) = (yyvsp[0].str); }
#line 1338 "src/parse.tab.c"  
    break;

  case 13:
#line 99 "priv/parse.y"  
    { (yyval.a) = NULL; }
#line 1344 "src/parse.tab.c"  
    break;

  case 14:
#line 100 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1350 "src/parse.tab.c"  
    break;

  case 15:
#line 104 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1356 "src/parse.tab.c"  
    break;

  case 16:
#line 105 "priv/parse.y"  
    {
            (yyval.a) = ast_create('|', (yyvsp[-2].a), (yyvsp[0].a));
                }
#line 1364 "src/parse.tab.c"  
    break;

  case 17:
#line 111 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1370 "src/parse.tab.c"  
    break;

  case 18:
#line 112 "priv/parse.y"  
    {
            (yyval.a) = ast_create('&', (yyvsp[-2].a), (yyvsp[0].a));
                }
#line 1378 "src/parse.tab.c"  
    break;

  case 19:
#line 118 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1384 "src/parse.tab.c"  
    break;

  case 20:
#line 119 "priv/parse.y"  
    { (yyval.a) = ast_create('!', (yyvsp[0].a), NULL); }
#line 1390 "src/parse.tab.c"  
    break;

  case 21:
#line 123 "priv/parse.y"  
    { (yyval.a) = (yyvsp[0].a); }
#line 1396 "src/parse.tab.c"  
    break;

  case 22:
#line 124 "priv/parse.y"  
    { (yyval.a) = (yyvsp[-1].a); }
#line 1402 "src/parse.tab.c"  
    break;

  case 23:
#line 128 "priv/parse.y"  
    { (yyval.a) = ast_create((yyvsp[-1].intval), (yyvsp[-2].a), (yyvsp[0].a)); }
#line 1408 "src/parse.tab.c"  
    break;

  case 24:
#line 132 "priv/parse.y"  
    { (yyval.a) = ast_create('i', (ast*)(void*)(yyvsp[0].str), NULL);}
#line 1414 "src/parse.tab.c"  
    break;

  case 25:
#line 133 "priv/parse.y"  
    { (yyval.a) = ast_create('l', (ast*)(void*)(yyvsp[0].str), NULL); }
#line 1420 "src/parse.tab.c"  
    break;

  case 26:
#line 134 "priv/parse.y"  
    { (yyval.a) = ast_create('p', (ast*)(void*)(yyvsp[0].str), NULL); }
#line 1426 "src/parse.tab.c"  
    break;

  case 27:
#line 138 "priv/parse.y"  
    { (yyval.intval) = '='; }
#line 1432 "src/parse.tab.c"  
    break;

  case 28:
#line 139 "priv/parse.y"  
    { (yyval.intval) = '\\'; }
#line 1438 "src/parse.tab.c"  
    break;

  case 29:
#line 140 "priv/parse.y"  
    { (yyval.intval) = '<'; }
#line 1444 "src/parse.tab.c"  
    break;

  case 30:
#line 141 "priv/parse.y"  
    { (yyval.intval) = ','; }
#line 1450 "src/parse.tab.c"  
    break;

  case 31:
#line 142 "priv/parse.y"  
    { (yyval.intval) = '>'; }
#line 1456 "src/parse.tab.c"  
    break;

  case 32:
#line 143 "priv/parse.y"  
    { (yyval.intval) = '.'; }
#line 1462 "src/parse.tab.c"  
    break;


#line 1466 "src/parse.tab.c"  
      default: break;
    }
   
  YY_SYMBOL_PRINT ("-> $$ =", yyr1[yyn], &yyval, &yyloc);

  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);

  *++yyvsp = yyval;

   

  yyn = yyr1[yyn];

  yystate = yypgoto[yyn - YYNTOKENS] + *yyssp;
  if (0 <= yystate && yystate <= YYLAST && yycheck[yystate] == *yyssp)
    yystate = yytable[yystate];
  else
    yystate = yydefgoto[yyn - YYNTOKENS];

  goto yynewstate;


 
yyerrlab:
   
  yytoken = yychar == YYEMPTY ? YYEMPTY : YYTRANSLATE (yychar);

   
  if (!yyerrstatus)
    {
      ++yynerrs;
#if ! YYERROR_VERBOSE
      yyerror (YY_("syntax error"));
#else
# define YYSYNTAX_ERROR yysyntax_error (&yymsg_alloc, &yymsg, \
                                        yyssp, yytoken)
      {
        char const *yymsgp = YY_("syntax error");
        int yysyntax_error_status;
        yysyntax_error_status = YYSYNTAX_ERROR;
        if (yysyntax_error_status == 0)
          yymsgp = yymsg;
        else if (yysyntax_error_status == 1)
          {
            if (yymsg != yymsgbuf)
              YYSTACK_FREE (yymsg);
            yymsg = (char *) YYSTACK_ALLOC (yymsg_alloc);
            if (!yymsg)
              {
                yymsg = yymsgbuf;
                yymsg_alloc = sizeof yymsgbuf;
                yysyntax_error_status = 2;
              }
            else
              {
                yysyntax_error_status = YYSYNTAX_ERROR;
                yymsgp = yymsg;
              }
          }
        yyerror (yymsgp);
        if (yysyntax_error_status == 2)
          goto yyexhaustedlab;
      }
# undef YYSYNTAX_ERROR
#endif
    }



  if (yyerrstatus == 3)
    {
       

      if (yychar <= YYEOF)
        {
           
          if (yychar == YYEOF)
            YYABORT;
        }
      else
        {
          yydestruct ("Error: discarding",
                      yytoken, &yylval);
          yychar = YYEMPTY;
        }
    }

   
  goto yyerrlab1;


 
yyerrorlab:

   
  if (  0)
     goto yyerrorlab;

   
  YYPOPSTACK (yylen);
  yylen = 0;
  YY_STACK_PRINT (yyss, yyssp);
  yystate = *yyssp;
  goto yyerrlab1;


 
yyerrlab1:
  yyerrstatus = 3;       

  for (;;)
    {
      yyn = yypact[yystate];
      if (!yypact_value_is_default (yyn))
        {
          yyn += YYTERROR;
          if (0 <= yyn && yyn <= YYLAST && yycheck[yyn] == YYTERROR)
            {
              yyn = yytable[yyn];
              if (0 < yyn)
                break;
            }
        }

       
      if (yyssp == yyss)
        YYABORT;


      yydestruct ("Error: popping",
                  yystos[yystate], yyvsp);
      YYPOPSTACK (1);
      yystate = *yyssp;
      YY_STACK_PRINT (yyss, yyssp);
    }

  YY_IGNORE_MAYBE_UNINITIALIZED_BEGIN
  *++yyvsp = yylval;
  YY_IGNORE_MAYBE_UNINITIALIZED_END


   
  YY_SYMBOL_PRINT ("Shifting", yystos[yyn], yyvsp, yylsp);

  yystate = yyn;
  goto yynewstate;


 
yyacceptlab:
  yyresult = 0;
  goto yyreturn;

 
yyabortlab:
  yyresult = 1;
  goto yyreturn;

#if !defined yyoverflow || YYERROR_VERBOSE
 
yyexhaustedlab:
  yyerror (YY_("memory exhausted"));
  yyresult = 2;
   
#endif

yyreturn:
  if (yychar != YYEMPTY)
    {
       
      yytoken = YYTRANSLATE (yychar);
      yydestruct ("Cleanup: discarding lookahead",
                  yytoken, &yylval);
    }
   
  YYPOPSTACK (yylen);
  YY_STACK_PRINT (yyss, yyssp);
  while (yyssp != yyss)
    {
      yydestruct ("Cleanup: popping",
                  yystos[*yyssp], yyvsp);
      YYPOPSTACK (1);
    }
#ifndef yyoverflow
  if (yyss != yyssa)
    YYSTACK_FREE (yyss);
#endif
#if YYERROR_VERBOSE
  if (yymsg != yymsgbuf)
    YYSTACK_FREE (yymsg);
#endif
  return yyresult;
}
#line 147 "priv/parse.y"  



ast* ast_create(int nt, ast* l, ast* r) {
    ast* a = calloc(1, sizeof(ast));
    lll("ast(%c, %p, %p) = %p\n", (char)nt, l, r, a);
    a->nodetype = nt;
    a->l = l;
    a->r = r;

    return a;
}

query_term* qt_create(ast* select_list, query_term* table_expression) {
    table_expression->select = select_list;

    lll("query_term(select %p from %s where %p) = %p\n",
        select_list,
        table_expression->from,
        table_expression->where,
        table_expression);
    return table_expression;
}

query_term* te_create(char* from, ast* where_clause) {
    query_term* te = calloc(1, sizeof(query_term));
    te->from = from;
    te->where = where_clause;
    lll("query_term(from %s where %p) = %p\n", from, where_clause, te);
    return te;
}

void yyerror (char const *msg) {
    lll("error %s\n", msg);
    exit(-1);
}
