#pragma once

#ifdef NO_LOG
#define lll(...)  
#else
#define lll(...) fprintf(stderr, __VA_ARGS__)
#endif
