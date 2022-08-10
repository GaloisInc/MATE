#pragma once

#include "llvm/Demangle/Demangle.h"
#include "llvm/IR/CallSite.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/Instructions.h"
#include "llvm/Support/SHA1.h"

namespace mate {
auto asCallSite(const llvm::Instruction& instruction)
    -> llvm::Optional<const llvm::ImmutableCallSite>;
auto asCallSite(const llvm::Value& value)
    -> llvm::Optional<const llvm::ImmutableCallSite>;

static inline __attribute__((unused)) auto hexstring(const std::string& input)
    -> std::string {
  // NOLINTNEXTLINE(modernize-avoid-c-arrays)
  static const char hex_digits[] = "0123456789abcdef";

  std::string output;
  output.reserve(input.length() * 2);
  for (auto& c : input) {
    output.push_back(hex_digits[static_cast<unsigned char>(c) >> 4]);
    output.push_back(hex_digits[static_cast<unsigned char>(c) & 15]);
  }
  return output;
}

static inline __attribute__((unused)) auto hexstring(
    const char* input, size_t length) -> std::string {
  // NOLINTNEXTLINE(modernize-avoid-c-arrays)
  static const char hex_digits[] = "0123456789abcdef";

  std::string output;
  output.reserve(length * 2);

  for (size_t i = 0; i < length; i++) {
    auto c = static_cast<unsigned char>(input[i]);
    output.push_back(hex_digits[static_cast<unsigned char>(c) >> 4]);
    output.push_back(hex_digits[static_cast<unsigned char>(c) & 15]);
  }
  return output;
}

/* NOTE(ww): Stolen from Demangle.cpp (not present in LLVM 7).
 */
static inline __attribute__((unused)) auto is_itanium_encoding(
    const std::string& MangledName) -> bool {
  size_t Pos = MangledName.find_first_not_of('_');
  // A valid Itanium encoding requires 1-4 leading underscores, followed by
  // 'Z'.
  return Pos > 0 && Pos <= 4 && MangledName[Pos] == 'Z';
}

/* NOTE(ww): As above, adapted from a later version of Demangle.cpp.
 */
static inline __attribute__((unused)) auto demangle_symbol(
    const std::string& MangledName) -> std::string {
  char* Demangled = nullptr;

  /* TODO(ww): Re-intro MS demangling here.
   */
  if (is_itanium_encoding(MangledName)) {
    Demangled =
        llvm::itaniumDemangle(MangledName.c_str(), nullptr, nullptr, nullptr);
  }

  if (Demangled == nullptr) {
    return MangledName;
  }

  std::string Ret = Demangled;
  free(Demangled);
  return Ret;
}

/* Returns a sensible name for the given DISubprogram, using the mangled
 * ("linkage") name first and falling back on `getName`.
 */
static inline __attribute__((unused)) auto subprogramName(
    const llvm::DISubprogram& DISP) -> std::string {
  const auto name = DISP.getLinkageName();
  if (!name.empty()) {
    return name.str();
  }

  return DISP.getName().str();
}

/* Returns a unique "compressed ID" for some source location within a function.
 *
 * This ID is deemed "compressed" because it's shorter than the fully
 * disambiguated form (source file + function name + line + column) would be,
 * but it's still relatively lengthy (SHA1 hash = 20 bytes -> 40 bytes as a
 * hexstring).
 *
 * We need these compressed IDs to resolve function-level ambiguities when
 * pairing LLVM-level program features with their debug, middle-end, and binary
 * counterparts. In particular: LLVM has internal disambiguation rules for
 * functions and other globally addressable names. These rules involve adding
 * numeric suffixes to addressable symbols, which means that they no longer
 * match the information available in the debug information or a user's
 * intuition about the function name they're querying for.
 *
 * To give ourselves the uniqueness we need, we
 * use the **ambiguous** form of the function name (no suffix), combined with
 * the translation unit information available in the debug information, combined
 * additionally with the line and column numbers of the source feature that
 * we're trying to uniquely locate.
 *
 * Why are `line` and `col` seperate from `DebugLoc`, you might ask? See the
 * first NOTE in addVariableLocationToJSON (Serialize/Nodes.cpp): DebugLoc isn't
 * always reliable, so we pass in versions that we know are (mostly) good
 * instead.
 *
 * The body of this function (i.e., the ID generation technique) **must** be
 * kept up-to-date with the `_compressed_id` function in
 * `mate.build.tob_chess_utils.tools.margin`, as the convention between the two
 * assures accurate mapping between IR and debug/machine level variable
 * information.
 */
static inline __attribute__((unused)) auto compressedScopeID(
    const std::string& func,
    const llvm::DebugLoc& location,
    unsigned line,
    unsigned col,
    unsigned scope_line,
    unsigned scope_col) -> std::string {
  std::string input = func + ":" + location->getDirectory().str() + ":" +
                      location->getFilename().str() + ":" +
                      std::to_string(line) + ":" + std::to_string(col) + ":" +
                      std::to_string(scope_line) + ":" +
                      std::to_string(scope_col);

  auto hasher = llvm::SHA1();
  hasher.update(llvm::StringRef(input));

  const auto hashed = hasher.final();

  return hexstring(hashed.data(), hashed.size());
}
};  // namespace mate
