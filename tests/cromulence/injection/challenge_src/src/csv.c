#define _GNU_SOURCE

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#include "csv.h"
#include "db.h"

const size_t MAX_LINE = 120;
const char SEPARATOR[] = ",";
const char QUOTE[] = "\"";

uint8_t count_commas(char* line);

void load_columns(table* table, FILE* csv_file);

char* parse_column(char** string_remain);
char* parse_quoted_column(char** string_remain);

uint32_t count_lines(FILE* csv_file);

table* load_csv(char* filename) {
  FILE* csv_file = fopen(filename, "r");

  void* tmp = calloc(1, sizeof(table));
  if (NULL == tmp) exit(1);
  table* table = tmp;
  assert(table);

  load_columns(table, csv_file);

  table->row_count = count_lines(csv_file);

  table->rows = calloc(table->row_count, sizeof(row));
  assert(table->rows);

  for (uint32_t r = 0; r < table->row_count; r++) {
    row* row = &(table->rows[r]);
    row->cols = calloc(table->col_count, sizeof(col));
    assert(row->cols);

    char line_buf[MAX_LINE + 1];
    bzero(line_buf, MAX_LINE);
    fgets(line_buf, MAX_LINE, csv_file);
    line_buf[strlen(line_buf) - 1] = 0; 

    char* col_buf = strdup(line_buf);
    char* cur_col = col_buf;

    for (uint8_t c = 0; c < table->col_count; c++) {
      row->cols[c].contents = strdup(parse_column(&cur_col));
    }

    free(col_buf);
  }

  return table;
}

char* parse_column(char** string_remain) {
  if (QUOTE[0] == (*string_remain)[0]) {
    (*string_remain)++; 
    return parse_quoted_column(string_remain);
  }

  return strsep(string_remain, SEPARATOR);
}

char* parse_quoted_column(char** string_remain) {
  char* quoted_bit = strsep(string_remain, QUOTE);
  (*string_remain)++; 
  return quoted_bit;
}

uint8_t count_commas(char* line) {
  uint8_t count = 0;
  char c;
  while ((c = *line)) {
    if (',' == c) count++;
    line += sizeof(char);
  }

  return count;
}

void load_columns(table* table, FILE* csv_file) {
  char line_buf[MAX_LINE + 1];
  bzero(line_buf, MAX_LINE);

  fgets(line_buf, MAX_LINE, csv_file);
  line_buf[strlen(line_buf) - 1] = 0; 

  table->col_count = count_commas(line_buf) + 1;
  table->cols = calloc(table->col_count, sizeof(col));

  char* col_buf = strdup(line_buf);
  char* cur_col = col_buf;
  for (uint8_t c = 0; c < table->col_count; c++) {
    table->cols[c].contents = strdup(strsep(&cur_col, SEPARATOR));
  }

  free(col_buf);
}

uint32_t count_lines(FILE* csv_file) {
  char line_buf[MAX_LINE + 1];
  bzero(line_buf, MAX_LINE);

  uint32_t count = 0;
  off_t data_start = ftello(csv_file);

  while (NULL != fgets(line_buf, MAX_LINE, csv_file)) {
    count++;
  }

  fseeko(csv_file, data_start, SEEK_SET);
  return count;
}
