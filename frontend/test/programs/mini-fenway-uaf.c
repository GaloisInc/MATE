/* Derived from chess-aces program with MIT license (reproduced below). See also
 * doc/legal.rst
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the “Software”), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_BYTE_SIZE 0xffff
#define MAX_FILENAME 255

typedef void (*ppm_printer)(uint16_t, uint16_t, int ***, uint64_t);
typedef void (*pgm_printer)(uint16_t, uint16_t, int **, uint64_t);

typedef struct PPM {
  ppm_printer fp;
  char filename[MAX_FILENAME];
  char magic_num[3];
  uint16_t width;
  uint16_t length;
  uint64_t version;
  int ***pixels;
} PPM;

typedef struct PGM {
  char filename[MAX_FILENAME];
  pgm_printer fp;
  char magic_num[3];
  uint16_t width;
  uint16_t length;
  uint64_t version;
  int **pixels;
} PGM;

/* globals */
PPM *ppm;
PGM *pgm;
uint64_t version;

/* =========================================================== */

void print_ppm(uint16_t width, uint16_t length, int ***pixels, uint64_t dummy) {
  printf("print_ppm\n");
}

PPM *create_ppm(char *filename, uint64_t version) {
  PPM *image = malloc(sizeof(PPM));
  image->fp = &print_ppm;

  strncpy(image->filename, filename, MAX_FILENAME - 1);
  image->filename[MAX_FILENAME - 1] = '\0';

  image->pixels = NULL;

  return image;
}
void destroy_ppm(PPM *p) { free(p); }

void print_pgm(uint16_t width, uint16_t length, int **pixels,
               uint64_t version) {
  printf("print_pgm\n");
}

PGM *create_pgm(char *filename, uint64_t version) {
  PGM *image = malloc(sizeof(PGM));

  strncpy(image->filename, filename, MAX_FILENAME - 1);
  image->filename[MAX_FILENAME - 1] = '\0';

  image->fp = &print_pgm;

  image->pixels = NULL;

  return image;
}

void destroy_pgm(PGM *p) { free(p); }

/* =========================================================== */

typedef struct __attribute__((packed)) {
  uint16_t byte_count[1];
  char *bytes;
} Data_Block;

typedef struct __attribute__((packed)) {
  char command;
  Data_Block dblock;
} SMB_Struct;

/*
 * Input Format
 * ====================================
 * 0 123456789 ...............
 * | \         \
 * |  \         \- bytes 10+ are 'path'
 * |   \
 * |    \- bytes 1-9 are 'version'
 * |
 * \- byte 0 is the 'command' type:
 *        'A' == PPM
 *        'B' == PGM
 */

void parse(char *input) {
  char *path;

  printf("Parsing input: '%s'\n", input);

  SMB_Struct *smb = malloc(sizeof(SMB_Struct));
  smb->dblock.bytes = NULL;

  // byte 0 is command
  memcpy(&smb->command, &input[0], 1);

  switch (smb->command) {
  case 'A':
    printf("Command A: creating PPM\n");
    /* create PPM with bytes 1-9 = version, 10+ = path */

    smb->dblock.bytes = calloc(1, MAX_BYTE_SIZE + 1);
    strcpy(smb->dblock.bytes, &input[1]);

    memcpy(&version, smb->dblock.bytes + 0, 8);

    path = calloc(1, MAX_BYTE_SIZE + 1);
    strncpy(path, smb->dblock.bytes + 8, MAX_BYTE_SIZE);

    printf("  Version: 0x%" PRIx64 "\n", version);
    printf("  Path: %s\n", path);
    ppm = create_ppm(path, version);

    free(path);
    path = NULL;
    break;

  case 'B':
    printf("Command B: creating PGM\n");
    /* create PGM with bytes 1-9 = version, 10+ = path */

    smb->dblock.bytes = calloc(1, MAX_BYTE_SIZE + 1);
    strcpy(smb->dblock.bytes, &input[1]);

    memcpy(&version, smb->dblock.bytes + 0, 8);

    path = calloc(1, MAX_BYTE_SIZE + 1);
    strncpy(path, smb->dblock.bytes + 8, MAX_BYTE_SIZE);

    printf("  Version: 0x%" PRIx64 "\n", version);
    printf("  Path: %s\n", path);
    pgm = create_pgm(path, version);

    free(path);
    path = NULL;
    break;

  default:
    printf("Parser got unhandled command: '%c'\n", smb->command);
    break;
  }

  printf("Finished processing command, performing print/cleanup...\n");
  if (smb->dblock.bytes != NULL) {
    if (strstr(smb->dblock.bytes, ".ppm") != NULL && ppm != NULL) {

      free(smb->dblock.bytes);
      smb->dblock.bytes = NULL;

      ppm->fp(250, 87, ppm->pixels, version); /* potential UAF */

      destroy_ppm(ppm);

#ifdef PATCHED
      ppm = NULL;
#endif

    } else if (strstr(smb->dblock.bytes, ".pgm") != NULL && pgm != NULL) {

      free(smb->dblock.bytes);
      smb->dblock.bytes = NULL;

      destroy_pgm(pgm);

#ifdef PATCHED
      pgm = NULL;
#endif

    } else {
      printf("No Print\n");
    }
  }
}

int main(int argc, char *argv[]) {
  char input[80];

  printf("NB example attack payload:\n");
  printf("A00000000ABCDEFGH.ppm\n");
  printf("B00000000ABCDEFGH.ppm\n");

  /* main loop: process each line of input from the user */
  printf("Enter input, Control-D to quit.\n");
  while (fgets(input, sizeof(input), stdin)) {
    input[strcspn(input, "\n")] = 0;
    parse(input);

    printf("Enter input, Control-D to quit.\n");
  }
}
