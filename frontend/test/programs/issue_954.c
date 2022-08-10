/* This is a regression case for MATE#954.
 * Ref: https://gitlab-ext.galois.com/mate/MATE/-/issues/954
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

const char *global1 = "this\xffstring\xffis\xffnot\xffutf8\xff";

const char *global2 = "this\xf4string\xf4is\xf4not\xf4utf8\xf4_either";

int main(int argc, char const *argv[]) {
  char *local1 = "this\xffstring\xffis\xff_also\xffnot\xffutf8\xff";

  char *local2 = "ЁЂЃЄЅІЇЈЉЊЋЌЍЎЏАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдежзийклмн"
                 "опрстуфхцчшщъыьэюя";

  return global1[rand() % strlen(global1)] + global2[rand() % strlen(global1)] +
         local1[rand() % strlen(local1)] + strlen(local2);
}
