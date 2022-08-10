#include <stdlib.h>

struct obj {
  int field1;
  int field2;
};

struct obj global_obj;

struct obj *id(struct obj *x) {
  return x;
}

struct obj *fun1() {
  return id(new struct obj);
}

struct obj *fun2() {
  return id(new struct obj);
}

struct obj *fun3() {
  return id(&global_obj);
}

struct obj *fun4() {
  return id(&global_obj);
}

int main() {
  struct obj *a = fun1();
  struct obj *b = fun2();
  struct obj *c = fun3();
  struct obj *d = fun4();
  return a->field1 + b->field1 + c->field1 + d->field1;
}
