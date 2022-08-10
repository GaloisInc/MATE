#include <stdio.h>

int main() {

  char user_input[100];
  fgets(user_input, 100, stdin);

  char q1[200];
  sprintf(q1, "SELECT username FROM users WHERE username = '%s';", user_input);

  // the POI shouldn't find this string after #528
  // https://gitlab-ext.galois.com/mate/MATE/-/issues/528
  sprintf(q1, "this is just a sentence that has the word SELECT in it '%s';",
          user_input);

  // intentionally put some invalid unicode in there, to make sure it
  // doesn't choke up our analysis
  char q2[200];
  sprintf(q2, "DROP user WHERE username = '\xff%s\xff';", user_input);

  return 0;
}
