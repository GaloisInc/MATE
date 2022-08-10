#pragma once

#include <string>

#include "llvm/IR/DataLayout.h"
#include "llvm/IR/Type.h"
#include "llvm/Support/JSON.h"

namespace mate {

auto serializeLLVMType(
    llvm::Type& type, bool pretty_string, const llvm::DataLayout& dl)
    -> llvm::json::Object;

};  // namespace mate
