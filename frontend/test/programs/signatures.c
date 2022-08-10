#include <stddef.h>

extern int *mate_return_alloc_test(void) __attribute__((weak));
extern int *mate_return_alloc_test_neg(void) __attribute__((weak));

void do_return_alloc_tests(void) {
  int *a = mate_return_alloc_test();
  int *b = mate_return_alloc_test();
  int *c = mate_return_alloc_test_neg();
  (void)a;
  (void)b;
  (void)c;
}

int *mate_return_alloc_override_test(void) { return NULL; }
__attribute__((noinline));
int *mate_return_alloc_override_test_neg(void) { return NULL; }
__attribute__((noinline));

void do_return_alloc_override_tests(void) __attribute__((optnone)) {
  int *a = mate_return_alloc_override_test();
  int *b = mate_return_alloc_override_test();
  int *c = mate_return_alloc_override_test_neg();
  (void)a;
  (void)b;
  (void)c;
}

extern int *mate_return_alloc_once_test(void) __attribute__((weak));
extern int *mate_return_alloc_once_test_neg(void) __attribute__((weak));

void do_return_alloc_once_tests(void) {
  int *a = mate_return_alloc_once_test();
  int *b = mate_return_alloc_once_test();
  int *c = mate_return_alloc_once_test_neg();
  (void)a;
  (void)b;
  (void)c;
}

extern int *mate_return_aliases_arg_test(int, int *, int *)
    __attribute__((weak));
extern int *mate_return_aliases_arg_test_neg(int, int *, int *)
    __attribute__((weak));

void do_return_aliases_arg_tests(void) {
  int arg;
  int negarg;
  int *a = mate_return_aliases_arg_test(0, &arg, &negarg);
  int *b = mate_return_aliases_arg_test_neg(0, &arg, &negarg);
  (void)a;
  (void)b;
}

struct s {
  int *internal;
  struct s *next;
};

extern int *mate_return_aliases_arg_reachable_test(int, int *, struct s *)
    __attribute__((weak));
extern int *mate_return_aliases_arg_reachable_test_neg(int, int *, struct s *)
    __attribute__((weak));

void do_return_aliases_arg_reachable_tests(void) {
  int one, two, three, four, neg;
  struct s first = {.internal = &one, .next = NULL};
  struct s second = {.internal = &two, .next = &first};
  struct s third = {.internal = &three, .next = &second};
  struct s fourth = {.internal = &four, .next = &third};
  int *a = mate_return_aliases_arg_reachable_test(0, &neg, &fourth);
  int *b = mate_return_aliases_arg_reachable_test_neg(0, &neg, &fourth);
  (void)a;
  (void)b;
}

int global_int;
struct s global_struct = {.internal = &global_int};
struct s *global_ptr = &global_struct;

extern int *mate_return_points_to_global_test() __attribute__((weak));
extern int *mate_return_points_to_global_test_neg() __attribute__((weak));

void do_return_points_to_global_tests(void) {
  int *a = mate_return_points_to_global_test();
  int *b = mate_return_points_to_global_test_neg();
  (void)a;
  (void)b;
}

extern struct s *mate_return_aliases_global_test() __attribute__((weak));
extern struct s *mate_return_aliases_global_test_neg() __attribute__((weak));

void do_return_aliases_global_tests(void) {
  struct s *a = mate_return_aliases_global_test();
  struct s *b = mate_return_aliases_global_test_neg();
  (void)a;
  (void)b;
}

extern int *mate_return_aliases_global_reachable_test() __attribute__((weak));
extern int *mate_return_aliases_global_reachable_test_neg()
    __attribute__((weak));

void do_return_aliases_global_reachable_tests(void) {
  int *a = mate_return_aliases_global_reachable_test();
  int *b = mate_return_aliases_global_reachable_test_neg();
  (void)a;
  (void)b;
}

extern void *mate_arg_alloc_test(int **) __attribute__((weak));
extern void *mate_arg_alloc_test_neg(int **) __attribute__((weak));

void do_arg_alloc_tests(void) {
  int *a;
  int *b;
  int *c;
  mate_arg_alloc_test(&a);
  mate_arg_alloc_test(&b);
  mate_arg_alloc_test_neg(&c);
}

extern void *mate_arg_alloc_once_test(int **) __attribute__((weak));
extern void *mate_arg_alloc_once_test_neg(int **) __attribute__((weak));

void do_arg_alloc_once_tests(void) {
  int *a;
  int *b;
  int *c;
  mate_arg_alloc_once_test(&a);
  mate_arg_alloc_once_test(&b);
  mate_arg_alloc_once_test_neg(&c);
}

extern void mate_arg_memcpy_arg_test(int **a, int **b) __attribute__((weak));
extern void mate_arg_memcpy_arg_test_neg(int **a, int **b)
    __attribute__((weak));

void do_arg_memcpy_arg_tests(void) {
  int a = 0;
  int b = 1;
  int c = 2;
  int d = 3;
  int *ap = &a;
  int *bp = &b;
  int *cp = &c;
  int *dp = &d;

  mate_arg_memcpy_arg_test(&ap, &bp);
  mate_arg_memcpy_arg_test_neg(&cp, &dp);
}

extern void mate_arg_memcpy_arg_reachable_test(int **a, struct s **b)
    __attribute__((weak));
extern void mate_arg_memcpy_arg_reachable_test_neg(int **a, struct s **b)
    __attribute__((weak));

void do_arg_memcpy_arg_reachable_tests() {
  int a = 0;
  int b = 1;
  struct s sb = {.internal = &b};
  int c = 2;
  int d = 3;
  struct s sd = {.internal = &d};
  int *ap = &a;
  int *cp = &c;
  struct s *sbp = &sb;
  struct s *sdp = &sd;

  mate_arg_memcpy_arg_reachable_test(&ap, &sbp);
  mate_arg_memcpy_arg_reachable_test_neg(&cp, &sdp);
}

extern void mate_arg_points_to_global_test(int **) __attribute__((weak));
extern void mate_arg_points_to_global_test_neg(int **) __attribute__((weak));

void do_arg_points_to_global_tests() {
  int a = 0;
  int b = 0;
  int *ap = &a;
  int *bp = &b;
  mate_arg_points_to_global_test(&ap);
  mate_arg_points_to_global_test_neg(&bp);
}

extern void mate_arg_memcpy_global_test(struct s *) __attribute__((weak));
extern void mate_arg_memcpy_global_test_neg(struct s *) __attribute__((weak));

void do_arg_memcpy_global_tests() {
  struct s as;
  struct s bs;
  mate_arg_memcpy_global_test(&as);
  mate_arg_memcpy_global_test_neg(&bs);
}

extern void mate_arg_memcpy_global_reachable_test(int **a)
    __attribute__((weak));
extern void mate_arg_memcpy_global_reachable_test_neg(int **a)
    __attribute__((weak));

void do_arg_memcpy_global_reachable_tests() {
  int a = 0;
  int b = 1;
  int *ap = &a;
  int *bp = &b;
  mate_arg_memcpy_global_reachable_test(&ap);
  mate_arg_memcpy_global_reachable_test_neg(&bp);
}

int main(int argc, char **argv) {
  do_return_alloc_tests();
  do_return_alloc_override_tests();
  do_return_alloc_once_tests();
  do_return_aliases_arg_tests();
  do_return_aliases_arg_reachable_tests();
  do_return_points_to_global_tests();
  do_return_aliases_global_tests();
  do_return_aliases_global_reachable_tests();
  do_arg_alloc_tests();
  do_arg_alloc_once_tests();
  do_arg_memcpy_arg_tests();
  do_arg_memcpy_arg_reachable_tests();
  do_arg_points_to_global_tests();
  do_arg_memcpy_global_tests();
  do_arg_memcpy_global_reachable_tests();
}
