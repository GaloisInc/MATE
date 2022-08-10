# General:

* **Tests:** Is the code tested? Are the tests missing any edge cases?
* **Integration Tests:** If the changes might affect the integration tests, schedule the integration tests to run in CI
* **Datastructures:** Are the appropriate datastructures used? Is there anywhere that a map or set would be more appropriate than a list?
* **Performance:** Is there any iteration that could be improved? Are there any performance improvements that could be made or bookmarked for later?
* **Documentation:** Is there any documentation that should be added or changed? 
* **Gitlab Issues:** Are there any related issues that should be linked, opened or closed?

# Specific checks:

* frontend code & tests: use NodeKind / EdgeKind / Opcode / NodeJSON enums rather than literal string values
* file paths should be relative
* tests & demos should document which flags they expect the program under analysis to be compiled with
* llvm passes: are there functions that should be marked either constexpr or __attribute__((always_inline))?
* new nodes / edges: updated all of: ASTGraphWriter, nodes / edges schema, mate/cpg/types.py

# Some possibly relevant C & C++ edge cases:

* Functions: no arguments, pointer arguments, return values or not, multiple returns, varargs
* Dataflow: global state, modifying the memory at that arguments point to, global state in linked library code, function calls
* Control flow: externally defined symbols
* Class inheritance in cpp
* Arrays: pointers to the stack, the heap, and explicit arrays, ie char arr[3];
* Aliasing pointer arguments before a function call

