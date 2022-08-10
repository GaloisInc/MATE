#include <stdio.h>
#include <stdlib.h>
#include <string.h>

const char *password = "very_secret_password";

void true_positive(void) {
  char buf[256];
  if (fgets(buf, 256, stdin) != NULL) {
    size_t len = strlen(buf);
    if (buf[len - 1] == '\n') {
      buf[len - 1] = '\0';
      len--;
    }
    if (strncmp(password, buf, len) == 0) { // ERROR: just "v" will work...
      puts("Authenticated! Here is the secret data: ...\n");
      return;
    }
    puts("Invalid password\n");
    return;
  }
  puts("Couldn't get password\n");
  return;
}

void neg_correct_length(void) {
  char buf[256];
  if (fgets(buf, 256, stdin) != NULL) {
    size_t len = strlen(buf);
    if (buf[len - 1] == '\n') {
      buf[len - 1] = '\0';
      len--;
    }
    if (strncmp(password, buf, strlen(password)) == 0) { // this is correct
      puts("Authenticated! Here is the secret data: ...\n");
      return;
    }
    puts("Invalid password\n");
    return;
  }
  puts("Couldn't get password\n");
  return;
}

// False positive: User controls both inputs, neither one is a password
void false_pos_both_args(void) {
  char buf1[256];
  char buf2[256];
  if (fgets(buf1, 256, stdin) == NULL || fgets(buf2, 256, stdin) == NULL) {
    puts("Couldn't get inputs\n");
    return;
  }
  size_t len1 = strlen(buf1);
  size_t len2 = strlen(buf2);
  if (buf1[len1 - 1] == '\n') {
    buf1[len1 - 1] = '\0';
    len1--;
  }
  if (buf2[len2 - 1] == '\n') {
    buf2[len2 - 1] = '\0';
    len2--;
  }
  if (strncmp(buf1, buf2, len1 < len2 ? len1 : len2) == 0) {
    puts("Your inputs were the same!\n");
    return;
  }
  puts("Inputs were not the same\n");
  return;
}

// True positive: User doesn't have access to file, but does write to stdin
void true_pos_both_args(void) {
  char buf1[256];
  char buf2[256];
  FILE *f = fopen("/super/secret/password", "r");
  if (f == NULL) {
    return;
  }
  if (fgets(buf1, 256, stdin) == NULL || fgets(buf2, 256, f) == NULL) {
    puts("Couldn't get inputs\n");
    fclose(f);
    return;
  }
  fclose(f);
  size_t len1 = strlen(buf1);
  size_t len2 = strlen(buf2);
  if (buf1[len1 - 1] == '\n') {
    buf1[len1 - 1] = '\0';
    len1--;
  }
  if (buf2[len2 - 1] == '\n') {
    buf2[len2 - 1] = '\0';
    len2--;
  }
  if (strncmp(buf1, buf2, strlen(buf2)) == 0) {
    puts("Authenticated!\n");
    return;
  }
  puts("Inputs were not the same\n");
  return;
}

// User only controls the length
void neg_just_len(void) {
  char buf[256];
  if (fgets(buf, 256, stdin) == NULL) {
    puts("Couldn't get inputs\n");
    return;
  }
  size_t len = strlen(buf);
  if (len > 4) {
    return;
  }
  if (strncmp("asdf", "asfdsa", len) == 0) {
    puts("Woot!\n");
    return;
  }
  puts("Whatever\n");
  return;
}

int main(int argc, char **argv) {
  if (argc > 1) {
    printf("usage: ./%s < PASSWORD\n", argv[0]);
    exit(1);
  }
  true_positive();
  neg_correct_length();
  false_pos_both_args();
  true_pos_both_args();
  neg_just_len();
  return 0;
}
