// Test that signature handling code handles definitions of functions with
// declarations that don't match the standards they're supposed to conform to.
long strtol(const char *restrict nptr, int base) {
  return (long)base + (long)(nptr != 0);
}

int main(int argc, char **argv) {
  if (argc > 0) {
    return strtol(argv[0], 10);
  }
  return 0;
}
