void h(int **px, int *x) { *px = x; }

void f(int **px, int *x) { h(px, x); }

void g(int **px, int *x) { h(px, x); }

int main() {
  int *pa, a = 0;
  int *pb, b = 0;
  f(&pa, &a);
  g(&pb, &b);
  return *pa + *pb;
}
