#include "llvm/Analysis/TargetLibraryInfo.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Module.h"
#include "llvm/Pass.h"
#include "llvm/Support/Path.h"
#include "llvm/Transforms/Utils/BuildLibCalls.h"

namespace mate {
class TraceLogger : public llvm::ModulePass {
 public:
  static char ID;

  TraceLogger() : llvm::ModulePass(ID) {}

  void getAnalysisUsage(llvm::AnalysisUsage& analysis_usage) const override {
    analysis_usage.addRequired<llvm::TargetLibraryInfoWrapperPass>();
  }

  auto getSourceStem(const llvm::Module* M) -> llvm::StringRef {
    return llvm::sys::path::stem(M->getSourceFileName());
  }

  // NOTE(ww): clang-tidy wants to rewrite this to:
  //   auto runOnModule(llvm::Module &module) override -> bool { ... }
  // Which *works*, but subsequently causes two clang different
  // clang-diagnostic-errors when rewritten. I think this is probably
  // a bug, so just skip it for now.
  // NOLINTNEXTLINE(modernize-use-trailing-return-type)
  bool runOnModule(llvm::Module& module) override {
    for (auto& function : module) {
      const auto& target_library_info =
          getAnalysis<llvm::TargetLibraryInfoWrapperPass>().getTLI(function);

      for (auto& block : function) {
        std::string base_string;
        llvm::raw_string_ostream raw_out(base_string);
        const auto* module = block.getModule();
        raw_out << "<block>:" << getSourceStem(module) << ':';
        block.getParent()->printAsOperand(raw_out, false);
        raw_out << ':';
        block.printAsOperand(raw_out, false);

        logMessage(
            raw_out.str(), block.getFirstInsertionPt(), target_library_info);
      }
    }

    return true;
  }

  static void logMessage(
      llvm::StringRef message,
      llvm::BasicBlock::iterator position,
      const llvm::TargetLibraryInfo& target_library_info) {
    llvm::IRBuilder<> builder(&*position);
    auto* message_pointer_value = builder.CreateGlobalStringPtr(message);
    llvm::emitPutS(message_pointer_value, builder, &target_library_info);
  }
};

char TraceLogger::ID = 0;
static llvm::RegisterPass<TraceLogger> X(
    "trace-logger",
    "Trace Logger Transformer Pass",
    true /* Only looks at CFG */,
    false /* Transformer Pass */);
}  // namespace mate
