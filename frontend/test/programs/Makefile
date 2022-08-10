CPROGS := $(basename $(wildcard *.c))
CXXPROGS := $(basename $(wildcard *.cpp))

MATE_OUT ?= $(shell realpath ../../../.out)
OUT := $(MATE_OUT)/build/tests

LLC := $(LLVM_BIN)/llc
OPT := $(LLVM_BIN)/opt
LLCFLAGS := -O0 -march=x86-64
OPTFLAGS := \
	-load $(MATE_BDIST_ROOT)/local/lib/LLVMHeadache.so

CC := clang
CXX := clang++
CFLAGS := -O0 -g3 -grecord-gcc-switches -Werror=implicit-function-declaration
CXXFLAGS := $(CFLAGS)

CFLAGS_SHORT := $(shell echo $(CFLAGS) | sed 's/ //g')

SEP := .
C_SUFFIX := $(SEP)$(CC)$(SEP)$(CFLAGS_SHORT)
CXX_SUFFIX := $(SEP)$(CXX)$(SEP)$(CFLAGS_SHORT)

CPROGS_WITH_SUFFIX := $(addprefix $(OUT)/, $(CPROGS:=$(C_SUFFIX)))
CXXPROGS_WITH_SUFFIX := $(addprefix $(OUT)/, $(CXXPROGS:=$(CXX_SUFFIX)))
PROGS_WITH_SUFFIX := $(CPROGS_WITH_SUFFIX) $(CXXPROGS_WITH_SUFFIX)

C_BINARIES := $(CPROGS_WITH_SUFFIX:=.bin)
CXX_BINARIES := $(CXXPROGS_WITH_SUFFIX:=.bin)
BINARIES := $(C_BINARIES) $(CXX_BINARIES)

C_BITCODE := $(CPROGS_WITH_SUFFIX:=.bc)
CXX_BITCODE := $(CXXPROGS_WITH_SUFFIX:=.bc)
LLVM_BITCODE_FILES := $(C_BITCODE) $(CXX_BITCODE)
C_LL := $(CPROGS_WITH_SUFFIX:=.ll)
CXX_LL := $(CXXPROGS_WITH_SUFFIX:=.ll)
LLVM_IR_FILES := $(C_LL) $(CXX_LL)

MARGIN_WALKER := python3 -m mate.build.tob_chess_utils.tools.margin
MIGRANE := python3 -m mate.build.tob_chess_utils.tools.migraine
ASPIRIN := python3 -m mate.build.tob_chess_utils.tools.aspirin

MARGIN_OUT := $(PROGS_WITH_SUFFIX:=.margin.jsonl)
ASPIRIN_FILES := $(PROGS_WITH_SUFFIX:=.aspirin.jsonl)
WEDLOCK_FILES := $(PROGS_WITH_SUFFIX:=.wedlock.jsonl)
WEDLOCK_LOG_FILES := $(PROGS_WITH_SUFFIX:=.wedlock.log)
ASM_FILES := $(PROGS_WITH_SUFFIX:=.s)
MIGRAINE_ASM_FILES := $(PROGS_WITH_SUFFIX:=.migraine.s)
HEADACHE_FILES := $(PROGS_WITH_SUFFIX:=.headache.bc)
HEADACHE_CU_FILES := $(PROGS_WITH_SUFFIX:=.cu.json)
NOMINA_BC_FILES := $(PROGS_WITH_SUFFIX:=.nomina.bc)
HEADACHE_VI_FILES := $(PROGS_WITH_SUFFIX:=.vi.jsonl)
HEADACHE_TI_FILES := $(PROGS_WITH_SUFFIX:=.ti.jsonl)
HEADACHE_LOG_FILES := $(PROGS_WITH_SUFFIX:=.headache.log)

%.ll: %.bc
	llvm-dis $(basename $@).bc

$(OUT):
	mkdir -p $(OUT)

$(C_BITCODE): $(OUT)
	$(CC) $(CFLAGS) -emit-llvm -o $@ -c $(notdir $(basename $(basename $(basename $@)))).c

$(CXX_BITCODE): $(OUT)
	$(CXX) $(CXXFLAGS) -emit-llvm -o $@ -c $(notdir $(basename $(basename $(basename $@)))).cpp

$(MARGIN_OUT): $(HEADACHE_TI_FILES) $(HEADACHE_CU_FILES) $(WEDLOCK_FILES) $(ASPIRIN_FILES)
	$(MARGIN_WALKER) $(MARGINFLAGS) \
		--sanity_checks \
		-w $(basename $(basename $@)).wedlock.jsonl \
		-a $(basename $(basename $@)).aspirin.jsonl \
		-t $(basename $(basename $@)).ti.jsonl \
		-c $(basename $(basename $@)).cu.json \
		-o $(basename $(basename $@)).margin.jsonl \

$(MIGRAINE_ASM_FILES): $(WEDLOCK_FILES)
	$(MIGRANE) \
		-w $(basename $(basename $@)).wedlock.jsonl \
		-o $(basename $(basename $@)).migraine.spatch
	cat \
		$(basename $(basename $@)).s \
		$(basename $(basename $@)).migraine.spatch \
		> $(basename $(basename $@)).migraine.s
	rm $(basename $(basename $@)).migraine.spatch

$(WEDLOCK_FILES): $(HEADACHE_FILES)
	$(LLC) $(LLCFLAGS) \
		-wedlock \
		-wedlock-output $(basename $(basename $@)).wedlock.jsonl \
		-wedlock-logging-output $(basename $(basename $@)).wedlock.log \
		$(basename $(basename $@)).headache.bc \
		-o $(basename $(basename $@)).s

# NOTE(ww): These are produced implicitly above, and marked explicitly here.
# See the $(HEADACHE_FILES) target below for another example + explanation.
$(ASM_FILES): $(WEDLOCK_FILES)

$(ASPIRIN_FILES): $(HEADACHE_VI_FILES) $(C_BINARIES) $(CXX_BINARIES)
	$(ASPIRIN) \
		-b $(basename $(basename $@)).bin \
		-H $(basename $(basename $@)).vi.jsonl \
		-o $(basename $(basename $@)).aspirin.jsonl

$(C_BINARIES): $(MIGRAINE_ASM_FILES) $(OUT)
	$(CC) $(COMMON_FLAGS) $(basename $@).migraine.s -o $@

$(CXX_BINARIES): $(MIGRAINE_ASM_FILES) $(OUT)
	$(CXX) $(COMMON_FLAGS) $(basename $@).migraine.s -o $@

$(HEADACHE_FILES): $(NOMINA_BC_FILES)
	$(OPT) $(OPTFLAGS) \
		-headache \
		-headache-cu-info \
		-headache-cu-info-output $(basename $(basename $@)).cu.json \
		-headache-var-type-info \
		-headache-var-info-output $(basename $(basename $@)).vi.jsonl \
		-headache-type-info-output $(basename $(basename $@)).ti.jsonl \
		-headache-logging-output $(basename $(basename $@)).headache.log \
		$(basename $(basename $@)).nomina.bc \
		-o $(basename $(basename $@)).headache.bc

# NOTE(ww): This prevents `make` from (incorrectly) parallelizing the construction
# of the various headache outputs.
$(HEADACHE_CU_FILES) $(HEADACHE_VI_FILES) $(HEADACHE_TI_FILES): $(HEADACHE_FILES)

$(NOMINA_BC_FILES): $(LLVM_IR_FILES)
	$(OPT) \
		-load $(MATE_BDIST_ROOT)/local/lib/LLVMNomina.so \
		-nomina \
		$(basename $(basename $@)).ll \
		-o $(basename $(basename $@)).nomina.bc

.PHONY: build
build: $(BINARIES)

.PHONY: all
all: $(LLVM_IR_FILES) $(MARGIN_OUT)

.PHONY: clean
clean:
	rm -rf __pycache__
	rm -f *.bc
	rm -f *.ll
	rm -f \
		$(MARGIN_OUT) \
		$(ASPIRIN_FILES) $(WEDLOCK_FILES) $(WEDLOCK_LOG_FILES) $(LLVM_BITCODE_FILES) \
		$(ASM_FILES) $(MIGRAINE_ASM_FILES) $(HEADACHE_FILES) \
		$(C_BINARIES) $(CXX_BINARIES) $(LLVM_IR_FILES) $(NOMINA_BC_FILES) \
		$(HEADACHE_CU_FILES) $(HEADACHE_VI_FILES) $(HEADACHE_TI_FILES) \
		$(HEADACHE_LOG_FILES)

.PHONY: fmt
fmt:
	clang-format -i -style=file *.c *.cpp *.h
