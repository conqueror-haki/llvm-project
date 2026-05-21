# AGENTS.md — LLVM Project

## Build system

- **CMake source dir is `llvm/`, NOT the repo root.** Use `cmake -S llvm -B <build>`.
- In-source builds are forbidden. Always build in a separate directory.
- Existing build dir: `build/` (Release, Clang only, BPF target only, no assertions).

### Configure

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_ENABLE_PROJECTS="clang;lld"
```

### Build

```bash
ninja -C build                    # build everything
ninja -C build llc opt clang      # build specific targets
```

### Key CMake variables

| Variable | Effect | Default |
|---|---|---|
| `LLVM_ENABLE_PROJECTS` | Projects to build (semicolon-separated) | `""` |
| `LLVM_ENABLE_RUNTIMES` | Runtimes to bootstrap (libcxx, compiler-rt, etc.) | `""` |
| `LLVM_TARGETS_TO_BUILD` | Architectures to build (`all` or `X86;AArch64;...`) | `all` |
| `LLVM_OPTIMIZED_TABLEGEN` | Build optimized TableGen even in Debug (saves time) | `OFF` |
| `LLVM_USE_LINKER` | `lld`, `gold`, etc. | system default |
| `LLVM_PARALLEL_LINK_JOBS` | Limit concurrent link jobs (memory saver) | unlimited |
| `LLVM_CCACHE_BUILD` | Enable ccache | `OFF` |

## Testing

Tests use **lit** (+ **FileCheck** for output verification). Unit tests use **Google Test**.

### Run all tests

```bash
ninja -C build check-all
```

### Run project-specific tests

```bash
ninja -C build check-llvm              # LLVM core
ninja -C build check-clang             # Clang
ninja -C build check-lld               # LLD
ninja -C build check-llvm-unit         # LLVM unit tests only
```

### Run a single test or directory

```bash
./build/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/add.ll
./build/bin/llvm-lit -sv llvm/test/CodeGen/X86/
./build/bin/llvm-lit -sv --filter 'MyPass' llvm/test/
```

- `-s` = succinct (suppress passing tests), `-v` = verbose (show commands), `-a` = show all output.
- Default lit args in targets: `-sv`.

### Test file conventions

- Tests use `RUN:` lines with `FileCheck` for assertion checking.
- Substitutions: `%s` = source file path, `%t` = temp file, `%S` = source dir.
- `REQUIRES:` / `UNSUPPORTED:` / `XFAIL:` constrain test execution.
- **Pipe input via stdin** (`opt < %s`) not path argument, to avoid ModuleID differences in output.
- **Never use `grep`** in test `RUN:` lines (legacy, poorly supported).

## Code style

- Clang-format: `BasedOnStyle: LLVM`, LF line endings. Run `git-clang-format` against `main`.
- CI checks formatting via `.github/workflows/pr-code-format.yml`.
- No MCP or agent-specific config files exist; this is the only instruction file.

## Major directories

| Directory | Purpose |
|---|---|
| `llvm/` | Core LLVM: IR, codegen, analyses, transforms, tools (opt, llc, lli) |
| `clang/` | C/C++/ObjC frontend compiler |
| `clang-tools-extra/` | clangd, clang-tidy, clang-format, include-cleaner |
| `lld/` | Linker (ELF, COFF, Mach-O, wasm) |
| `lldb/` | Debugger |
| `mlir/` | Multi-Level IR framework |
| `compiler-rt/` | Sanitizers (ASan, TSan, UBSan), builtins, profiling |
| `libcxx/` / `libcxxabi/` | C++ standard library and ABI |
| `libc/` | C standard library |
| `bolt/` | Binary optimizer |
| `flang/` | Fortran frontend |
| `openmp/` | OpenMP runtime |
| `polly/` | Polyhedral loop optimizer |
| `cmake/` | Shared CMake modules |
| `third-party/` | Vendored: Google Test, Google Benchmark |
| `.github/workflows/` | GitHub Actions CI (premerge, release, docs) |
| `.ci/` | CI scripts and Buildbot workers |
