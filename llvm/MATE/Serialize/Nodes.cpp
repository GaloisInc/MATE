#include "Nodes.h"

namespace mate {
auto getPrettyValue(const llvm::Value& value) -> std::string {
  std::string pretty_string((std::string::size_type)0, 0);
  pretty_string.reserve(1024);
  llvm::raw_string_ostream raw_pretty_stream(pretty_string);
  raw_pretty_stream.SetUnbuffered();
  raw_pretty_stream << value;
  return pretty_string;
}

void addGlobalObjectDataToJSON(
    const llvm::GlobalObject& global_obj, llvm::json::Object& payload) {
  payload["is_declaration"] = global_obj.isDeclaration();
  payload["alignment"] = global_obj.getAlignment();
  if (global_obj.hasSection()) {
    payload["section"] = global_obj.getSection();
  }
}

static inline void addDIVariableLocationToJSON(
    const llvm::DIVariable& di_variable, llvm::json::Object& payload) {
  payload["location"] = llvm::json::Object(
      {{"line", di_variable.getLine()},
       {"file", di_variable.getFilename()},
       {"dir", di_variable.getDirectory()}});
}

void addVariableLocationToJSON(
    const llvm::DILocalVariable& di_local_variable,
    const llvm::DebugLoc& debug_location,
    llvm::json::Object& payload) {
  auto line = debug_location->getLine();
  auto column = debug_location->getColumn();

  // NOTE(ww): See expandLocation in Headache: a line and column of (0, 0)
  // indicates that LLVM has probably optimized this DILocation out; we fall
  // back on the DILocalVariable's (more reliable) line information when we
  // encounter this. This behavior **must** match that of Headache, since the
  // two must agree on node IDs for proper pairing.
  if (line == 0 && column == 0) {
    line = di_local_variable.getLine();
  }

  unsigned scope_line, scope_column;
  if (const auto* DILB = llvm::dyn_cast_or_null<llvm::DILexicalBlock>(
          di_local_variable.getScope())) {
    scope_line = DILB->getLine();
    scope_column = DILB->getColumn();
  } else {
    scope_line = 0;
    scope_column = 0;
  }

  // NOTE(ww): We get the function name through the DISubprogram here
  // to prevent mis-generation of IDs for local variables and arguments:
  // using `llvm::Function` will sometimes give us the name of the function
  // that the variable or argument has been inlined into, rather than its
  // originating function.
  // Unfortunately, this alone isn't enough: LLVM has internal disambiguation
  // rules for conflicting symbols, meaning that the function name retrieved
  // here may not match its corresponding LLVM function (for example, `foo` here
  // might be `foo.3` in LLVM's world). We don't have an easy way to get the
  // *real* LLVM function name here (since we might be inlined), so instead we
  // generate a "compressed ID" that should always be unique for this particular
  // function and source location, even if the function's name isn't itself
  // unique.
  // See the note on compressedScopeID (Utils.h) for more rationale about this
  // ID, as well as about what goes into it.
  const auto func =
      subprogramName(*di_local_variable.getScope()->getSubprogram());
  auto compressed_id = compressedScopeID(
      func, debug_location, line, column, scope_line, scope_column);
  payload["location"] = llvm::json::Object({
      {"line", line},
      {"column", column},
      {"file", debug_location->getFilename()},
      {"dir", debug_location->getDirectory()},
      {"function", func},
      {"compressed_id", std::move(compressed_id)},
  });
}

auto serializeFunction(const llvm::Function& function, bool pretty_string)
    -> llvm::json::Object {
  llvm::json::Object payload{
      {"name", function.getName()},
      {"demangled_name", demangle_symbol(function.getName())}};
  addGlobalObjectDataToJSON(function, payload);
  const auto* di_subprogram = function.getSubprogram();
  if (di_subprogram != nullptr) {
    payload["location"] = llvm::json::Object(
        {{"file", di_subprogram->getFilename()},
         {"dir", di_subprogram->getDirectory()}});
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(function);
  }
  return payload;
}

auto serializeBlock(const llvm::BasicBlock& block, bool pretty_string)
    -> llvm::json::Object {
  llvm::json::Object payload;
  if (block.hasName()) {
    payload["label"] = block.getName();
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(block);
  }
  return payload;
}

auto serializeGlobalVariable(
    const llvm::GlobalVariable& global, bool pretty_string)
    -> llvm::json::Object {
  llvm::json::Object payload{
      {"has_initializer", global.hasInitializer()},
      {"is_constant", global.isConstant()},
      {"name", global.getGlobalIdentifier()}};
  addGlobalObjectDataToJSON(global, payload);
  llvm::SmallVector<llvm::DIGlobalVariableExpression*, 16> global_var_exprs;
  global.getDebugInfo(global_var_exprs);
  for (const auto* global_var_expr : global_var_exprs) {
    addDIVariableLocationToJSON(*global_var_expr->getVariable(), payload);
    break;
  }

  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(global);
  }
  return payload;
}

auto serializeInstruction(
    const llvm::Instruction& instruction,
    bool pretty_string,
    llvm::Optional<bool> maybe_null) -> llvm::json::Object {
  llvm::json::Object payload;

  payload["opcode"] = instruction.getOpcodeName();

  if (maybe_null.hasValue()) {
    payload["might_be_null"] = maybe_null.getValue();
  }

  // Attach debug info/metadata, if present
  const auto* dbg_metadata = instruction.getMetadata(llvm::LLVMContext::MD_dbg);
  if (dbg_metadata != nullptr) {
    if (llvm::isa<llvm::DILocation>(*dbg_metadata)) {
      const auto* location = llvm::cast<llvm::DILocation>(dbg_metadata);
      payload["location"] = llvm::json::Object(
          {{"line", location->getLine()},
           {"column", location->getColumn()},
           {"file", location->getFilename()},
           {"dir", location->getDirectory()}});
    }
  }

  // For instructions that "return" non-void, attach the name
  // of the SSA variable that the return is stored in.
  if (!instruction.getType()->isVoidTy()) {
    payload["ssa_name"] = instruction.getName();
  }

  const auto call_site = asCallSite(instruction);
  if (call_site.hasValue()) {
    payload["is_direct"] = !call_site.getValue().isIndirectCall();
    // For calls to intrinsics, attach the intrinsic ID
    if (call_site.getValue().getCalledFunction() != nullptr) {
      const auto& called_function = *call_site.getValue().getCalledFunction();
      auto iid = (unsigned)called_function.getIntrinsicID();
      if (called_function.getIntrinsicID() != llvm::Intrinsic::not_intrinsic) {
        payload["intrinsic"] = iid;
      }
    }
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(instruction);
  }
  return payload;
}  // namespace mate

auto serializeConstant(const llvm::Constant& constant, bool pretty_string)
    -> llvm::json::Object {
  llvm::json::Object payload;
  payload["is_null_value"] = constant.isNullValue();
  payload["is_one_value"] = constant.isOneValue();
  payload["is_all_ones_value"] = constant.isAllOnesValue();
  payload["is_zero_value"] = constant.isZeroValue();
  payload["is_normal_fp"] = constant.isNormalFP();
  payload["is_nan"] = constant.isNaN();
  payload["contains_undef"] = constant.containsUndefElement();
  payload["can_trap"] = constant.canTrap();
  if (llvm::isa<llvm::ConstantData>(constant)) {
    if (llvm::isa<llvm::ConstantAggregateZero>(constant)) {
      payload["constant_data_subclass"] = "ConstantAggregateZero";
    } else if (llvm::isa<llvm::ConstantDataArray>(constant)) {
      payload["constant_data_subclass"] = "ConstantDataArray";
    } else if (llvm::isa<llvm::ConstantDataVector>(constant)) {
      payload["constant_data_subclass"] = "ConstantDataVector";
    } else if (llvm::isa<llvm::ConstantFP>(constant)) {
      payload["constant_data_subclass"] = "ConstantFP";
    } else if (llvm::isa<llvm::ConstantInt>(constant)) {
      payload["constant_data_subclass"] = "ConstantInt";
      payload["constant_int_value"] =
          llvm::cast<llvm::ConstantInt>(constant).getLimitedValue();
    } else if (llvm::isa<llvm::ConstantPointerNull>(constant)) {
      payload["constant_data_subclass"] = "ConstantPointerNull";
    } else if (llvm::isa<llvm::ConstantTokenNone>(constant)) {
      payload["constant_data_subclass"] = "ConstantTokenNone";
    } else if (llvm::isa<llvm::UndefValue>(constant)) {
      payload["constant_data_subclass"] = "UndefValue";
    } else {
      assert(false);  // unreachable
    }
  }
  if (llvm::isa<llvm::ConstantDataSequential>(constant) &&
      llvm::cast<llvm::ConstantDataSequential>(constant).isCString()) {
    // NOTE(ww): Observe that we use a hexadecimal string, rather than a more
    // compact encoding (like base64) here. This is intentional. We do it for
    // substring searchability: base64-encoded inputs can't be searched for
    // substrings without decoding first, while hexadecimal (or another N-1
    // encoding, for N>=1) inputs can be.
    payload["string_value"] =
        hexstring(llvm::cast<llvm::ConstantDataSequential>(constant)
                      .getAsCString()
                      .str());
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(constant);
  }
  return payload;
}

// NOTE(lb): There's very slight duplication between this case and the case with
// debug info, but they have enough different arguments that it would be a pain
// to make a bunch of them optional, and it's not quite enough to factor out
// IMO.
auto serializeArgumentWithoutDebugInfo(
    const llvm::Argument& argument,
    bool pretty_string,
    llvm::Optional<bool> maybe_null) -> llvm::json::Object {
  llvm::json::Object payload{{"argument_number", argument.getArgNo()}};
  if (maybe_null.hasValue()) {
    payload["might_be_null"] = maybe_null.getValue();
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(argument);
  }
  return payload;
}

auto serializeArgument(
    const llvm::Argument& argument,
    bool pretty_string,
    llvm::Optional<bool> maybe_null,
    const llvm::DILocalVariable& di_local_variable,
    const llvm::DebugLoc& debug_location) -> llvm::json::Object {
  llvm::json::Object payload{{"argument_number", argument.getArgNo()}};
  if (maybe_null.hasValue()) {
    payload["might_be_null"] = maybe_null.getValue();
  }
  payload["name"] = di_local_variable.getName().str();
  addVariableLocationToJSON(di_local_variable, debug_location, payload);
  if (pretty_string) {
    payload["pretty_string"] = getPrettyValue(argument);
  }
  return payload;
}

auto serializeLocalVariable(
    const llvm::DILocalVariable& di_local_variable,
    const llvm::DebugLoc& debug_location) -> llvm::json::Object {
  llvm::json::Object payload{{"name", di_local_variable.getName().str()}};
  addVariableLocationToJSON(di_local_variable, debug_location, payload);
  return payload;
}

auto serializeMemoryLocation(
    const MemoryLocationIdentifier& memory_location_identifier)
    -> llvm::json::Object {
  llvm::json::Object payload;
  memory_location_identifier.insertIntoPayload(payload);
  return payload;
}
};  // namespace mate
