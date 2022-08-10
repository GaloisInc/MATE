typedef struct {
  int u;
  int v;
} pt;

extern int df_sig_arg_to_arg_pts_agg(int, pt *, int *, int *)
    __attribute__((weak));

int main(int argc, char *argv[]) {
  pt x;
  // We need to pass &x.u and &x.v because otherwise those allocations won't
  // have any variables pointing to them, and so won't show up in the CPG.
  return df_sig_arg_to_arg_pts_agg(argc, &x, &x.u, &x.v);
}
