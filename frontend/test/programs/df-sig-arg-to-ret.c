extern int df_sig_arg_to_ret(int) __attribute__((weak));

int main(int argc, char *argv[]) { return df_sig_arg_to_ret(argc); }
