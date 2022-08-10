/* This is a regression case for MATE#1058.
 * Ref: https://gitlab-ext.galois.com/mate/MATE/-/issues/1058
 */

#include <fcntl.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#ifdef __cplusplus
#include <exception>
#include <functional>
#include <iostream>
#include <numeric>
#include <string>
#include <system_error>
#include <vector>
#endif

#define COINFLIP() (rand() % 2)

/* This is a minimization of a CPG-breaking case in the Ovington challenge.
 *
 * When compiled with `-O2`, LLVM inlines `checked_open`
 * into `checked_open_reading` and `checked_open_writing`. While doing so,
 * it does something slightly unusual: it preserves a single DILocalVariable
 * for `got_fd`, with the inlined sites containing `llvm::Use` references
 * for `got_fd`'s metadata node.
 *
 * This particular debug production confused ASTGraphWriter, which assumed
 * that (1) all `llvm::Use` values were already emitted as nodes, and
 * (2) that `MetadataAsValue` weren't among the uses. Consequently, each
 * DILocalVariable was prematurely emitted by ASTGraphWriter as an
 * UnclassifiedNode rather than a LocalVariable node, which subsequently
 * caused CPG construction to fail with a foreign key constraint error upon
 * attempting to pair to a DWARFLocalVariable.
 */

int checked_open(std::string, int);

int checked_open_reading(std::string filename) {
  return checked_open(filename, O_RDONLY);
}

int checked_open_writing(std::string filename) {
  return checked_open(filename, O_WRONLY | O_CREAT | O_TRUNC);
}

int checked_open(std::string filename, int flags) {
  int got_fd = open(filename.c_str(), flags);
  if (got_fd < 0)
    throw std::system_error{};
  return got_fd;
}

int main(int argc, char const *argv[]) {
  auto fd = checked_open_writing("/tmp/issue_1058");
  write(fd, "hello", 5);
  close(fd);

  char buf[5];
  fd = checked_open_reading("/tmp/issue_1058");
  read(fd, buf, 5);

  return buf[0] == 'h';
}
