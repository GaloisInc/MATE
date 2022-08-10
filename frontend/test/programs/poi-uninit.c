/* Test program for uninitialized stack memory usage POI */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/timex.h>
#include <unistd.h>

void compare_num_read() {
  char c;
  int n;
  int tp_maybe;

  printf("Enter a digit:\n");
  read(0, &c, 1);
  n = c - '0';

  if (n < 5) {
    tp_maybe = 8;
  } else if (n > 5) {
    tp_maybe = 7;
  }

  if (tp_maybe - 7) { /* true positive use of tp_maybe */
    printf("n is less than 5\n");
  } else {
    printf("n is not less than 5\n");
  }
}

void use_string_fns() {
  char xs[8];
  char ys[8];
  char tp_zs[8];

  memset(xs, 0, sizeof(xs));
  memset(xs, '.', sizeof(xs) / 2);
  printf("xs = '%s'\n", xs);

  memcpy(ys, xs, sizeof(ys));
  printf("ys = '%s'\n", ys);

  printf("tp_zs[2] = '%c'\n", tp_zs[2]); /* true positive */
}

struct hmm {
  char a;
  char b;
  char c;
};

void struct_mem_fns() {
  struct hmm tp_src;
  struct hmm tp_dst;
  /* these fields have not been initialized */
  printf("uninitialized tp_src.a = '%c'\n", tp_src.a); /* true positive */
  printf("uninitialized tp_dst.c = '%c'\n", tp_dst.c); /* true positive */

  /* uses signature for memset */
  memset(&tp_src, '~', sizeof(tp_src));
  printf("memset initialized tp_src.a = '%c'\n", tp_src.a);
  printf("memset initialized tp_src.c = '%c'\n", tp_src.c);

  /* uses signature for memcpy */
  memcpy(&tp_dst, &tp_src, sizeof(tp_src));
  printf("memcpy initialized tp_dst.a = '%c'\n", tp_dst.a);
  printf("memcpy initialized tp_dst.c = '%c'\n", tp_dst.c);
}

/* === Functions inspired by the 'adams' challenge problem === */

int adams_local_strlen(const char *src) {
  int i = 0;

  if (!src) {
    return 0;
  }

  while (src[i] != '\x00') {
    i++;
  }

  return i;
}

void response_str() {
  char response[32];
  memset(response, 0, 32);
  snprintf(response, 32, "variable initialised by memset\n");
  if (adams_local_strlen(response) == 0) {
    printf("response length is zero.\n");
  } else {
    printf("response length is nonzero.\n");
  }
}

int adams_write_wrapper(char *buffer, int length) {
  int result;

  if (buffer == NULL) {
    return 0;
  }

  if (length <= 0) {
    return 0;
  }

  /* use site of 'buffer' (and thus whatever it aliases) */
  result = write(STDOUT_FILENO, buffer, length);

  if (result < 0) {
    return 0;
  }

  return 1;
}

/* This code demonstrates a known false positive in our CPG-based POI finder
 *
 * Since variable tn_response may be used in adams_write_wrapper(), the
 * relevant part of the body of adams_write_wrapper() is marked as a
 * use site for tn_response.
 *
 * However, there is a code path in this function that invokes
 * adams_write_wrapper() without having first initialized tn_response. This
 * call is safe because tn_response isn't passed into that invocation, but
 * an analysis that doesn't handle calls and returns carefully would give a
 * false positive here.
 *
 * Manticore validation should be able to determine that this is actually
 * a false positive. */
int adams_handle_EXPN_fp(int argc) {
  char tn_response[256];

  if (argc == 2) {
    /* Since tn_response hasn't yet been initialized by this point,
     * and because tn_response is passed to adams_write_wrapper in
     * elsewhere in this function, the following line could introduce
     * a false positive "use without initialization" on tn_response. */
    adams_write_wrapper("546 Not Authd\n", 14);
    return 1;
  } else {
    memset(tn_response, 0, 256); /* initialize tn_response */
    snprintf(tn_response, 256, "268 List not found\n");

    /* Here is where tn_response is used with adams_write_wrapper(),
     * which is safe since at this point it's been initialized via memset */
    adams_write_wrapper(tn_response, adams_local_strlen(tn_response));
    return 2;
  }
}

/* === end functions inspired by the 'adams' challenge problem === */

/*
 * In this function, there are two if-blocks that each initialize fp_msg. The
 * conditions for these if blocks overlap - that is, at least one of these
 * initializers will always execute, so fp_msg is always initialized at the
 * point it is used. However, our static analysis "find all possible
 * control-flow paths" logic does not do the kind of reasoning needed to
 * determine that there is no feasible input that results in neither if
 * condition holding. As a result, it "finds" a path that does not execute the
 * body of either if-block, and thus fp_msg looks like it might not be
 * initialized as the point that it is used at the printf.
 */
char overlapping() {
  char c;
  char fp_msg[8];

  printf("Enter a char:\n");
  read(0, &c, 1);

  /* fp_msg will be initialized by at least one of these memsets */
  if (c > 'a') {
    memset(fp_msg, 'a', sizeof(fp_msg));
  }
  if (c < 'z') {
    memset(fp_msg, 'b', sizeof(fp_msg));
  }

  return fp_msg[5]; /* use of fp_msg */
}

/* Note: Sys cannot find this bug */
char get4(char *buf) { return buf[4]; }

void indirect() {
  char tp_indir_buf[8];
  printf("c = '%c'\n", get4(tp_indir_buf));
}

struct threeint {
  int i;
  int ii;
  int iii;
};

char struct_fieldinit() {
  struct threeint tp_partialstruct;
  tp_partialstruct.ii = 42;

  return tp_partialstruct.i + tp_partialstruct.iii;
}

char struct_memset() {
  struct threeint tn_partialstruct;
  memset(&tn_partialstruct, 0, sizeof(struct threeint));

  return tn_partialstruct.ii;
}

/*
 * CVE-2018-11508 example
 *
 * First we stub out relevant kernel functionality for the example
 */

#define EFAULT 14 /* Bad address */

int fake_copy_from_user(void *to, unsigned long n) {
  /* fake, loads data from the user process */
  memset(to, 0, n);
  /* in the real kernel, catch and return -EFAULT on page fault, otherwise 0 */
  return 0;
}

int fake_copy_to_user(void *from, unsigned long n) {
  /* fake, leaks data to the user process */
  printf("%.*s", n, from);
  return 0;
}

int do_adjtimex(struct timex *txc) {
  /* fake, do nothing */
  return 0;
}

/* adapted from kernel/compat.c */
/* BUG: does not initialize txc->tai */
int compat_get_timex(struct timex *txc) {
  struct timex tx32;

  /* CVE-2018-11508 bugfix
   * fix 4-byte infoleak via uninitialized struct field
   * https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=0a0b98734479aa5b3c671d5190e86273372cab95
   *
   * Uncomment the following line to apply the fix that removes the bug.
   * When this fix has been applied, our static POI analysis no longer reports
   * use of uninitialized data in these functions.
   */
  /* memset(txc, 0, sizeof(struct timex)); */

  /* initialize (non-tai fields) from userspace */
  if (fake_copy_from_user(&tx32, sizeof(struct timex))) {
    /* this causes lots of false positives! returning here fails to initialize
     * *any* of the txc fields. Though returning here prevents them from being
     * read later, but our paths aren't smart enough to figure this out. */
    return -EFAULT;
  }

  txc->modes = tx32.modes;
  txc->offset = tx32.offset;
  txc->freq = tx32.freq;
  txc->maxerror = tx32.maxerror;
  txc->esterror = tx32.esterror;
  txc->status = tx32.status;
  txc->constant = tx32.constant;
  txc->precision = tx32.precision;
  txc->tolerance = tx32.tolerance;
  txc->time.tv_sec = tx32.time.tv_sec;
  txc->time.tv_usec = tx32.time.tv_usec;
  txc->tick = tx32.tick;
  txc->ppsfreq = tx32.ppsfreq;
  txc->jitter = tx32.jitter;
  txc->shift = tx32.shift;
  txc->stabil = tx32.stabil;
  txc->jitcnt = tx32.jitcnt;
  txc->calcnt = tx32.calcnt;
  txc->errcnt = tx32.errcnt;
  txc->stbcnt = tx32.stbcnt;

  return 0;
}

/* adapted from kernel/compat.c */
int compat_put_timex(const struct timex *txc) {
  struct timex tx32;

  memset(&tx32, 0, sizeof(struct timex));
  tx32.modes = txc->modes;
  tx32.offset = txc->offset;
  tx32.freq = txc->freq;
  tx32.maxerror = txc->maxerror;
  tx32.esterror = txc->esterror;
  tx32.status = txc->status;
  tx32.constant = txc->constant;
  tx32.precision = txc->precision;
  tx32.tolerance = txc->tolerance;
  tx32.time.tv_sec = txc->time.tv_sec;
  tx32.time.tv_usec = txc->time.tv_usec;
  tx32.tick = txc->tick;
  tx32.ppsfreq = txc->ppsfreq;
  tx32.jitter = txc->jitter;
  tx32.shift = txc->shift;
  tx32.stabil = txc->stabil;
  tx32.jitcnt = txc->jitcnt;
  tx32.calcnt = txc->calcnt;
  tx32.errcnt = txc->errcnt;
  tx32.stbcnt = txc->stbcnt;
  tx32.tai = txc->tai; /* BUG: copies uninitialized data 'tai' */

  if (fake_copy_to_user(&tx32, sizeof(struct timex)))
    return -EFAULT;

  return 0;
}

/*
 * Example based on CVE-2018-11508
 *
 * Summary:
 *   - stack variable 'struct timex txc' gets initialized in syscall_adjtimex
 *   - compat_get_timex initializes some fields of txc, but not tai
 *   - compat_put_timex copies the uninitialized tai field into
 *     the struct that gets used (sent back to "userspace")
 *
 * The True Positive Bug:
 *   - tai used without initialization (in compate_put_timex)
 *
 * False Positives:
 *   - if fake_copy_from_user fails in compate_get_timex, then
 *     none of the other fields in txc get initialized either
 *   - but if that happens, syscall_adjtimex returns before accessing them
 *   - our pathfinding doesn't do that kind of reasoning, so reports
 *     paths where fake_copy_from_user, no fields are initialized,
 *     and then they all get accessed later in compate_put_timex
 *     even though that is not feasible
 */

/* adapted from kernel/time/time.c */
int syscall_adjtimex() {
  struct timex txc; /* stack object */
  int err, ret;

  /* initializes some fields of txc, but not tai */
  err = compat_get_timex(&txc);
  if (err)
    return err; /* no fields of txc were initialized, return */

  ret = do_adjtimex(&txc);
  /* txc.tai has not been initialized by this point */

  /* next: access and leak the (uninitialized) 'tai' field */
  err = compat_put_timex(&txc);
  if (err)
    return err;

  return ret;
}

int main(int argc, char **argv) {
  compare_num_read();
  use_string_fns();
  struct_mem_fns();
  response_str();
  adams_handle_EXPN_fp(argc);
  overlapping();
  indirect();
  struct_fieldinit();
  syscall_adjtimex();
}
