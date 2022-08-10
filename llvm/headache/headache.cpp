#include <llvm/IR/Intrinsics.h>

#include <sstream>
#include <tuple>
#include <unordered_map>
#include <unordered_set>

#include "llvm/ADT/StringSet.h"
#include "llvm/BinaryFormat/Dwarf.h"
#include "llvm/Demangle/Demangle.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/DebugInfoMetadata.h"
#include "llvm/IR/DerivedTypes.h"
#include "llvm/IR/Function.h"
#include "llvm/IR/GlobalVariable.h"
#include "llvm/IR/InstrTypes.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/IntrinsicInst.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/ValueSymbolTable.h"
#include "llvm/Pass.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/ErrorHandling.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/Path.h"
#include "llvm/Support/Process.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

static cl::opt<bool> EnableCUInfomation(
    "headache-cu-info",
    cl::Hidden,
    cl::desc("Enable compilation unit information retrieval"),
    cl::init(false));

static cl::opt<std::string> CUInformationOutput(
    "headache-cu-info-output",
    cl::Hidden,
    cl::desc("Compilation unit information output"),
    cl::init("headache.cu.json"));

static cl::opt<bool> EnableVariableTypeInfo(
    "headache-var-type-info",
    cl::Hidden,
    cl::desc("Enable variable type information retrieval"),
    cl::init(false));

static cl::opt<std::string> VariableInfoOutput(
    "headache-var-info-output",
    cl::Hidden,
    cl::desc("Variable information output"),
    cl::init("headache.vi.jsonl"));

static cl::opt<std::string> TypeInfoOutput(
    "headache-type-info-output",
    cl::Hidden,
    cl::desc("Type information output"),
    cl::init("headache.ti.jsonl"));

static cl::opt<std::string> LoggingOutput(
    "headache-logging-output",
    cl::Hidden,
    cl::Optional,
    cl::desc("Logging and diagnostic output"));

namespace {

using JObject = json::Object;
using JArray = json::Array;
using JValue = json::Value;
using VariableCache = std::unordered_set<const DILocalVariable *>;
using DITypeCache = std::unordered_set<const DIType *>;
using DITypeMap = std::unordered_map<const DIType *, std::string>;

// NOTE(ww): These are special sentinels, and **must** be kept synchronized
// with the DWARFTypeIDSentinel enumeration in MATE.
const std::string DWARF_TYPE_ID_NONE = "()";
const std::string DWARF_TYPE_ID_VOID = "(<void>)";
const std::string DWARF_TYPE_ID_VARARGS = "(<varargs>)";

enum class TypTag : char {
  Basic = 'b',
  SeenComposite = 'S',
  Struct = 's',
  Array = 'a',
  Enum = 'e',
  Union = 'u',
  Class = 'c',
  UnknownComposite = 'C',
  Derived = 'd',
  Function = 'f',
};

struct Headache : public ModulePass {
  static char ID;
  raw_fd_ostream *HeadacheCUStream{nullptr};
  raw_fd_ostream *HeadacheVIStream{nullptr};
  raw_fd_ostream *HeadacheTIStream{nullptr};
  raw_fd_ostream *HeadacheVerboseStream{nullptr};
  DITypeCache SeenComposites;
  // NOTE(ww): This only caches the top-level of each expandType invocation,
  // meaning that recursive cases like `(foo (bar)), (baz (bar))` require
  // `bar` to be expanded in full each time. This could probably be fixed by
  // turning the cache into a cache of DIT -> {TypKey, JValue} and performing
  // the actual caching step inside of each expandType call.
  DITypeMap SeenDITs;
  bool VoidTypeAlreadyEmitted{false};
  bool VariadicArgsAlreadyEmitted{false};

  Headache() : ModulePass(ID) {}

  auto doInitialization(Module &M) -> bool override {
    std::error_code StreamEC{};
    if (!LoggingOutput.empty()) {
      HeadacheVerboseStream = new raw_fd_ostream(
          LoggingOutput,
          StreamEC,
          sys::fs::CD_CreateAlways,
          sys::fs::FA_Write,
          sys::fs::OF_None);

      if (StreamEC) {
        report_fatal_error("Failed to open " + LoggingOutput, false);
      }
    }

    if (EnableCUInfomation) {
      HeadacheCUStream = new raw_fd_ostream(
          CUInformationOutput,
          StreamEC,
          sys::fs::CD_CreateAlways,
          sys::fs::FA_Write,
          sys::fs::OF_None);

      if (StreamEC) {
        report_fatal_error("Failed to open " + CUInformationOutput, false);
      }
    }

    if (EnableVariableTypeInfo) {
      HeadacheVIStream = new raw_fd_ostream(
          VariableInfoOutput,
          StreamEC,
          sys::fs::CD_CreateAlways,
          sys::fs::FA_Write,
          sys::fs::OF_None);
      if (StreamEC) {
        report_fatal_error("Failed to open " + VariableInfoOutput, false);
      }

      HeadacheTIStream = new raw_fd_ostream(
          TypeInfoOutput,
          StreamEC,
          sys::fs::CD_CreateAlways,
          sys::fs::FA_Write,
          sys::fs::OF_None);
      if (StreamEC) {
        report_fatal_error("Failed to open " + TypeInfoOutput, false);
      }
    }

    return false;
  }

  auto runOnModule(Module &M) -> bool override {
    if (EnableCUInfomation) {
      doEmitModuleCUInformation(M);
    }

    if (EnableVariableTypeInfo) {
      doEmitVariableTypeInformation(M);
      doEmitFunctionTypeInformation(M);
    }

    return false;
  }

  auto doFinalization(Module &M) -> bool override {
    if (EnableCUInfomation) {
      delete HeadacheCUStream;
    }

    if (EnableVariableTypeInfo) {
      delete HeadacheVIStream;
      delete HeadacheTIStream;
    }

    delete HeadacheVerboseStream;

    return false;
  }

 private:
  /* Returns a sensible name for the given DISubprogram, using the mangled
   * ("linkage") name first and falling back on `getName`.
   */
  static inline auto subprogramName(const llvm::DISubprogram *DISP)
      -> std::string {
    const auto name = DISP->getLinkageName();
    if (!name.empty()) {
      return name.str();
    }

    return DISP->getName().str();
  }

  inline void typKeyObjBegin(std::string &TypKey) { TypKey += "("; }

  inline void typKeyObjEnd(std::string &TypKey) {
    if (TypKey.back() == ' ') {
      TypKey.pop_back();
    }
    TypKey += ")";
  }

  inline void typKeyArrayBegin(std::string &TypKey) { TypKey += "["; }

  inline void typKeyNextItem(std::string &TypKey) { TypKey += " "; }

  inline void typKeyItem(TypTag Item, std::string &TypKey) {
    TypKey.push_back(static_cast<char>(Item));
    typKeyNextItem(TypKey);
  }

  inline void typKeyItem(const std::string &Item, std::string &TypKey) {
    TypKey += Item;
    typKeyNextItem(TypKey);
  }

  inline void typKeyArrayEnd(std::string &TypKey) {
    if (TypKey.back() == ' ') {
      TypKey.pop_back();
    }
    TypKey += "]";
  }

  auto DITypeNameOrAnonymous(const DIType *DIT) -> std::string {
    auto Name = DIT->getName();

    if (Name.empty()) {
      return "<anon>";
    }
    return Name.str();
  }

  auto pointerToID(const DIType *DIT) -> std::string {
    // NOTE(ww): Using pointers as IDs makes headache's output
    // non-deterministic. This would normally be a problem, but we specifically
    // exclude any keys that contains these IDs from the generated CPG JSONL and
    // (eventual) DB. See the NOTE in margin's emit_type_nodes_and_edges.
    auto addr = static_cast<const void *>(DIT);

    std::ostringstream oss;
    oss << addr;

    return oss.str();
  }

  auto verboses() -> raw_ostream & {
    if (HeadacheVerboseStream != nullptr) {
      return *HeadacheVerboseStream;
    }
    return nulls();
  }

  auto getSourceStem(const Module &M) -> StringRef {
    return sys::path::stem(M.getSourceFileName());
  }

  /* NOTE(ww): Stolen from Demangle.cpp (not present in LLVM 7).
   */
  static auto isItaniumEncoding(const std::string &MangledName) -> bool {
    size_t Pos = MangledName.find_first_not_of('_');
    // A valid Itanium encoding requires 1-4 leading underscores, followed by
    // 'Z'.
    return Pos > 0 && Pos <= 4 && MangledName[Pos] == 'Z';
  }

  void doEmitModuleCUInformation(const Module &M) {
    JArray CUs{};
    for (const auto *DICU : M.debug_compile_units()) {
      const auto *DIF = DICU->getFile();
      /* TODO(ww): There's a whole bunch of other information
       * here that we could potentially extract, but don't currently.
       * Some good future candidates:
       * 1. DICU->getEnumTypes()
       */
      CUs.push_back(JObject{
          {"source_language_id", DICU->getSourceLanguage()},
          {"source_language", dwarf::LanguageString(DICU->getSourceLanguage())},
          {"producer", DICU->getProducer()},
          {"flags", DICU->getFlags()},
          {"file",
           JObject{
               {"filename", DIF->getFilename()},
               {"directory", DIF->getDirectory()},
           }},
      });
    }

    JArray Externals{};
    for (const auto &VSTE : M.getValueSymbolTable()) {
      if (const auto *GV = dyn_cast<GlobalValue>(VSTE.second)) {
        /* NOTE(ww): Checking the "llvm." prefix here is dumb, but
         * HasLLVMReservedName is a protected member and I don't want to
         * specialize on llvm::Function instances here -- our externals could
         * include variables.
         */
        if (!GV->isDeclaration() || !GV->hasName() ||
            GV->getName().startswith("llvm.")) {
          continue;
        }

        Externals.push_back(JObject{
            {"name", GV->getName()},
            {"is_mangled", isItaniumEncoding(GV->getName())},
            {"demangled_name", demangle(GV->getName())},
        });
      }
    }

    JValue CUInfoJson = JObject{
        {"module_name", M.getName()},
        {"module_stem", sys::path::stem(M.getName())},
        {"source_file", M.getSourceFileName()},
        {"source_stem", getSourceStem(M)},
        {"target_triple", M.getTargetTriple()},
        {"data_layout", M.getDataLayoutStr()},
        {"cus", std::move(CUs)},
        {"externals", std::move(Externals)},
    };

    *HeadacheCUStream << CUInfoJson << '\n';
  }

  auto expandCommonTypeInfo(const DIType *DIT) -> JObject {
    if (DIT == nullptr) {
      return JObject{};
    }

    // NOTE(ww): Keep the format and contents of this object consistent with the
    // equivalent one in emitVoidType.
    return JObject{
        {"name", DIT->getName()},
        {"tag", dwarf::TagString(DIT->getTag())},
        {"size", ((int64_t)DIT->getSizeInBits()) / 8},
        {"align", DIT->getAlignInBytes()},
        {"offset", ((int64_t)DIT->getOffsetInBits()) / 8},
        // TODO(ww): Lots of other potentially useful boolean fields:
        // isObjectPointer, isStaticMember, isLValueReference, etc.
        {"forward_decl", DIT->isForwardDecl()},
        {"virtual", DIT->isVirtual()},
        {"artificial", DIT->isArtificial()},
    };
  }

  void expandCompositeStructure(
      const DICompositeType *DICT, JObject &Typ, std::string &TypKey) {
    typKeyObjBegin(TypKey);

    typKeyArrayBegin(TypKey);
    JArray Parents{};
    JArray Members{};
    for (const auto *E : DICT->getElements()) {
      if (E == nullptr) {
        continue;
      }

      const DIDerivedType *DIDT = nullptr;
      if (!(DIDT = dyn_cast<DIDerivedType>(E))) {
        verboses()
            << "Weird: expanding a struct with non-DIDerivedType elements?\n";
        continue;
      }

      JObject FieldTyp{};
      if (DIDT->getTag() == dwarf::DW_TAG_inheritance) {
        // NOTE(ww): See the NOTE in expandCompositeClass.
        auto FieldTypKey = expandType(DIDT->getBaseType(), FieldTyp);
        typKeyItem(FieldTypKey, TypKey);
        Parents.push_back(std::move(FieldTypKey));
      } else if (DIDT->getTag() == dwarf::DW_TAG_member) {
        auto FieldTypKey = expandType(DIDT, FieldTyp);
        typKeyItem(FieldTypKey, TypKey);
        Members.push_back(std::move(FieldTypKey));
      }
    }
    typKeyArrayEnd(TypKey);

    typKeyNextItem(TypKey);
    JObject BaseTyp{};
    auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
    typKeyItem(BaseTypKey, TypKey);

    Typ = JObject{
        {"kind", "structure"},
        {"cached_id", std::move(pointerToID(DICT))},
        {"common", std::move(expandCommonTypeInfo(DICT))},
        {"base_type", std::move(BaseTypKey)},
        {"parents", std::move(Parents)},
        {"members", std::move(Members)},
    };

    typKeyObjEnd(TypKey);
  }

  void expandCompositeArray(
      const DICompositeType *DICT, JObject &Typ, std::string &TypKey) {
    const DISubrange *DISR = nullptr;
    for (const auto *E : DICT->getElements()) {
      if (E == nullptr) {
        continue;
      }

      if (DISR != nullptr) {
        verboses() << "Weird: more than one DISubrange in the array?\n";
      }

      if (!(DISR = dyn_cast<DISubrange>(E))) {
        verboses()
            << "Weird: expanding an array with non-DISubrange elements?\n";
        continue;
      }
    }

    if (DISR == nullptr) {
      verboses() << "Very weird: no DISubrange for array?\n";
      return;
    }

    const auto &DISRCT = DISR->getCount();
    JObject Subrange{};
    if (const auto *Int = DISRCT.dyn_cast<ConstantInt *>()) {
      Subrange.insert({"count", Int->getSExtValue()});
    } else if (const auto *Var = DISRCT.dyn_cast<DIVariable *>()) {
      if (const auto *GV = dyn_cast<DIGlobalVariable>(Var)) {
        Subrange.insert(
            {"global_variable",
             JObject{
                 {"name", Var->getName()},
                 {"local_to_unit", GV->isLocalToUnit()},
                 {"display_name", GV->getDisplayName()},
                 {"linkage_name", GV->getLinkageName()},
             }});
      } else if (const auto *LV = dyn_cast<DILocalVariable>(Var)) {
        Subrange.insert(
            {"local_variable",
             JObject{
                 {"name", Var->getName()},
                 {"parameter", LV->isParameter()},
                 {"arg", LV->getArg()},
                 {"artificial", LV->isArtificial()},
                 {"object_pointer", LV->isObjectPointer()},
             }});
      } else {
        verboses() << "Very weird: DIVariable doesn't specialize as either "
                      "local or global?\n";
      }
    } else {
      verboses() << "Very weird: DISubrange represents count as neither "
                    "literal nor variable?\n";
      return;
    }

    JObject BaseTyp{};
    auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
    typKeyItem(BaseTypKey, TypKey);

    Typ = JObject{
        {"kind", "array"},
        {"common", std::move(expandCommonTypeInfo(DICT))},
        {"base_type", std::move(BaseTypKey)},
        {"subrange", std::move(Subrange)},
    };
  }

  void expandCompositeEnum(
      const DICompositeType *DICT, JObject &Typ, std::string &TypKey) {
    typKeyObjBegin(TypKey);

    typKeyArrayBegin(TypKey);
    JArray Enumerators{};
    for (const auto *E : DICT->getElements()) {
      if (E == nullptr) {
        continue;
      }

      const DIEnumerator *DIE = nullptr;
      if (!(DIE = dyn_cast<DIEnumerator>(E))) {
        verboses()
            << "Weird: expanding an enum with non-DIEnumerator elements?\n";
        continue;
      }

      Enumerators.push_back(JObject{
          {"name", DIE->getName()},
          {"value", DIE->getValue()},
          {"unsigned", DIE->isUnsigned()},
      });
      TypKey +=
          DIE->getName().str() + "{" + std::to_string(DIE->getValue()) + "}";
      typKeyNextItem(TypKey);
    }
    typKeyArrayEnd(TypKey);

    typKeyNextItem(TypKey);
    JObject BaseTyp{};
    auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
    typKeyItem(BaseTypKey, TypKey);

    Typ = JObject{
        {"kind", "enum"},
        {"common", std::move(expandCommonTypeInfo(DICT))},
        {"base_type", std::move(BaseTypKey)},
        {"enumerators", std::move(Enumerators)},
    };
    typKeyObjEnd(TypKey);
  }

  void expandCompositeUnion(
      const DICompositeType *DICT, JObject &Typ, std::string &TypKey) {
    /* NOTE(ww): Union handling is basically identical to struct handling;
     * we can probably dedupe the two.
     */
    typKeyObjBegin(TypKey);
    typKeyArrayBegin(TypKey);
    JArray Members{};
    for (const auto *E : DICT->getElements()) {
      const DIDerivedType *DIDT = nullptr;
      if (!(DIDT = dyn_cast_or_null<DIDerivedType>(E))) {
        verboses()
            << "Weird: expanding a union with non-DIDerivedType elements?\n";
        continue;
      }

      if (DIDT->getTag() != dwarf::DW_TAG_member) {
        verboses() << "Weird: unexpected union field tag: "
                   << dwarf::TagString(DIDT->getTag()) << '\n';
        continue;
      }

      JObject FieldTyp{};
      auto FieldTypKey = expandType(DIDT, FieldTyp);
      typKeyItem(FieldTypKey, TypKey);
      Members.push_back(std::move(FieldTypKey));
    }
    typKeyArrayEnd(TypKey);

    typKeyNextItem(TypKey);
    JObject BaseTyp{};
    auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
    typKeyItem(BaseTypKey, TypKey);

    Typ = JObject{
        {"kind", "union"},
        {"common", std::move(expandCommonTypeInfo(DICT))},
        {"base_type", std::move(BaseTypKey)},
        {"members", std::move(Members)},
    };
    typKeyObjEnd(TypKey);
  }

  void expandTemplateParameter(
      const DITemplateParameter *DITP, JObject &TParm, std::string &TypKey) {
    if (const auto *DITTP = dyn_cast<DITemplateTypeParameter>(DITP)) {
      const Metadata *TypMeta = DITTP->getType();
      std::string TTypKey;
      if (TypMeta != nullptr) {
        if (const auto *DIT = dyn_cast<DIType>(TypMeta)) {
          JObject TTyp{};
          TTypKey = expandType(DIT, TTyp);
        } else {
          TTypKey = noType();
          verboses() << "Weird: DITemplateTypeParameter type isn't a DIType?\n";
        }
      } else {
        // NOTE(ww): Not sure this can actually happen in well-formed IR.
        TTypKey = noType();
        verboses() << "Very weird: DITemplateValueParameter has no type "
                      "metadata at all!\n";
      }
      typKeyItem(TTypKey, TypKey);

      TParm = JObject{
          {"kind", "type_parameter"},
          {"name", DITTP->getName()},
          {"type", std::move(TTypKey)},
      };
    } else if (const auto *DITVP = dyn_cast<DITemplateValueParameter>(DITP)) {
      const Metadata *TypMeta = DITVP->getType();
      std::string TTypKey;
      if (TypMeta != nullptr) {
        if (const auto *DIT = dyn_cast<DIType>(TypMeta)) {
          JObject TTyp{};
          TTypKey = expandType(DIT, TTyp);
          verboses() << "TTypKey: " << TTypKey << '\n';
        } else {
          TTypKey = noType();
          verboses()
              << "Weird: DITemplateValueParameter type isn't a DIType?\n";
        }
      } else {
        // NOTE(ww): This seems to happen with some template value parameters in
        // the STL. I'm not sure why.
        TTypKey = noType();
        verboses()
            << "Weird: DITemplateValueParameter has no type metadata at all!\n";
      }
      typKeyItem(TTypKey, TypKey);

      /* NOTE(ww): DITypeTemplateValueParameters appear to correspond to
       * what C++ calls "non-type template parameters". Experimentally,
       * the values of these are represented in the IR either as Constants
       * (e.g. integral, character, constant string) or refererences
       * to a (potentially empty) list of DITemplateTypeParameters.
       * I don't fully understand the purpose of this second group yet;
       * we skip them below.
       */
      JObject TVal{};
      const Metadata *ValMeta = DITVP->getValue();
      if (ValMeta != nullptr) {
        if (const auto *CAM = dyn_cast<ConstantAsMetadata>(ValMeta)) {
          const auto *ValConst = CAM->getValue();
          /* C++ says that these values can be pretty much anything
           * constant/with a static storage duration. Boo.
           */
          if (const auto *CI = dyn_cast<ConstantInt>(ValConst)) {
            TVal.insert(
                {"int",
                 JObject{
                     {"value", CI->getSExtValue()},
                 }});
          } else if (
              const auto *CDS = dyn_cast<ConstantDataSequential>(ValConst)) {
            if (CDS->isString()) {
              TVal.insert(
                  {"string",
                   JObject{
                       {"value", CDS->getAsString()},
                   }});
            } else {
              JArray Elems{};
              for (auto i = 0; i < CDS->getNumElements(); i++) {
                // NOTE(ww): It's safe to assume that our elements are
                // integral here, since floating-point values aren't allowed
                // anywhere in non-type template parameters.
                Elems.push_back(CDS->getElementAsInteger(i));
              }
              TVal.insert({"array", JObject{{"value", std::move(Elems)}}});
            }
          } else {
            // TODO(ww): nontypetemplate in frontend/tests has some other
            // cases that we'll probably want to handle eventually:
            // pointers to constant global variables, pointers to members, &c.
            TVal.insert({"_unknown_constant", nullptr});
            verboses() << "Weird: unknown constant kind for template value: "
                       << ValConst << '\n';
          }
        } else {
          TVal.insert({"_unknown_value", nullptr});
          verboses() << "Weird: unknown non-constant kind for template value: "
                     << *ValMeta << '\n';
        }
      }

      TParm = JObject{
          {"kind", "value_parameter"},
          {"name", DITVP->getName()},
          {"type", std::move(TTypKey)},
          {"value", std::move(TVal)},
      };
    } else {
      verboses() << "Weird: expanding template parameters that aren't type or "
                    "value?\n";
    }
  }

  void expandCompositeClass(
      const DICompositeType *DICT, JObject &Typ, std::string &TypKey) {
    typKeyObjBegin(TypKey);

    typKeyArrayBegin(TypKey);
    JArray Parents{};
    JArray Members{};
    for (const auto *E : DICT->getElements()) {
      // TODO(ww): Also check for DISubprogram here, and figure out
      // an appropriate format for emitting information about a class's methods
      // and those methods' types. Likewise for expandCompositeStructure.
      const DIDerivedType *DIDT = nullptr;
      if (!(DIDT = dyn_cast_or_null<DIDerivedType>(E))) {
        verboses()
            << "Weird: expanding a class with non-DIDeivedType fields?\n";
        continue;
      }

      JObject FieldTyp{};
      if (DIDT->getTag() == dwarf::DW_TAG_inheritance) {
        // NOTE(ww): The derived type that wraps each parent type contains no
        // useful information and only gets in the way, so remove it.
        auto FieldTypKey = expandType(DIDT->getBaseType(), FieldTyp);
        typKeyItem(FieldTypKey, TypKey);
        Parents.push_back(std::move(FieldTypKey));
      } else if (DIDT->getTag() == dwarf::DW_TAG_member) {
        auto FieldTypKey = expandType(DIDT, FieldTyp);
        typKeyItem(FieldTypKey, TypKey);
        Members.push_back(std::move(FieldTypKey));
      } else {
        verboses() << "Weird: unexpected class field tag: "
                   << dwarf::TagString(DIDT->getTag()) << '\n';
      }
    }
    typKeyArrayEnd(TypKey);

    typKeyNextItem(TypKey);
    typKeyArrayBegin(TypKey);
    JArray TParams{};
    for (const auto *E : DICT->getTemplateParams()) {
      if (E == nullptr) {
        continue;
      }

      JObject TParm{};
      expandTemplateParameter(E, TParm, TypKey);
      TParams.push_back(std::move(TParm));
      typKeyNextItem(TypKey);
    }
    typKeyArrayEnd(TypKey);

    typKeyNextItem(TypKey);
    JObject BaseTyp{};
    auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
    typKeyItem(BaseTypKey, TypKey);

    Typ = JObject{
        {"kind", "class"},
        {"cached_id", std::move(pointerToID(DICT))},
        {"common", std::move(expandCommonTypeInfo(DICT))},
        {"base_type", std::move(BaseTypKey)},
        {"parents", std::move(Parents)},
        {"members", std::move(Members)},
        {"template_params", std::move(TParams)},
    };
    typKeyObjEnd(TypKey);
  }

  // A special helper for emitting the "none" (pseudo-)type.
  // This type exists to provide a sentinel for the end of a particular
  // chain of type expansions. It's equivalent to calling
  // expandType with a nullptr DIType.
  inline auto noType() -> std::string { return DWARF_TYPE_ID_NONE; }

  // A special helper for emitting the "void" (pseudo-)type.
  // Multiple calls only emit the type once, for consistency with the rest of
  // the type expansion/emission API.
  auto emitVoidType() -> std::string {
    if (VoidTypeAlreadyEmitted) {
      return DWARF_TYPE_ID_VOID;
    }

    VoidTypeAlreadyEmitted = true;

    JValue Typ = JObject{
        {"kind", "basic"},
        {"common",
         JObject{
             {"name", "void"},
             // NOTE(ww): DWARFv4 S.5.2 "Unspecified Type Entries":
             // DW_TAG_unspecified_type is the standard sentinel for "void" in
             // C/C++ programs.
             {"tag", "DW_TAG_unspecified_type"},
             {"size", 0},
             {"align", 0},
             {"offset", 0},
             {"forward_decl", false},
             {"virtual", false},
             {"artificial", false},
         }},
        {"unsigned", false},
    };

    JValue TIJson = JObject{
        {"type", std::move(Typ)},
        {"type_id", DWARF_TYPE_ID_VOID},
    };
    *HeadacheTIStream << TIJson << '\n';

    return DWARF_TYPE_ID_VOID;
  }

  // Like emitVoidType: This is a special helper for the variadic argument
  // signature in function (i.e. subroutine) types. LLVM represents this with a
  // nullptr, so we special-case it for emission.
  auto emitVarArgsType() -> std::string {
    if (VariadicArgsAlreadyEmitted) {
      return DWARF_TYPE_ID_VARARGS;
    }

    VariadicArgsAlreadyEmitted = true;

    JValue Typ = JObject{
        {"kind", "basic"},
        {"common",
         JObject{
             {"name", "..."},
             // NOTE(ww): DWARFv4 S.3.3.4 "Declarations Owned by Subroutines and
             // Entry Points": DW_TAG_unspecified_parameters is the standard
             // sentinel for "..." in C/C++ programs.
             {"tag", "DW_TAG_unspecified_parameters"},
             {"size", 0},
             {"align", 0},
             {"offset", 0},
             {"forward_decl", false},
             {"virtual", false},
             {"artificial", false},
         }},
        {"unsigned", false},
    };

    JValue TIJson = JObject{
        {"type", std::move(Typ)},
        {"type_id", DWARF_TYPE_ID_VARARGS},
    };

    *HeadacheTIStream << TIJson << '\n';
    return DWARF_TYPE_ID_VARARGS;
  }

  auto expandType(const DIType *DIT, JObject &Typ) -> std::string {
    const auto SeenDIT = SeenDITs.find(DIT);
    if (SeenDIT != SeenDITs.end()) {
      return SeenDIT->second;
    }

    std::string TypKey;
    // TODO(ww): Evaluate whether this is a sensible default reservation.
    TypKey.reserve(2048);
    typKeyObjBegin(TypKey);

    if (DIT != nullptr) {
      typKeyItem(DITypeNameOrAnonymous(DIT), TypKey);
      typKeyItem(std::to_string(DIT->getSizeInBits() / 8), TypKey);
      typKeyItem(std::to_string(DIT->getOffsetInBits() / 8), TypKey);
    }

    if (const auto *DIBT = dyn_cast_or_null<DIBasicType>(DIT)) {
      typKeyObjBegin(TypKey);
      typKeyItem(TypTag::Basic, TypKey);
      auto Unsigned =
          DIBT->getSignedness().getValueOr(DIBasicType::Signedness::Unsigned) ==
          DIBasicType::Signedness::Unsigned;
      Typ = JObject{
          {"kind", "basic"},
          {"common", std::move(expandCommonTypeInfo(DIBT))},
          {"unsigned", Unsigned},
      };
      typKeyObjEnd(TypKey);
    } else if (const auto *DICT = dyn_cast_or_null<DICompositeType>(DIT)) {
      typKeyObjBegin(TypKey);
      if (SeenComposites.count(DICT)) {
        typKeyItem(TypTag::SeenComposite, TypKey);
        Typ = JObject{
            {"kind", "composite_cached"},
            {"cached_id", std::move(pointerToID(DICT))},
            {"name", DICT->getName()},
            {"common", std::move(expandCommonTypeInfo(DICT))},
        };
      } else {
        /* NOTE(ww): There's no point in tracking them anonymous composite:
         * we're chiefly interested in composites that contain recursive
         * defintions, and that isn't possible with an anonymous composite.
         */
        if (!DICT->getName().empty()) {
          SeenComposites.insert(DICT);
        }

        switch (DICT->getTag()) {
          case dwarf::DW_TAG_structure_type: {
            typKeyItem(TypTag::Struct, TypKey);
            expandCompositeStructure(DICT, Typ, TypKey);
            break;
          }
          case dwarf::DW_TAG_array_type: {
            typKeyItem(TypTag::Array, TypKey);
            expandCompositeArray(DICT, Typ, TypKey);
            break;
          }
          case dwarf::DW_TAG_enumeration_type: {
            typKeyItem(TypTag::Enum, TypKey);
            expandCompositeEnum(DICT, Typ, TypKey);
            break;
          }
          case dwarf::DW_TAG_union_type: {
            typKeyItem(TypTag::Union, TypKey);
            expandCompositeUnion(DICT, Typ, TypKey);
            break;
          }
          case dwarf::DW_TAG_class_type: {
            typKeyItem(TypTag::Class, TypKey);
            expandCompositeClass(DICT, Typ, TypKey);
            break;
          }
          default: {
            verboses() << "Generic DICompositeType handler for "
                       << dwarf::TagString(DICT->getTag()) << '\n';

            typKeyItem(TypTag::UnknownComposite, TypKey);

            typKeyArrayBegin(TypKey);
            JArray SubTyps{};
            for (auto *E : DICT->getElements()) {
              if (const auto *DIT = dyn_cast_or_null<DIType>(E)) {
                JObject SubTyp{};
                auto SubTypKey = expandType(DIT, SubTyp);
                typKeyItem(SubTypKey, TypKey);
                SubTyps.push_back(std::move(SubTypKey));
              }
            }
            typKeyArrayEnd(TypKey);

            typKeyNextItem(TypKey);
            JObject BaseTyp{};
            auto BaseTypKey = expandType(DICT->getBaseType(), BaseTyp);
            typKeyItem(BaseTypKey, TypKey);

            Typ = JObject{
                {"kind", "composite"},
                {"common", std::move(expandCommonTypeInfo(DICT))},
                {"base_type", std::move(BaseTypKey)},
                {"elements", std::move(SubTyps)},
            };
          }
        }
      }

      typKeyObjEnd(TypKey);
    } else if (const auto *DIDT = dyn_cast_or_null<DIDerivedType>(DIT)) {
      typKeyObjBegin(TypKey);

      typKeyItem(TypTag::Derived, TypKey);
      typKeyObjBegin(TypKey);
      typKeyItem(dwarf::TagString(DIDT->getTag()).str(), TypKey);

      const auto *DIT = DIDT->getBaseType();
      std::string BaseTypKey;
      if (DIT != nullptr) {
        JObject BaseTyp{};
        BaseTypKey = expandType(DIT, BaseTyp);
      } else {
        // NOTE(ww): Special case: a derived type that has a nullptr for its
        // base type is treated as having void for its base, using a special
        // sentinel.
        BaseTypKey = emitVoidType();
      }

      typKeyItem(BaseTypKey, TypKey);
      typKeyObjEnd(TypKey);

      Typ = JObject{
          {"kind", "derived"},
          {"common", std::move(expandCommonTypeInfo(DIDT))},
          {"base_type", std::move(BaseTypKey)},
      };

      typKeyObjEnd(TypKey);
    } else if (const auto *DIST = dyn_cast_or_null<DISubroutineType>(DIT)) {
      typKeyObjBegin(TypKey);
      typKeyItem(TypTag::Function, TypKey);

      const auto &DITRA = DIST->getTypeArray();
      if (DITRA.size() == 0) {
        // NOTE(ww): Special sentinel for void return.
        const auto RetTypKey = emitVoidType();
        typKeyItem(RetTypKey, TypKey);

        // NOTE(ww): Empty array for empty parameter list.
        typKeyArrayBegin(TypKey);
        typKeyArrayEnd(TypKey);

        Typ = JObject{
            {"kind", "subroutine"},
            {"common", std::move(expandCommonTypeInfo(DIST))},
            {"params", JArray{}},
            {"return", RetTypKey},
        };
      } else {
        std::string RetTypKey;
        const auto *RetDIT = DITRA[0];
        if (RetDIT == nullptr) {
          RetTypKey = emitVoidType();
        } else {
          JObject RetTyp{};
          RetTypKey = expandType(RetDIT, RetTyp);
        }
        typKeyItem(RetTypKey, TypKey);

        typKeyArrayBegin(TypKey);
        JArray ParamTyps{};
        for (int i = 1; i < DITRA.size(); ++i) {
          std::string ParamTypKey;
          const auto *ParamDIT = DITRA[i];
          if (ParamDIT == nullptr && i == DITRA.size() - 1) {
            // NOTE(ww): A nullptr as the last member of the parameter list
            // indicates variadic arguments.
            ParamTypKey = emitVarArgsType();
          } else {
            // A nullptr shouldn't occur anywhere in the list except at the end
            // (as special-cased above), so warn if we see one.
            if (ParamDIT == nullptr) {
              verboses() << "Weird: nullptr DIType in parameter list, but not "
                            "at the end?\n";
            }
            JObject ParamTyp{};
            ParamTypKey = expandType(ParamDIT, ParamTyp);
          }
          typKeyItem(ParamTypKey, TypKey);
          ParamTyps.push_back(std::move(ParamTypKey));
        }
        typKeyArrayEnd(TypKey);

        Typ = JObject{
            {"kind", "subroutine"},
            {"common", std::move(expandCommonTypeInfo(DIST))},
            {"params", std::move(ParamTyps)},
            {"return", std::move(RetTypKey)},
        };
      }

      typKeyObjEnd(TypKey);
    } else if (DIT == nullptr) {
      // NOTE(ww): expandType was passed a nullptr, meaning that we drilled down
      // to a type that doesn't actually have a base type. Don't warn, since
      // this is a common occurrence (e.g., for a plain old structure).
    } else {
      verboses() << "weird: unknown DIType?\n";
    }

    typKeyObjEnd(TypKey);
    SeenDITs.insert({DIT, TypKey});

    JValue TIJson = JObject{
        {"type", std::move(Typ)},
        {"type_id", TypKey},
    };
    *HeadacheTIStream << TIJson << '\n';

    return TypKey;
  }

  void expandScope(const DIScope *DIS, JObject &Scope) {
    if (DIS == nullptr) {
      return;
    }

    /* NOTE(ww): If our scope is a subprogram (i.e., a function scope),
     * grab its associated linkage name. This is crucial for unambiguous
     * pairing with aspirin's output, since aspirin needs to disambiguate
     * this implicit `*this` parameters of various methods whose pre-mangled
     * names may be ambiguous (e.g., due to overloading).
     */
    if (const auto *DISP = dyn_cast_or_null<DISubprogram>(DIS)) {
      Scope.try_emplace("linkage_name", DISP->getLinkageName());
    }

    /* NOTE(ww): If our scope is a lexical block, grab its associated line
     * and column numbers. This is *also* crucial for unambiguous pairing,
     * this time at the IR mapping layer, when multiple entities have the same
     * line but different scopes (e.g. due to macro expansion).
     */
    if (const auto *DILB = dyn_cast_or_null<DILexicalBlock>(DIS)) {
      Scope.try_emplace("line", DILB->getLine());
      Scope.try_emplace("column", DILB->getColumn());
    }

    Scope.try_emplace("filename", DIS->getFilename());
    Scope.try_emplace("directory", DIS->getDirectory());
    Scope.try_emplace("name", DIS->getName());
    Scope.try_emplace("tag", dwarf::TagString(DIS->getTag()));

    if (const auto *PDIS = DIS->getScope()) {
      JObject ParentScope{};
      expandScope(PDIS, ParentScope);
      Scope.try_emplace("parent_scope", std::move(ParentScope));
    }
  }

  void expandLocation(
      const BasicBlock &BB,
      const DILocalVariable *DILV,
      const DILocation *DIL,
      JObject &Location) {
    Location.try_emplace("bb_operand", BB.getName());
    Location.try_emplace("llvm_func_name", BB.getParent()->getName());
    Location.try_emplace(
        "func_name", subprogramName(DILV->getScope()->getSubprogram()));

    auto line = DIL->getLine();
    auto column = DIL->getColumn();
    auto probably_optimized_away = false;

    // NOTE(ww): As of LLVM 10, DILocations are a little less reliable: LLVM
    // can choose to zero them out when the corresponding variable has been
    // optimized out entirely. Similarly, if LLVM is unable to reconcile two
    // DILocations after an optimization, it will zero them out and choose
    // the scope of an arbitrary one.
    // LLVM doesn't provide a reliable way to detect that this has occurred,
    // other than checking to see whether the DILocation is (0, 0).
    // We fall back to the line information stored in the DILocalVariable when
    // we see this, since it's more reliable.
    // We check whether the corresponding local variable is artificial first,
    // since compiler-inserted local variables won't have source location
    // information but aren't actually optimized away.
    if (!DILV->isArtificial() && line == 0 && column == 0) {
      verboses()
          << "Found a local variable that was probably optimized out entirely: "
          << DILV->getName() << '\n';

      probably_optimized_away = true;
      line = DILV->getLine();
    }

    Location.try_emplace("probably_optimized_away", probably_optimized_away);
    Location.try_emplace("line", line);
    Location.try_emplace("column", column);

    if (DIL = dyn_cast_or_null<DILocation>(DIL->getInlinedAt())) {
      const auto *DIS = cast<DIScope>(DIL->getRawScope());
      JObject Scope{};
      expandScope(DIS, Scope);

      JObject InlinedLoc{
          {"line", DIL->getLine()},
          {"column", DIL->getColumn()},
          {"source_scope", std::move(Scope)},
      };
      Location.try_emplace("inlined_at", std::move(InlinedLoc));
    }
  }

  void doEmitGlobalVTI(const DIGlobalVariable *DIGV) {
    const DIScope *DIS = nullptr;
    if (!(DIS = DIGV->getScope())) {
      verboses() << "Weird: couldn't get scope for global variable?\n";
      return;
    }

    JObject Scope{};
    expandScope(DIS, Scope);

    const DIFile *DIF = nullptr;
    if (!(DIF = DIGV->getFile())) {
      verboses() << "Weird: couldn't get definition file for global?\n";
      return;
    }

    const DIType *DIT = nullptr;
    if (!(DIT = DIGV->getType())) {
      verboses() << "Weird: DIGlobalVariable with no type?\n";
      return;
    }

    JObject Typ{};
    std::string TypKey = expandType(DIT, Typ);

    JValue VIJson = JObject{
        {"kind", "global"},
        {"name", DIGV->getDisplayName()},
        {"linkage_name", DIGV->getLinkageName()},
        {"local_to_unit", DIGV->isLocalToUnit()},
        {"definition", DIGV->isDefinition()},
        {"source_scope", std::move(Scope)},
        {"type_id", std::move(TypKey)},
        {"definition_location",
         JObject{
             {"filename", DIF->getFilename()},
             {"directory", DIF->getDirectory()},
             {"line", DIGV->getLine()},
         }},
    };

    *HeadacheVIStream << VIJson << '\n';
  }

  void doEmitLocalVTI(
      const BasicBlock &BB,
      const DbgVariableIntrinsic *DVI,
      VariableCache &FunctionLocals) {
    const DILocalVariable *DILV = nullptr;
    if (!(DILV = DVI->getVariable())) {
      verboses() << "Weird: couldn't get local variable assoicated with dbg "
                    "intrinsic?\n";
      return;
    }

    if (FunctionLocals.count(DILV)) {
      return;
    }
    FunctionLocals.insert(DILV);

    const DILocalScope *DILS = nullptr;
    if (!(DILS = DILV->getScope())) {
      verboses()
          << "Weird: couldn't get scope associated with DILocalVariable?\n";
      return;
    }

    JObject Scope{};
    expandScope(DILS, Scope);

    JObject Location{};
    expandLocation(BB, DILV, DVI->getDebugLoc().get(), Location);

    const DIType *DIT = nullptr;
    if (!(DIT = DILV->getType())) {
      verboses() << "Weird: DILocalVariable with no type?\n";
      return;
    }

    std::string TypKey;
    const auto SeenDIT = SeenDITs.find(DIT);
    if (SeenDIT != SeenDITs.end()) {
      TypKey = SeenDIT->second;
    } else {
      JObject Typ{};
      TypKey = expandType(DIT, Typ);
    }

    JValue VIJson = JObject{
        {"kind", "local"},
        {"source_location", std::move(Location)},
        {"parameter", DILV->isParameter()},
        {"arg", DILV->getArg()},
        {"name", DILV->getName()},
        {"artificial", DILV->isArtificial()},
        {"source_scope", std::move(Scope)},
        {"type_id", std::move(TypKey)},
    };

    *HeadacheVIStream << VIJson << '\n';
  }

  void doEmitFunctionTypeInformation(const Module &M) {
    for (const auto &F : M) {
      if (!F.hasName()) {
        verboses()
            << "weird: Function does not have name so cannot link type info\n";
        continue;
      }
      const auto DISub = F.getSubprogram();
      if (!DISub) {
        verboses() << "weird: Function does not have DISubprogram( "
                   << F.getName() << ")";
        continue;
      }
      auto const DIST = DISub->getType();

      // expandType will emit the TypeObj to the TIStream to be created as a
      // node. We save the TypKey (type_id) and pair it with the function name
      // so that the DwarfType can be paired with the Function by name later.
      JObject Typ{};
      auto const TypKey = expandType(DIST, Typ);
      const auto name = F.getName();

      JValue FIJson = JObject{
          {"kind", "function"}, {"func_name", name}, {"type_id", TypKey}};

      *HeadacheVIStream << FIJson << "\n";
    }
  }

  void doEmitVariableTypeInformation(const Module &M) {
    /* Global variables.
     */
    for (const auto *DICU : M.debug_compile_units()) {
      for (const auto *DIGVE : DICU->getGlobalVariables()) {
        const auto *DIGV = DIGVE->getVariable();
        doEmitGlobalVTI(DIGV);
      }
    }

    /* Local variables.
     */
    for (const auto &F : M) {
      VariableCache FunctionLocals;
      for (const auto &BB : F) {
        for (const auto &I : BB) {
          const DbgVariableIntrinsic *DVI = nullptr;
          if (!(DVI = dyn_cast<DbgVariableIntrinsic>(&I))) {
            continue;
          }

          doEmitLocalVTI(BB, DVI, FunctionLocals);
        }
      }
    }
  }
};
}  // namespace

char Headache::ID = 0;
static RegisterPass<Headache> X("headache", "Headache pass", true, false);
