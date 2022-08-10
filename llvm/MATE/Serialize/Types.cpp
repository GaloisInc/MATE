#include "Types.h"

namespace mate {

static inline auto getPrettyType(const llvm::Type& type) -> std::string {
  std::string llvm_type_string;
  llvm::raw_string_ostream raw_llvm_type_stream(llvm_type_string);
  raw_llvm_type_stream << type;
  return llvm_type_string;
}

// NB: recursion on named struct types can cause infinite loops (they can
// refer to themselves by name) so we recurse only once if the top-level type
// is a named struct.
static inline auto jsonTypeHelper(
    const llvm::Type& type, bool is_root_struct = false) -> llvm::json::Value {
  if (type.isVoidTy()) {
    return llvm::json::Value("void");
  }
  if (type.isPointerTy()) {
    const auto& pointerTy = llvm::cast<llvm::PointerType>(type);
    return llvm::json::Object(
        {{"pointer", jsonTypeHelper(*pointerTy.getElementType())}});
  }
  if (type.isStructTy()) {
    const auto& structTy = llvm::cast<llvm::StructType>(type);
    if (!structTy.hasName() || is_root_struct) {
      llvm::json::Array fields;
      for (const auto* field : structTy.elements()) {
        fields.push_back(llvm::json::Object(
            {{"field",
              llvm::json::Object({{"type", jsonTypeHelper(*field)}})}}));
      }
      // Emit both the name and the content
      if (is_root_struct) {
        if (structTy.hasName()) {
          return llvm::json::Object(
              {{"struct", llvm::json::Value(std::move(fields))},
               {"name", llvm::json::Value(structTy.getName())}});
        }
        return llvm::json::Object(
            {{"struct", llvm::json::Value(std::move(fields))}});
      }
      // It wasn't the top-level named struct, just emit the content
      return llvm::json::Object(
          {{"struct", llvm::json::Value(std::move(fields))}});
    }
    // Reference the previously- or elsewhere- defined named struct
    return llvm::json::Object({{"ref", llvm::json::Value(structTy.getName())}});
  }
  if (type.isArrayTy()) {
    const auto& arrayTy = llvm::cast<llvm::ArrayType>(type);
    return llvm::json::Object(
        {{"array", jsonTypeHelper(*arrayTy.getElementType())},
         {"array_size", llvm::json::Value(arrayTy.getArrayNumElements())}});
  }
  if (type.isIntegerTy()) {
    const auto& intTy = llvm::cast<llvm::IntegerType>(type);
    return llvm::json::Object(
        {{"int", llvm::json::Value(intTy.getBitWidth())}});
  }
  if (type.isFunctionTy()) {
    const auto& funTy = llvm::cast<llvm::FunctionType>(type);
    llvm::json::Array params;
    for (const auto& param : funTy.params()) {
      params.push_back(llvm::json::Value(jsonTypeHelper(*param)));
    }
    return llvm::json::Object(
        {{"function",
          llvm::json::Object(
              {{"parameters", llvm::json::Value(std::move(params))},
               {"return", jsonTypeHelper(*funTy.getReturnType())}})}});
  }
  if (type.isHalfTy()) {
    return llvm::json::Value("half");
  }
  if (type.isFloatTy()) {
    return llvm::json::Value("float");
  }
  if (type.isDoubleTy()) {
    return llvm::json::Value("double");
  }
  if (type.isX86_FP80Ty()) {
    return llvm::json::Value("X86_FP80");
  }
  if (type.isFP128Ty()) {
    return llvm::json::Value("FP128");
  }
  if (type.isLabelTy()) {
    return llvm::json::Value("label");
  }
  return llvm::json::Object(
      {{"unknown", llvm::json::Value(getPrettyType(type))}});
}  // namespace mate

// Structured JSON representations of LLVM types
static inline auto jsonType(const llvm::Type& type) -> llvm::json::Value {
  return jsonTypeHelper(type, true);
}

auto serializeLLVMType(
    llvm::Type& type, bool pretty_string, const llvm::DataLayout& dl)
    -> llvm::json::Object {
  llvm::json::Object payload{{"definition", jsonType(type)}};
  if (type.isSized()) {
    payload["size_in_bits"] = dl.getTypeSizeInBits(&type).getFixedSize();
    payload["store_size_in_bits"] =
        dl.getTypeStoreSizeInBits(&type).getFixedSize();
    payload["alloc_size_in_bits"] =
        dl.getTypeAllocSizeInBits(&type).getFixedSize();
    payload["abi_type_alignment"] = dl.getABITypeAlignment(&type);
  }
  if (pretty_string) {
    payload["pretty_string"] = getPrettyType(type);
  }
  return payload;
}

}  // namespace mate
