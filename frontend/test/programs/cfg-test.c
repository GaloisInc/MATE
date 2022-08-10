int global = 0;

int bar(int x) { return x; }

int foo(int x) {
  int a = bar(x); // foo1
  int b = bar(x);
  return a + b + global;
}

void baz() { global = 1; }

int main(int argc, char **argv) {
  int a = 0;
  int b = 1;

  int c = foo(a); // main1
  baz();
  int d = foo(b); // main2
  int e = bar(d); // main3

  return c + d + e;
}
