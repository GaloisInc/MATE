#include "Utils.h"

namespace mate {
/**
 * If this is a call or invoke instruction, return it as an ImmutableCallSite.
 */
auto asCallSite(const llvm::Instruction& instruction)
    -> llvm::Optional<const llvm::ImmutableCallSite> {
  if (llvm::isa<llvm::CallInst>(instruction)) {
    return llvm::Optional<const llvm::ImmutableCallSite>(
        llvm::cast<llvm::CallInst>(&instruction));
  }
  if (llvm::isa<llvm::InvokeInst>(instruction)) {
    return llvm::Optional<const llvm::ImmutableCallSite>(
        llvm::cast<llvm::InvokeInst>(&instruction));
  }
  return llvm::None;
}

auto asCallSite(const llvm::Value& value)
    -> llvm::Optional<const llvm::ImmutableCallSite> {
  if (llvm::isa<llvm::Instruction>(value)) {
    return asCallSite(llvm::cast<llvm::Instruction>(value));
  }
  return llvm::None;
}
};  // namespace mate
