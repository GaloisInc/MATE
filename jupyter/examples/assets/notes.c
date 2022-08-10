// A simple server that allows user(s) to create notes. When a note is written,
// the user is given a key. They can retrieve the note using this key. The key
// is completely random, so the likelihood that anyone could successfully guess
// a key and retrieve another user's notes is low, and is inversely related to
// the KEY_SIZE (defined below).
//
// Example use:
//
// $ clang -Wall -Werror -o notes -O1 -g notes.c
// $ ./notes
// Listening on port 8894
//
// In a separate terminal:
//
// $ nc localhost 8894
// notes> write very secret data
// <server will send back a long alphanumeric key here>
// notes> read <key that the server sent back>
// very secret data

// -----------------------------------------------------------------------------

#include <arpa/inet.h>
#include <assert.h>
#include <dirent.h>
#include <netinet/in.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/param.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

// See file-level comment.
#define KEY_SIZE 32

// The values here aren't important.
#define PORT 8894
#define BUF_SIZE 1024

// -----------------------------------------------------------------------------

static void oom(void) {
  fprintf(stderr, "Out of memory!\n");
  exit(EXIT_FAILURE);
}

static void *notes_malloc(size_t sz) {
  void *p = malloc(sz);
  if (p == NULL) {
    oom();
  }
  return p;
}

static void *notes_strdup(const char *s) {
  void *p = strdup(s);
  if (p == NULL) {
    oom();
  }
  return p;
}

// -----------------------------------------------------------------------------

typedef enum cmds {
  CMD_QUIT,
  CMD_READ,
  CMD_WRITE,
} cmds_t;

typedef struct cmd {
  cmds_t c;
  char *arg;
} cmd_t;

static cmd_t *new_cmd(cmds_t c, char *arg) {
  cmd_t *cmd = notes_malloc(sizeof(cmd_t));
  cmd->c = c;
  cmd->arg = arg;
  return cmd;
}

// Parse a request into a (caller-owned/freed) command. Returns null if parsing
// fails. Mutates but does not free its string argument.
static cmd_t *parse(char *req) {
  assert(req != NULL);
  char *arg = NULL;
  char *space = strchr(req, ' ');
  if (space != NULL) {
    space[0] = '\0';
    arg = space + 1;
  }
  cmd_t *cmd = new_cmd(CMD_QUIT, arg);
  if (strcmp(req, "quit") == 0) {
    cmd->c = CMD_QUIT;
  } else if (strcmp(req, "read") == 0) {
    cmd->c = CMD_READ;
  } else if (strcmp(req, "write") == 0) {
    cmd->c = CMD_WRITE;
  } else {
    free(cmd);
    return NULL;
  }
  return cmd;
}

// -----------------------------------------------------------------------------

const char *TOO_FEW_ARGS = "Too few arguments to command.";

static char *hex_str(const char *in, size_t in_len) {
  assert(in_len > 0);
  assert(in != NULL);
  static const char hex_digits[] = "0123456789abcdef";
  size_t out_len = (2 * in_len) + 1;
  char *out = malloc(out_len);
  int j = 0;
  for (int i = 0; i < in_len; i++) {
    out[j] = hex_digits[(unsigned char)in[i] >> 4];
    out[j + 1] = hex_digits[(unsigned char)in[i] & 15];
    j += 2;
  }
  out[out_len - 1] = '\0';
  return out;
}

static char *key() {
  char data[KEY_SIZE];
  FILE *f = fopen("/dev/urandom", "r");
  if (f == NULL) {
    return NULL;
  }
  for (int i = 0; i < KEY_SIZE; i++) {
    size_t ret = fread(data + i, 1, 1, f);
    if (ret != 1) {
      fclose(f);
      return NULL;
    }
  }
  fclose(f);
  return hex_str(data, KEY_SIZE);
}

static char *cmd_write(const char *arg) {
  if (arg == NULL) {
    return notes_strdup(TOO_FEW_ARGS);
  }
  if (strlen(arg) >= BUF_SIZE) {
    return notes_strdup("Too big!");
  }
  char *k = key();
  FILE *f = fopen(k, "w");
  if (f == NULL) {
    free(k);
    return NULL;
  }
  fprintf(f, "%s\n", arg);
  fclose(f);
  return k;
}

static char *cmd_read(const char *arg) {
  if (arg == NULL) {
    return notes_strdup(TOO_FEW_ARGS);
  }
  FILE *f = fopen(arg, "r");
  if (f == NULL) {
    return notes_strdup("Invalid key!");
  }
  char data[BUF_SIZE];
  fgets(data, BUF_SIZE, f);
  fclose(f);
  return notes_strdup(data);
}

// -----------------------------------------------------------------------------

//  Mutates but does not free its string argument.
char *handle(char *req) {
  assert(req != NULL);
  cmd_t *cmd = parse(req);
  if (cmd == NULL) {
    return notes_strdup(
        "Failed to parse command, try 'read <key>', 'write <str>' or 'quit'");
  }

  char *resp = NULL;
  switch (cmd->c) {
  case CMD_WRITE: {
    resp = cmd_write(cmd->arg);
    break;
  }
  case CMD_READ: {
    resp = cmd_read(cmd->arg);
    break;
  }
  case CMD_QUIT: {
    break;
  }
  default: {
    resp = notes_strdup("Not implemented!");
    break;
  }
  }
  free(cmd);
  return resp;
}

int handle_loop(int connection_fd) {
  while (true) {
    send(connection_fd, "notes> ", strlen("notes> "), MSG_NOSIGNAL);

    char req[BUF_SIZE];
    ssize_t read = recv(connection_fd, req, BUF_SIZE - 1, 0);
    assert(read < BUF_SIZE);
    if (read == 0 || (read == 1 && req[0] == '\n')) {
      continue;
    }
    req[read] = '\0';
    if (req[read - 1] == '\n') {
      req[read - 1] = '\0';
    }
    char *response = handle(req);
    if (response == NULL) {
      return -1;
    }
    send(connection_fd, response, strlen(response), MSG_NOSIGNAL);
    send(connection_fd, "\n", 1, MSG_NOSIGNAL);
    free(response);
  }
  assert(false);
}

int accept_loop(int socket_fd) {
  while (true) {
    int connection_fd = accept(socket_fd, NULL, NULL);
    if (connection_fd < 0) {
      close(socket_fd);
      return EXIT_FAILURE;
    }

    handle_loop(connection_fd);

    if (shutdown(connection_fd, SHUT_RDWR) == -1) {
      close(connection_fd);
      close(socket_fd);
      return EXIT_FAILURE;
    }
    close(connection_fd);
  }
  assert(false); // unreachable
}

// =============================================================================
#ifndef FUZZ
#ifndef TEST
int main(void) {
  struct sockaddr_in sa;
  int socket_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (socket_fd == -1) {
    puts("Couldn't create socket!\n");
    exit(EXIT_FAILURE);
  }

  memset(&sa, 0, sizeof sa);

  sa.sin_family = AF_INET;
  sa.sin_port = htons(PORT);
  sa.sin_addr.s_addr = htonl(INADDR_ANY);

  if (bind(socket_fd, (struct sockaddr *)&sa, sizeof sa) == -1) {
    close(socket_fd);
    puts("Couldn't bind socket!\n");
    exit(EXIT_FAILURE);
  }

  printf("Listening on port %d\n", PORT);

  if (listen(socket_fd, 10) == -1) {
    puts("Couldn't listen to socket!\n");
    close(socket_fd);
    exit(EXIT_FAILURE);
  }

  int exit_code = accept_loop(socket_fd);
  close(socket_fd);
  return exit_code;
}

// =============================================================================

/* Everything beyond this point is infrastructure for testing. To run the tests:

clang -Wall -Werror -o notes -O1 -fsanitize=undefined -DTEST -g notes.c && \
  valgrind --quiet --tool=memcheck --leak-check=no ./notes && \
  clang -o notes -O1 -fsanitize=address -DTEST -g notes.c && \
  ./notes && \
  clang -o notes -O1 -fsanitize=address,fuzzer -DFUZZ -g notes.c && \
  ./notes -runs=1000000
 */

// =============================================================================
#else
static void test_parse(void) {
  char *s = notes_strdup("read");
  cmd_t *cmd = parse(s);
  assert(cmd != NULL);
  assert(cmd->arg == NULL);
  free(s);
  free(cmd);

  s = notes_strdup("read\n");
  cmd = parse(s);
  assert(cmd == NULL);
  free(s);

  s = notes_strdup("read key");
  cmd = parse(s);
  assert(cmd->arg != NULL);
  free(s);
  free(cmd);
}

static const char *CMDS[] = {
    "", "junk", "quit", "read", "write", "read foo", "write foo",
};

static void test_handle(void) {
  for (int i = 0; i < (sizeof(CMDS) / sizeof(CMDS[0])); i++) {
    char *req = notes_strdup(CMDS[i]);
    char *resp = handle(req);
    free(req);
    free(resp);
  }
}

int main(void) {
  test_parse();
  test_handle();
  return 0;
}
#endif
// =============================================================================
#else
int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
  if (size != 0) {
    char *mut_data = malloc(size);
    assert(mut_data != NULL);
    memcpy(mut_data, data, size);
    mut_data[size - 1] = '\0';
    free(handle(mut_data));
    free(mut_data);
  }
  return 0;
}
#endif
