/* Derived from chess-aces program with MIT license (reproduced below). See also
 * doc/legal.rst
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the “Software”), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

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
