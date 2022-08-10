extern int df_sig_arg_to_arg_pts(int, int *) __attribute__((weak));

int main(int argc, char *argv[]) {
  int x;
  return df_sig_arg_to_arg_pts(argc, &x);
}
