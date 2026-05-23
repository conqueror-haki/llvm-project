# 1.1 环境搭建

> **学习目标**：完成本章后，你将能够从源码构建 LLVM + Clang，拥有一个可用的编译器开发环境。
>
> **前置知识**：基本 Linux/macOS 命令行操作，了解 Git 的基本用法。

---

## 本章导读

LLVM 是一个由 C++17 编写的巨型编译器基础设施项目，包含超过 20 个主要子项目，代码量超过千万行。搭建一个高效的开发环境是学习 LLVM 的第一步——也是最容易被忽视的一步。

一个不合理的构建配置可能导致：
- Debug 构建需要 40 GB 内存和 2 小时编译时间
- 每次修改代码后需要等待 15 分钟才能重新构建
- 测试运行缓慢，导致开发循环被严重拖慢

本章将从硬件需求开始，逐步指导你完成环境搭建的每一个步骤，并在每个关键节点给出优化建议。我们会覆盖 Linux、macOS 和 Windows(WSL) 三种平台的配置方法。

---

## 1.1.1 硬件需求分析

LLVM 对硬件资源的需求因构建配置差异巨大。以下是三种常见开发场景的硬件需求：

| 资源 | 最小要求（仅 LLVM + Clang） | 推荐配置（LLVM + Clang + LLD） | 全量构建 |
|------|--------------------------|------------------------------|---------|
| CPU 核心 | 4 核（每个核心 ≥2.0 GHz） | 16 核以上 | 32 核以上 |
| 内存 | 8 GB（Release 构建） | 32 GB | 64 GB+ |
| 磁盘空间 | 30 GB（单一 Debug 构建） | 100 GB SSD（多构建目录） | 200 GB+ SSD |
| 操作系统 | Linux / macOS / Windows(WSL2) | Linux (Ubuntu 22.04+) | 同左 |

### 为什么 Debug 构建如此耗费资源？

LLVM 的 Debug 构建中，每个 `.cpp` 文件编译出的目标文件可能包含大量调试符号。关键问题出在**链接阶段**：

1. **静态库链接**：LLVM 默认将每个库编译为 `.a`（静态库），链接 `opt` 或 `clang` 时需要将数十个静态库合成一个可执行文件。Debug 模式下，每个 `.o` 文件可达数十 MB（包含完整的 DWARF 调试信息），最终链接器需要处理 **数 GB 的数据**。

2. **符号数量**：LLVM 的 C++ 模板和头文件展开后符号数量巨大。一个典型 Debug 构建的 `opt` 可能包含超过 100 万个符号。

3. **链接器内存**：GNU `ld`（bfd linker）在处理大文件时内存占用约为文件大小的 3-5 倍。处理 3 GB 的数据可能需要 15 GB 以上的内存。

### 如何缓解资源问题

如果你只有 16 GB 内存，可以采用以下策略：

- **使用 Release + Assertions 构建**（推荐，第 1.2 章详述）：编译速度快 10-20 倍，内存占用减少 70%
- **使用 `-DBUILD_SHARED_LIBS=ON`**：改为动态库构建，链接阶段内存需求大幅降低
- **使用 `-DLLVM_USE_LINKER=lld`**：LLD 的内存使用远低于 GNU ld
- **使用 `-DLLVM_PARALLEL_LINK_JOBS=2`**：限制同时链接的进程数量
- **只构建需要的目标后端**：如 `-DLLVM_TARGETS_TO_BUILD="X86"`，省去 90% 的目标架构编译

---

## 1.1.2 源码检出

### 完整克隆 vs 浅克隆

LLVM 的 Git 仓库历史非常长（自 2003 年起），完整克隆可能超过 2 GB，且需要较多网络带宽和时间。如果你只看代码、不做开发和贡献，推荐使用**浅克隆**：

```bash
# 浅克隆（只取最新一次提交，约 200 MB）
git clone --depth 1 https://github.com/llvm/llvm-project.git
cd llvm-project
```

如果你需要完整历史（例如做 `git blame`、提交 PR、查看历史变更）：

```bash
# 完整克隆（约 2 GB）
git clone https://github.com/llvm/llvm-project.git
cd llvm-project
```

### 仓库目录结构（第一印象）

进入 `llvm-project/` 后，你会看到大约 30 个子目录。不要被吓到，它们分为四个层级：

```
llvm-project/                          # Monorepo 根目录
│
├── llvm/                              # ★ 核心 LLVM（我们的主要学习对象）
│   ├── include/                       #    公共 C++ 头文件
│   ├── lib/                           #    库实现（按模块划分）
│   ├── tools/                         #    命令行工具
│   ├── test/                          #    回归测试
│   ├── unittests/                     #    单元测试
│   ├── docs/                          #    文档（RST 格式）
│   └── examples/                      #    教学示例（Kaleidoscope 等）
│
├── clang/                             # ★ C/C++/ObjC 前端编译器
├── clang-tools-extra/                 #   额外工具：clangd、clang-tidy、clang-format
├── lld/                               #   链接器（ELF、COFF、Mach-O、wasm）
├── lldb/                              #   调试器
├── mlir/                              #   多层 IR 框架（ML 编译）
│
├── compiler-rt/                       #   运行时库（Sanitizers、builtins、profiling）
├── libcxx/                            #   C++ 标准库（libc++）
├── libcxxabi/                         #   C++ ABI 库
├── libunwind/                         #   栈展开库
├── libc/                              #   C 标准库实现
│
├── bolt/                              #   二进制优化器
├── flang/                             #   Fortran 前端
├── openmp/                            #   OpenMP 运行时
├── polly/                             #   多面体循环优化器
│
├── cmake/                             #   共享 CMake 模块
├── third-party/                       #   第三方库（Google Test、Google Benchmark）
├── .github/workflows/                 #   CI 工作流
└── .ci/                               #   CI 脚本与 Buildbot
```

> 💡 **关键认知**：`llvm/` 目录里有自己的 CMakeLists.txt 和构建配置，**所有的 CMake 配置命令都需要从 `llvm/` 作为源码目录**。这是 LLVM 项目最不直观的一点，8 成新手第一次配置都会犯错。

---

## 1.1.3 系统工具链准备

### Linux (Ubuntu 22.04+)

Ubuntu 是最推荐的开发平台，因为 Linux 上构建 LLVM 最快：

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \        # GCC、G++、make 等基本编译工具
    cmake \                  # 构建系统生成器（需要 ≥3.20.0）
    ninja-build \            # 快速构建工具（替代 make）
    python3 \                # 脚本（测试框架 lit 需要）
    python3-psutil \         # 测试并行化需要
    python3-distutils \      # Python 包构建
    zlib1g-dev \             # zlib 压缩库（LLVM 链接时需要）
    libzstd-dev              # zstd 压缩库（LLVM 链接时需要）
```

**CMake 版本要求**：LLVM 要求 CMake ≥3.20.0。Ubuntu 22.04 的 apt 可能安装较旧版本，检查：

```bash
cmake --version
# 如果版本 < 3.20.0，从官方安装：
wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc | sudo apt-key add -
sudo apt-add-repository "deb https://apt.kitware.com/ubuntu/ $(lsb_release -cs) main"
sudo apt-get update
sudo apt-get install cmake
```

### macOS

macOS 是第二常用的 LLVM 开发平台。需要 Xcode 命令行工具和 Homebrew：

```bash
# 安装 Xcode 命令行工具（提供 clang、make 等）
xcode-select --install

# 安装 Homebrew（如果尚未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装必需工具
brew install cmake ninja python3

# 可选：安装 ccache 加速重复构建
brew install ccache
```

### Windows (WSL2)

Windows 上推荐使用 WSL2 + Ubuntu。WSL2 提供了接近原生 Linux 的性能：

```powershell
# 在 PowerShell（管理员）中
wsl --install -d Ubuntu-22.04
wsl --set-default-version 2
```

然后按 Linux 的步骤操作。需要特别注意：
- 将 LLVM 源码放在 WSL 的文件系统内（如 `/home/user/llvm-project`），**不要**放在 `/mnt/c/` 下，跨文件系统编译会极慢
- WSL2 的网络文件系统（`/mnt/c/`）的 I/O 速度约为原生 Linux 文件系统的 1/5

---

## 1.1.4 首轮构建：最小 LLVM

在首次构建时，建议只构建 LLVM 核心——不包含 Clang、不包含所有目标架构。这个最小构建可以快速验证环境配置是否正确。

### 配置

```bash
# 从 llvm-project 根目录执行
cmake -S llvm -B build-minimal -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD="X86" \
    -DLLVM_ENABLE_PROJECTS=""
```

参数解析：
- `-S llvm`：指定 CMake 源码目录为 `llvm/`（**不是当前目录！**）
- `-B build-minimal`：构建产物输出到 `build-minimal/`
- `-G Ninja`：使用 Ninja 构建系统（比 Unix Makefiles 快 20-30%）
- `-DCMAKE_BUILD_TYPE=Release`：Release 模式，编译快、运行快
- `-DLLVM_TARGETS_TO_BUILD="X86"`：只编译 X86 目标后端，省去 95% 的后端代码
- `-DLLVM_ENABLE_PROJECTS=""`：不构建任何附加项目（Clang、LLD 等）

### 构建

```bash
ninja -C build-minimal
```

构建时间约为 5-15 分钟（取决于 CPU）。构建完成后，可执行文件位于 `build-minimal/bin/`：

```bash
ls build-minimal/bin/
# 应该看到：
#   opt              — LLVM IR 优化器
#   llc              — 静态编译器（IR → 汇编）
#   llvm-as          — IR 汇编器（.ll → .bc）
#   llvm-dis         — IR 反汇编器（.bc → .ll）
#   llvm-link        — IR 链接器
#   llvm-objdump     — 目标文件反汇编
#   llvm-nm          — 符号表查看
#   llvm-readelf     — ELF 文件分析
#   FileCheck        — 测试输出验证
#   llvm-tblgen      — TableGen 代码生成
#   llvm-lit         — 测试运行器
#   count            — 测试中的行计数工具
#   not              — 测试中的取反工具
```

### 验证

```bash
# 检查 LLVM 版本
./build-minimal/bin/opt --version

# 典型输出：
# LLVM (http://llvm.org/):
#   LLVM version 19.0.0git
#   Optimized build with assertions.
#   Default target: x86_64-unknown-linux-gnu
#   Host CPU: skylake
```

### 如果构建失败

**错误 1：`In-source builds are not allowed`**

```
CMake Error at CMakeLists.txt:...:
  In-source builds are not allowed.
```

这意味着你将 `-B` 设成了与 `-S` 相同或父目录的路径。确保 `-S llvm` 指向 `llvm/` 目录，`-B` 指向一个**不在 `llvm/` 子树内**的独立目录。

**错误 2：`No CMAKE_CXX_COMPILER could be found`**

```
CMake Error: No CMAKE_CXX_COMPILER could be found.
```

你的系统缺少 C++ 编译器。在 Ubuntu 上安装 `build-essential`。

**错误 3：内存耗尽（OOM Killer）**

```
collect2: fatal error: ld terminated with signal 9 [Killed]
```

链接阶段内存不足。解决方案（按推荐优先级）：
1. 添加 swap 空间：`sudo fallocate -l 16G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`
2. 限制并行链接数：`-DLLVM_PARALLEL_LINK_JOBS=2`
3. 使用 LLD 作为链接器：`-DLLVM_USE_LINKER=lld`
4. 使用动态库构建：`-DBUILD_SHARED_LIBS=ON`

---

## 1.1.5 完整构建：LLVM + Clang

最小构建验证通过后，我们来构建完整环境——同时包含 LLVM 核心和 Clang 前端。

### 推荐的学习配置

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="X86"
ninja -C build
```

### 配置参数详解

**`-DCMAKE_BUILD_TYPE=Release`**

LLVM 支持四种构建类型：

| 构建类型 | 编译器优化 | 调试符号 | LLVM 断言 | 适用场景 |
|---------|----------|---------|----------|---------|
| `Debug` | `-O0` | `-g` | ON | 调试 LLVM 自身的代码（单步调试） |
| `Release` | `-O2/-O3` | 无 | OFF | 生产环境、运行测试、日常开发 |
| `RelWithDebInfo` | `-O2` | `-g` | OFF | 性能分析 + 需要符号信息时 |
| `MinSizeRel` | `-Os` | 无 | OFF | 最小化可执行文件体积 |

**选择建议**：
- **学习阶段**：使用 `Release` + `-DLLVM_ENABLE_ASSERTIONS=ON`。这个组合编译快、运行快，同时保留了 assertion 检查——你很快会发现 LLVM 内部大量使用 `assert()` 来捕捉不变量违反，这对理解代码逻辑非常重要。
- **调试 LLVM 本身的 bug**：使用 `Debug`。但要注意其性能（`opt` 启动可能需要 10 秒以上，而 Release 只需要 0.5 秒）。
- **Profiling 性能**：使用 `RelWithDebInfo`。

**`-DLLVM_ENABLE_ASSERTIONS=ON`**

这是最容易被漏掉的重要选项。LLVM 源码中有数千个 `assert()` 语句，它们检查各种代码不变量。它们的作用包括：

1. **尽早暴露 bug**：如果你写的 Pass 违反了 IR 约束（例如产生了一个 void 类型的 add 指令），assertion 会立即终止程序并指出问题所在，而不是在后续的某个 Pass 中神秘崩溃。

2. **理解代码假设**：阅读源码时，`assert()` 语句告诉你"这里假设了什么条件成立"。例如：
   ```cpp
   assert(isa<IntegerType>(I.getType()) && "Expected integer type");
   ```
   这告诉你这段代码要求操作数是整数类型。

3. **几乎零运行时开销**：在 Release 构建中，`assert()` 被编译为无操作，没有性能损失。但如果你开启了 `LLVM_ENABLE_ASSERTIONS`，它们只在你的 LLVM 代码中生效——你的生成的二进制程序的性能不受影响。

**`-DLLVM_ENABLE_PROJECTS="clang"`**

`LLVM_ENABLE_PROJECTS` 的值是一个分号分隔的列表。除了 `clang`，常见的项目还包括：

```
clang                — C/C++/ObjC 前端编译器
clang-tools-extra    — clangd（LSP 服务器）、clang-tidy、clang-format
lld                  — 链接器（ELF、COFF、Mach-O、wasm）
lldb                 — 调试器（这个非常大，谨慎开启）
mlir                 — 多层 IR 框架
bolt                 — 二进制优化器
```

如果你在学习阶段，先开启 `clang` 就够了。`clang-tools-extra` 和 `lld` 可以在需要时再添加。注意：开启 `lldb` 会显著增加构建时间（30-60 分钟）。

**`-DLLVM_TARGETS_TO_BUILD="X86"`**

LLVM 支持的完整目标架构列表多达 20+ 种：

```
AArch64, AMDGPU, ARM, AVR, BPF, Hexagon, Lanai, LoongArch,
Mips, MSP430, NVPTX, PowerPC, RISCV, Sparc, SPIRV, SystemZ,
VE, WebAssembly, X86, XCore
```

默认（`all`）会构建全部。学习阶段只构建 X86 就够了，节省约 85% 的后端编译时间。

**自动依赖解析**：如果你启用 `lldb`，LLVM 会自动启用 `clang`（lldb 依赖 clang 的库）。如果你启用 `flang`，会自动启用 `mlir` 和 `clang`。这些依赖由 CMake 自动处理。

### 构建时间估算

以下是在 Intel Core i7-13700K（16 核 24 线程）、32 GB RAM、NVMe SSD 上的实测数据：

| 构建范围 | 配置 | 时间 | 磁盘占用 |
|---------|------|------|---------|
| LLVM only (X86) | Release | 3 分钟 | 2 GB |
| LLVM only (all targets) | Release | 5 分钟 | 4 GB |
| LLVM + Clang (X86) | Release | 6 分钟 | 6 GB |
| LLVM + Clang (all targets) | Release | 12 分钟 | 10 GB |
| LLVM + Clang (X86) | Debug | 25 分钟 | 18 GB |
| LLVM + Clang + LLD + tools-extra (all) | Release | 25 分钟 | 18 GB |

### 构建产物详解

```bash
ls -la build/bin/
```

关键的可执行文件及其用途：

| 可执行文件 | 功能 | 类别 |
|-----------|------|------|
| `clang` | C/C++ 编译器驱动 | 前端 |
| `clang++` | C++ 编译器驱动（实际上是 `clang` 的符号链接） | 前端 |
| `clang-cpp` | C 预处理器 | 前端 |
| `opt` | LLVM IR 优化器 | 中端 |
| `llc` | LLVM 静态编译器（IR → 汇编/目标文件） | 后端 |
| `lli` | LLVM 解释器 / JIT 执行器 | 执行 |
| `llvm-as` | IR 汇编器（`.ll` → `.bc`） | 转换 |
| `llvm-dis` | IR 反汇编器（`.bc` → `.ll`） | 转换 |
| `llvm-link` | IR 链接器（合并多个 `.bc` 文件） | 链接 |
| `llvm-extract` | 从 Module 中提取函数 | 工具 |
| `llvm-objdump` | 目标文件反汇编和分析 | 工具 |
| `llvm-nm` | 查看符号表 | 工具 |
| `llvm-readelf` | ELF 文件分析 | 工具 |
| `llvm-size` | 查看段大小 | 工具 |
| `llvm-strings` | 提取可打印字符串 | 工具 |
| `llvm-ar` | 静态库打包 | 工具 |
| `llvm-strip` | 剥离符号 | 工具 |
| `llvm-profdata` | PGO 数据处理 | 工具 |
| `llvm-cov` | 代码覆盖率 | 工具 |
| `llvm-symbolizer` | 地址 → 符号转换 | 工具 |
| `llvm-mca` | 微架构性能分析 | 工具 |
| `llvm-tblgen` | TableGen 代码生成 | 构建 |
| `llvm-lit` | 测试运行器 | 测试 |
| `FileCheck` | 输出验证工具 | 测试 |
| `count` | 行计数（测试中辅助） | 测试 |
| `not` | 命令取反（测试中辅助） | 测试 |

在 `build/lib/` 下，你会发现编译出的库文件（如果没有使用 `BUILD_SHARED_LIBS`，则都是 `.a` 静态库）：

```
build/lib/
├── libLLVMCore.a             # IR 核心（Value、Instruction、Type 等）
├── libLLVMSupport.a          # 基础工具库（raw_ostream、StringRef 等）
├── libLLVMTransformUtils.a   # Pass 辅助工具
├── libLLVMScalarOpts.a       # 标量优化 Passes
├── libLLVMipo.a              # 过程间优化
├── libLLVMCodeGen.a          # 后端基础设施
├── libLLVMX86CodeGen.a       # X86 后端（最大的单个库，约 500 MB Debug）
├── libclangAST.a             # Clang AST 库
├── libclangSema.a            # Clang 语义分析
├── libclangCodeGen.a         # Clang IR 生成
└── ...
```

---

## 1.1.6 加速构建

编译 LLVM 是一个 I/O 密集、CPU 密集的过程。以下策略可以显著加速重复构建：

### 策略 A：使用 ccache/sccache

`ccache` 将编译结果缓存到磁盘。第二次构建相同文件时（包括你只改了别的文件时的重新编译），直接从缓存读取：

```bash
# 安装 ccache
sudo apt-get install ccache

# 配置 CMake
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_CCACHE_BUILD=ON \
    -DLLVM_ENABLE_PROJECTS="clang"
```

验证 ccache 是否生效：
```bash
ccache -z         # 清零统计
ninja -C build    # 构建（第一次，编译全部文件）
ccache -s         # 查看缓存命中率
# 应该看到 "cache hit (direct)" 和 "cache miss (preprocessed)"

touch llvm/lib/Support/SmallVector.cpp
ninja -C build    # 只重新编译这个文件
ccache -s         # 应该看到高命中率
```

### 策略 B：使用 LLD 链接器

LLD 是 LLVM 自己的链接器，比 GNU `ld` 快得多，内存占用也更低：

```bash
# 首先需要构建 LLD（或通过系统包管理器安装）
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_USE_LINKER=lld \
    -DLLVM_ENABLE_PROJECTS="clang;lld"
```

> 💡 **重要**：`-DLLVM_USE_LINKER=lld` 告诉 CMake "使用 LLD 来链接 LLVM 自身"，而不是"构建 LLD 作为 LLVM 项目的一部分"。如果你的系统上已经安装了 `lld`（通过 `sudo apt-get install lld`），也可以直接使用而不需要在 `LLVM_ENABLE_PROJECTS` 中加入 `lld`。

### 策略 C：限制并行链接数

在内存受限的机器上（< 16 GB），同时链接多个大型可执行文件会导致内存溢出。限制并行链接数：

```bash
cmake -S llvm -B build -G Ninja \
    -DLLVM_PARALLEL_LINK_JOBS=2
```

这个选项只对链接步骤生效，编译步骤不受影响。

### 策略 D：动态库构建

Debug 构建时使用动态库可以大幅减少链接时间和内存。代价是 `opt` 和 `clang` 启动时（加载动态库）会略慢：

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_SHARED_LIBS=ON
```

**使用场景**：只在频繁修改代码时开启动态库 Debug 构建。日常工作使用 Release + 静态库。

### 策略 E：Optimized TableGen

TableGen 工具在 Debug 构建中也很慢（因为它本身也以 `-O0` 编译）。可以用 Release 模式编译它，即使整体是 Debug 构建：

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_OPTIMIZED_TABLEGEN=ON
```

### 策略 F：Split DWARF

Debug 构建时，DWARF 调试信息是链接器的主要负担。将调试信息分离为独立文件可以显著减少链接内存：

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_USE_SPLIT_DWARF=ON
```

### 最优配置组合

将以上策略组合，可以得到一个"快速开发 + 可调试"的配置：

```bash
# 快速开发和调试配置
cmake -S llvm -B build-fast -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_CCACHE_BUILD=ON \
    -DLLVM_USE_LINKER=lld \
    -DLLVM_TARGETS_TO_BUILD="X86" \
    -DLLVM_ENABLE_PROJECTS="clang"
ninja -C build-fast opt llc clang
```

这个配置的典型性能：
- 首次构建时间：~6 分钟（X86 only）
- 修改单个 `.cpp` 后的增量构建：~15 秒
- `opt` 启动时间：<0.5 秒
- `opt` 运行 O2 Pass 管线：正常速度的 100%（Release 模式）

---

## 1.1.7 多构建目录策略

随着学习的深入，你会有不同的构建需求。建议创建多个构建目录，针对不同用途：

```bash
# 1. 快速开发目录（日常使用）
cmake -S llvm -B build-release -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_CCACHE_BUILD=ON \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="X86"

# 2. Debug 目录（调试 LLVM 自身时使用）
cmake -S llvm -B build-debug -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_OPTIMIZED_TABLEGEN=ON \
    -DLLVM_PARALLEL_LINK_JOBS=2 \
    -DBUILD_SHARED_LIBS=ON \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="X86"

# 3. 全目标构建目录（需要跨平台分析时）
cmake -S llvm -B build-all -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="all"

# 4. 带 Sanitizer 的目录（调试内存错误）
cmake -S llvm -B build-asan -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_USE_SANITIZER=Address \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="X86"
```

---

## 1.1.8 验证完整的工具链

```bash
# 1. 检查 clang 版本
./build-release/bin/clang --version

# 2. 编译一个最小的 C 程序
echo 'int main() { return 0; }' > /tmp/test.c
./build-release/bin/clang /tmp/test.c -o /tmp/test
/tmp/test && echo "OK"

# 3. 生成 LLVM IR
./build-release/bin/clang -S -emit-llvm /tmp/test.c -o /tmp/test.ll
cat /tmp/test.ll

# 4. 优化 IR
./build-release/bin/opt -passes='default<O2>' /tmp/test.ll -S -o /tmp/test_opt.ll

# 5. 生成汇编
./build-release/bin/llc /tmp/test_opt.ll -o /tmp/test.s
cat /tmp/test.s

# 6. 运行一个测试
./build-release/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/add.ll
```

---

## 1.1.9 常见问题排查

### Q: CMake 配置时出现 `python3 not found`

LLVM 的构建过程需要 Python（测试框架 lit 用 Python 编写）。安装 Python 3：

```bash
sudo apt-get install python3 python3-distutils
```

### Q: Ninja 构建时卡住（CPU 占用高、无输出）

Ninja 默认使用所有 CPU 核心进行并行编译和链接。如果多个大型链接同时进行，内存可能耗尽，系统开始疯狂使用 swap（称为 thrashing）。

**诊断**：用 `htop` 查看内存使用。如果 swap 使用量激增，系统处于 thrashing 状态。

**解决**：
- 添加物理 swap 空间
- 限制并行链接数：`-DLLVM_PARALLEL_LINK_JOBS=2`
- 使用 LLD 链接器

### Q: 磁盘空间不足

LLVM 的 Debug 构建可能占用 40+ GB 磁盘空间。如果磁盘紧张：

```bash
# 清理构建产物
rm -rf build-debug

# 只保留 Release 构建（约 6 GB）
# Release 构建也不需要时，全部清理
du -sh build-*
rm -rf build-minimal
```

### Q: git clone 太慢

GitHub 在国内的访问速度可能不稳定。可以尝试：
- 使用代理：`git clone --config http.proxy=http://127.0.0.1:7890 https://github.com/llvm/llvm-project.git`
- 使用国内镜像（如 Gitee）
- 使用浅克隆：`--depth 1`

---

## 1.1.10 练习

<div class="exercise">

### 基础练习

1. 使用浅克隆方式检出 LLVM 仓库，比较完整克隆和浅克隆的下载时间差异。
2. 使用 `Release` 模式构建最小 LLVM（只构建 X86 目标），验证构建是否成功。
3. 使用 `Release + clang + X86` 配置构建一个完整环境，并用你构建的 `clang` 编译一个 "Hello, World!" 程序。

### 进阶练习

4. 创建两个构建目录：`build-debug`（Debug 模式）和 `build-release`（Release 模式），对比两者的：
   - 构建时间
   - `opt` 启动时间（用 `time ./build-debug/bin/opt --version` 测量）
   - `opt` 运行 O2 Pass 管线的时间（用 `-time-passes` 测量）
5. 安装并启用 `ccache`，执行两次完整构建，观察第二次的缓存命中率。
6. 在 16 GB 内存的机器上尝试 Debug 构建，如果遇到 OOM（Out Of Memory），实验 `LLVM_PARALLEL_LINK_JOBS=2` 和 `BUILD_SHARED_LIBS=ON` 的效果。

### 挑战练习

7. 研究 `BuildVariables.inc` 文件（在 `build/CMakeFiles/` 目录下），理解 CMake 缓存文件 `CMakeCache.txt` 的结构。尝试直接编辑 `CMakeCache.txt` 来修改某个选项，然后运行 `cmake build/`（无 `-S`、无其他选项）来应用修改——理解"增量 CMake 配置"的概念。
8. 如果你的系统有 clang，尝试用 `-DCMAKE_C_COMPILER=clang -DCMAKE_CXX_COMPILER=clang++` 构建 LLVM（即用 Clang 编译 LLVM），对比 GCC 和 Clang 编译 LLVM 的速度差异。

</div>

---

<div class="exercise">

### 本章要点回顾

- LLVM 的 CMake 源码目录是 `llvm/`，不是仓库根目录
- 推荐的学习配置：Release + Assertions + clang + X86
- 使用 `ccache`、LLD 和 `LLVM_OPTIMIZED_TABLEGEN` 可以显著加速构建
- 多构建目录策略可以满足不同场景的需求（调试、开发、测试）
- Debug 构建只用于调试 LLVM 自身，日常开发使用 Release 构建

</div>
