#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

// global auth: simple flag & auth token struct
bool a_okay = false;

struct AuthToken {
  bool a_okay;
  bool herring_is_red;
} auth_token = {false, true};

// a mutually called but irrelevant function
// parses until it sees a newline
void parse(char *password) {
  int i = 0;
  while (true) {
    password[i] = getchar();
    if (password[i] == '\n') {
      break;
    }
    i++;
  }
}

// there are multiple passwords for different test cases
// they are: magic & taxes
void authenticate(char *password) {
  // first case is setting a global auth flag
  if (password[0] == 'm') {
    char red_herring = password[0];
    if (red_herring == password[1]) {
      return;
    }
    if (strncmp(password, "magic", 5) == 0) {
      a_okay = true;
    }
  } // next case is setting a field of a global auth struct
  else if (password[0] == 't') {
    char red_herring = password[0];
    if (red_herring == password[1]) {
      return;
    } else if (strncmp(password, "taxes", 5) == 0) {
      auth_token.a_okay = true;
    }
  }
}

// a sensitive function that performs an access control check
void tell_me_the_secret() {
  if (a_okay) {
    printf("P /= NP!!\n");
  } else if (auth_token.a_okay) {
    printf("P = NP!!\n");
  } else {
    printf("No dice!\n");
  }
}

int main(void) {
  char *password;
  password = (char *)malloc(10 * sizeof(char));
  parse(password);
  authenticate(password);
  tell_me_the_secret();
  return 0;
}

/**
Here are the inputs for various traces:

1. Test global auth flag
success auth trace input: magic\n
failed auth trace input: wrong\n

alternative inputs (different bbs in trace):
success auth trace input: magic\n
failed auth trace input: mm\n

2. Test global auth token field
success auth trace input: taxes\n
failed auth trace input: wrong\n

alternative inputs (different bbs in trace):
success auth trace input: taxes\n
failed auth trace input: tt\n

**/