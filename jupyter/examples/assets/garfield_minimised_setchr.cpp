#include <string.h>
#include <string>

enum valueType {
  integer_t = 0x73746e69,
  double_t = 0x6c627564,
  string_t = 0x6e727473,
  list_t = 0x7473696c,
};

typedef struct string {
  char *s;
  int length;
} string;

class Value; // Forward decl
typedef struct list {
  Value **l;
  int max;
  int index;
} list;

class Value {
public:
  long long i;
  double d;
  string s;

  list lt;

  // std::vector< Value *> l;

  valueType t;

  ~Value() {}
  Value() {}
  Value(valueType t) : t(t) {
    if (t == list_t) {
      lt.l = NULL;
      lt.index = 0;
      lt.max = 0;
    }
  }
  Value(long long i) : i(i) { t = integer_t; }
  Value(double d) : d(d) { t = double_t; }
  Value(string *ns) {
    t = string_t;
    this->s.length = ns->length;
    this->s.s = new char[ns->length + 1];
    memset(this->s.s, 0, this->s.length + 1);
    memcpy(this->s.s, ns->s, ns->length);
  }
  Value(char *ns) {
    t = string_t;
    this->s.length = strlen(ns);
    this->s.s = ns;
  }
  Value(std::string s) {
    t = string_t;
    this->s.length = s.size();
    this->s.s = new char[s.size() + 1];
    memset(this->s.s, 0, s.size() + 1);
    memcpy(this->s.s, s.c_str(), s.size());
  }
  // Value( std::vector< Value *> l) { t = list_t; }
  Value(list *nl) {
    t = list_t;
    lt.l = (Value **)calloc(1, nl->max * sizeof(Value *));
    lt.max = nl->max;
    lt.index = nl->index;
    memcpy(lt.l, nl->l, nl->max * sizeof(Value *));
  }
};

// Off-by-one if loc == a->s.length
Value *setchr_builtin(Value *a, Value *b, int loc) {
  if (a->s.length <= loc) {
    return NULL;
    // throw GenericException( "location out of bounds");
  }

  if (b->s.length != 1) {
    return NULL;
    // throw GenericException( "invalid character argument");
  }

  a->s.s[loc] = b->s.s[0];

  return NULL;
}

int main(int argc, char **argv) {
  Value a("test_string");
  Value b("test_char");
  setchr_builtin(&a, &b, 2);
  return 0;
}