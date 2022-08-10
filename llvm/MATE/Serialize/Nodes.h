#pragma once

#include <set>
#include <string>

#include "../Nodes.h"
#include "../Utils.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/Support/JSON.h"

namespace mate {

auto getPrettyValue(const llvm::Value&) -> std::string;

auto serializeFunction(const llvm::Function&, bool) -> llvm::json::Object;

auto serializeBlock(const llvm::BasicBlock&, bool) -> llvm::json::Object;

auto serializeGlobalVariable(const llvm::GlobalVariable&, bool)
    -> llvm::json::Object;

auto serializeInstruction(const llvm::Instruction&, bool, llvm::Optional<bool>)
    -> llvm::json::Object;

auto serializeConstant(const llvm::Constant&, bool) -> llvm::json::Object;

auto serializeArgumentWithoutDebugInfo(
    const llvm::Argument&, bool, llvm::Optional<bool>) -> llvm::json::Object;

auto serializeArgument(
    const llvm::Argument&,
    bool,
    llvm::Optional<bool>,
    const llvm::DILocalVariable&,
    const llvm::DebugLoc&) -> llvm::json::Object;

auto serializeLocalVariable(const llvm::DILocalVariable&, const llvm::DebugLoc&)
    -> llvm::json::Object;

auto serializeMemoryLocation(const MemoryLocationIdentifier&)
    -> llvm::json::Object;

};  // namespace mate
