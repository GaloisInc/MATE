
#pragma once

#include <stdint.h>
#include <stdio.h>

typedef struct {
  char* contents;
} col;

typedef struct {
  col* cols;
} row;

typedef struct {
  uint32_t row_count;
  uint8_t col_count;
  col* cols;
  row* rows;
} table;

typedef struct _database {
  char* name;
  table* table;
  struct _database* next_table;
} database;

database* load_database(char* directory);

void dump_database(FILE* out, database* db);

table* db_get_table(char* table_name, database* db);
