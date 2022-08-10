#include "llvm/IR/Function.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"
#include "llvm/Support/CommandLine.h"

using namespace llvm;

static cl::opt<bool> EnableArgumentCanonicalization(
    "nomina-arg-canonicalization",
    cl::Hidden,
    cl::desc("Enable canonicalization of function arguments"),
    cl::init(false));

namespace {
struct Nomina : public ModulePass {
  static char ID;
  Nomina() : ModulePass(ID) {}

  auto runOnModule(Module &M) -> bool override {
    for (auto &F : M) {
      if (EnableArgumentCanonicalization) {
        uint64_t arg_idx = 0;
        for (auto &A : F.args()) {
          const auto ArgName = "a" + std::to_string(arg_idx++);
          A.setName(ArgName);
        }
      }

      uint64_t bb_idx = 0;
      uint64_t inst_idx = 0;
      for (auto &BB : F) {
        const auto BBName = "i" + std::to_string(bb_idx++);
        BB.setName(BBName);

        for (auto &I : BB) {
          // Skip instructions that "return" void, since these don't receive an
          // SSA binding.
          if (I.getType()->isVoidTy()) {
            continue;
          }

          const auto IName = "t" + std::to_string(inst_idx++);
          I.setName(IName);
        }
      }
    }
    return true;
  }
};
}  // namespace

char Nomina::ID = 0;
static RegisterPass<Nomina> X("nomina", "nomina pass", true, false);
