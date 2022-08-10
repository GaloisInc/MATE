int f(int a, int b, int c, int d, int e, int f, int g, int h, int i, int j,
      int k, int l, int m, int n) {
  return (a + b) + (c * d) * (e - f) - (g / h) / (i % j) % (k && l) && (m || n);
}

int main(int argc, char *argv[] /* unused */) {
  return f(argc, argc, argc, argc, argc, argc, argc, argc, argc, argc, argc,
           argc, argc, argc);
}
