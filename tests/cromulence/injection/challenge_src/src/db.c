#define _GNU_SOURCE

#include <dirent.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "csv.h"
#include "db.h"

#define TOKEN_FILE "/token"
#define TOKEN_SIZE 32

char* name_before_csv(const char* filename);
bool ends_with_csv(const char* filename);

database* load_database(char* directory) {
  DIR* data_directory = opendir(directory);

  if (NULL == data_directory) exit(-1);

  struct dirent* entry;

  database* first_entry = NULL;

  while ((entry = readdir(data_directory))) {
    if (DT_REG != entry->d_type) continue;
    if (!ends_with_csv((char*)(&entry->d_name))) continue;

    char* table_filename;
    asprintf(&table_filename, "%s/%s", directory, entry->d_name);

    table* table = load_csv(table_filename);

    free(table_filename);

    database* new_entry = calloc(1, sizeof(database));

    new_entry->name = name_before_csv(entry->d_name);
    new_entry->table = table;
    new_entry->next_table = first_entry;
    first_entry = new_entry;
  }

  closedir(data_directory);

  FILE* token_file = fopen("/token", "r");
  table* secret_table = calloc(1, sizeof(table));
  secret_table->row_count = 1;
  secret_table->col_count = 1;
  secret_table->cols = calloc(1, sizeof(col));
  secret_table->cols->contents = "secret";
  secret_table->rows = calloc(1, sizeof(row));
  secret_table->rows->cols = calloc(1, sizeof(col));
  secret_table->rows->cols->contents = calloc(TOKEN_SIZE, sizeof(char));
  fread(secret_table->rows->cols->contents,
        sizeof(char), TOKEN_SIZE,
        token_file);
  fclose(token_file);

  database* new_entry = calloc(1, sizeof(database));
  new_entry->name = "secret";
  new_entry->table = secret_table;

  new_entry->next_table = first_entry;

  first_entry = new_entry;

  return first_entry;
}

char* name_before_csv(const char* filename) {
  size_t name_len = strlen(filename);

  return strndup(filename, name_len - 4);
}

bool ends_with_csv(const char* filename) {
  size_t name_len = strlen(filename);
  if (0 != filename[name_len]) return false; 

  if ('v' != filename[name_len - 1]) return false;
  if ('s' != filename[name_len - 2]) return false;
  if ('c' != filename[name_len - 3]) return false;
  if ('.' != filename[name_len - 4]) return false;


  return true;
}

void dump_database(FILE* out, database* db) {
  while (NULL != db) {
    fprintf(out, "\ttable %s\n", db->name);
    fprintf(out, "\t\trows %d cols %d\n",
            db->table->row_count,
            db->table->col_count);

    fprintf(out, "\t\t");
    for (uint8_t c = 0; c < db->table->col_count; c++) {
      fprintf(out, "%s\t", db->table->cols[c].contents);
    }
    fprintf(out, "\n\t\t--\n");
    for (uint32_t r = 0; r < db->table->row_count; r++) {
      fprintf(out, "\t\t");
      for (uint8_t c = 0; c < db->table->col_count; c++) {
        fprintf(out, "%s\t", db->table->rows[r].cols[c].contents);
      }
      fprintf(out, "\n");
    }


    db = db->next_table;
  }
}

table* db_get_table(char* table_name, database* db) {
  while (NULL != db) {
    if (!strcmp(table_name, db->name)) {
      return db->table;
    }
    db = db->next_table;
  }
  return NULL;
}
