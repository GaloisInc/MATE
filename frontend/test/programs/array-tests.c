static int c;

int fun(int n) {
  c = n;
  int arr[n];
  int arr2[c];
  int arr3[1] = {0};
  int i;
  for (i = 0; i < n; i++) {
    arr[i] = n * 2;
    arr2[i] = arr[i] - 4;
    arr3[0] = arr3[0] + arr2[i];
  }
  return arr[n - 1] + arr2[n / 3] + arr3[0];
}

int main() { return fun(24); }
