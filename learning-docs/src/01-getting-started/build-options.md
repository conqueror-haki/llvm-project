# 1.2 构建选项详解

> **学习目标**：理解 LLVM CMake 构建系统中每个关键变量的作用和适用场景，能够根据需求选择正确的构建配置。
>
> **前置知识**：完成 1.1 的环境搭建，了解基本的 CMake 概念。

---

## 本章导读

LLVM 的 CMake 构建系统提供了超过 100 个配置变量。面对这么多选项，如何选择最合适的一组？本章将每个核心变量放在实际场景中讲解——不是罗列文档，而是回答"什么时候用、为什么用、有什么代价"。

读完本章后，你应该能自信地回答：
- 我需要调试 LLVM 自身的段错误，应该用什么构建配置？
- 我需要写一个新的 Pass，应该怎么配置才能提高开发效率？
- 为什么有时 Debug 构建反而比 Release 构建慢 20 倍？
- LLVM_ENABLE_PROJECTS 和 LLVM_ENABLE_RUNTIMES 有什么区别？

---

## 1.2.1 构建类型的深层理解

### Debug、Release 的本质差异不是"快慢"

```
Debug 构建：
  C++ 代码用 -O0 编译
  → 每条语句独立翻译，不进行跨语句优化
  → 生成的机器码"忠实但臃肿"
  → 可以逐行调试（断点、变量查看均准确）

Release 构建：
  C++ 代码用 -O2/-O3 编译
  → 编译器执行数十种优化 Pass
  → 生成的机器码"高效但扭曲"
  → 调试器显示的行号和变量可能不准确
```

一个更形象的类比：Debug 构建相当于"逐字逐句翻译"，Release 构建相当于"理解意思后用自己的话重新表达"——后者更短更高效，但和原文的字面结构已经对不上了。

### 不同构建类型的 CPU 和内存特征

| 度量 | Debug | Release | 说明 |
|------|-------|---------|------|
| `opt` 启动时间 | 5-15 秒 | 0.3-0.5 秒 | Debug 需要加载巨大的 .so 或 link |
| `opt` 运行 InstCombine | 慢 30-50 倍 | 基准 | hotspot 代码在 -O0 无优化 |
| 内存碎片化 | 高 | 低 | Debug 有更多小对象和栈帧 |
| 断言 | 开 | 关（可手动开启）| assert() 由 NDEBUG 宏控制 |

### LLVM_ENABLE_ASSERTIONS：最被低估的选项

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON       # 关键！
```

为什么强烈建议学习阶段开启：
1. **LLVM 的 assert 不是"可有可无的检查"**。它们验证的是代码的核心约束。例如：
   ```cpp
   // 在 SimplifyCFG 中
   assert(BB->getTerminator() && "Basic block must have a terminator!");
   ```
   如果没有 assertion，一个缺少终结指令的基本块可能导致在完全不同的地方（比如 10 个 Pass 之后）崩溃——调试起来是一场噩梦。

2. **API 使用纠错**：调用 LLVM API 时参数不对，assertion 会立即终止并指出问题，而不是返回一个半损坏的 IR。

3. **性能开销极小**：在 Release 优化下，即使开启 assertions，运行时开销通常不超过 5-10%。因为优化器会消除那些编译器能证明为常量的 assertion 条件。

---

## 1.2.2 LLVM_ENABLE_PROJECTS vs LLVM_ENABLE_RUNTIMES

这是 LLVM 构建系统中最让人困惑的概念之一。

### 两类子项目的本质区别

```
LLVM_ENABLE_PROJECTS:
    这些项目与 LLVM 核心"并列构建"
    → 使用相同的编译器配置
    → 使用相同的 C++ 标准库
    → 互相可以引用头文件和链接库

LLVM_ENABLE_RUNTIMES:
    这些项目"引导构建"（bootstrap）
    → 使用刚刚构建好的 Clang 来编译
    → 可以链接到刚刚构建好的 libc++、libcxxabi
    → 形成一个"自包含"的 LLVM 工具链
```

### 为什么需要这种区分？

考虑一个具体场景：你想在 Linux 上构建 `libcxx`（C++ 标准库）。

如果你把 `libcxx` 放在 `LLVM_ENABLE_PROJECTS` 中，它会用系统的 GCC 或 Clang 编译。但如果你想让 `libcxx` 依赖刚刚构建好的 `compiler-rt`（sanitizers）和 `libunwind`，就需要先用 LLVM_ENABLE_PROJECTS 构建好 Clang，然后用 `LLVM_ENABLE_RUNTIMES` 让 Clang 来编译 `libcxx`。

一个典型的自举构建：

```bash
# Step 1: 构建 Clang（作为宿主编译器）
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_PROJECTS="clang"
ninja -C build

# Step 2: 用刚构建的 Clang 编译运行时库
cmake -S llvm -B build-runtimes -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_ENABLE_RUNTIMES="libcxx;libcxxabi;libunwind;compiler-rt"
ninja -C build-runtimes
```

### PROJECTS 支持的完整项目列表

| 项目 | 说明 | 构建时间 | 学习价值 |
|------|------|---------|---------|
| `clang` | C/C++/ObjC 编译器 | 中等 (5-10 min) | ★★★★★ 必学 |
| `clang-tools-extra` | clangd, clang-tidy, clang-format | 中等 (3-5 min) | ★★★ 有用 |
| `lld` | 链接器 | 快 (1-2 min) | ★★★ 了解 |
| `lldb` | 调试器 | 非常慢 (30+ min) | ★★ 了解 |
| `mlir` | 多层 IR 框架 | 中等 (10 min) | ★★★★ ML 方向必学 |
| `bolt` | 二进制优化器 | 中等 | ★★ 特定领域 |
| `polly` | 多面体循环优化器 | 快 | ★★ 高级 |
| `flang` | Fortran 前端 | 慢 | ★ 特定领域 |
| `libc` | C 标准库 | 中等 | ★★ 底层 |

### RUNTIMES 支持的完整项目列表

| 项目 | 说明 |
|------|------|
| `compiler-rt` | Sanitizers、内置函数、profiling |
| `libcxx` | C++ 标准库 |
| `libcxxabi` | C++ ABI |
| `libunwind` | 栈展开 |
| `libc` | C 标准库 |
| `openmp` | OpenMP 运行时 |
| `offload` | GPU 卸载 |

> 📌 **自动依赖解析**：`flang` 会自动启用 `mlir` 和 `clang`；`lldb` 会自动启用 `clang`。你不需要手动展开这些依赖。

---

## 1.2.3 LLVM_TARGETS_TO_BUILD

LLVM 支持的目标架构列表：

```
AArch64       — ARM 64 位（智能手机、Apple Silicon、服务器）
AMDGPU        — AMD GPU（最大、最复杂的后端）
ARM           — ARM 32 位（嵌入式、老手机）
AVR           — Atmel AVR（Arduino）
BPF           — eBPF（Linux 内核）
Hexagon       — Qualcomm Hexagon DSP
Lanai         — Google 内部芯片
LoongArch     — 龙芯（国产 CPU）
Mips          — MIPS
MSP430        — TI 超低功耗 MCU
NVPTX         — NVIDIA PTX（CUDA）
PowerPC       — IBM Power
RISCV         — RISC-V（开源指令集，越来越重要）
Sparc         — Oracle SPARC
SPIRV         — SPIR-V（Vulkan/OpenCL）
SystemZ       — IBM 大型机
VE            — NEC SX-Aurora 向量引擎
WebAssembly   — WASM（浏览器、边缘计算）
X86           — x86 / x86-64（PC、服务器）
XCore         — XMOS XCore
```

**推荐策略**：学习阶段只构建 X86。当你需要分析跨平台代码生成差异时，加 AArch64 和 RISCV。

---

## 1.2.4 LLVM_USE_LINKER

LLVM 项目内部使用大量的 C++ 模板和头文件，导致链接阶段可能成为瓶颈（特别是 Debug 构建）。选择更快的链接器可以显著加速开发周期。

| 选项 | 说明 |
|------|------|
| (默认) | 系统默认链接器（Linux 上通常是 GNU ld/bfd） |
| `lld` | LLVM 自己的链接器，最快，推荐 |
| `gold` | GNU Gold 链接器（比 bfd 快，但比 lld 慢） |
| `mold` | 第三方链接器，极快，但可能需要单独安装 |

**推荐**：始终使用 `LLVM_USE_LINKER=lld`（需要在 `LLVM_ENABLE_PROJECTS` 中加入 `lld`，或系统已安装）。

---

## 1.2.5 一组实用构建配置模板

### 模板 1：学习/教学用

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_ENABLE_PROJECTS="clang" \
    -DLLVM_TARGETS_TO_BUILD="X86"
```

### 模板 2：Pass 开发（快速迭代）

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_CCACHE_BUILD=ON \
    -DLLVM_USE_LINKER=lld \
    -DLLVM_TARGETS_TO_BUILD="X86" \
    -DLLVM_ENABLE_PROJECTS="clang;lld"
```

### 模板 3：调试 LLVM 自身

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_OPTIMIZED_TABLEGEN=ON \
    -DLLVM_PARALLEL_LINK_JOBS=2 \
    -DBUILD_SHARED_LIBS=ON \
    -DLLVM_TARGETS_TO_BUILD="X86"
```

### 模板 4：最小化（CI/空间受限）

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=MinSizeRel \
    -DLLVM_TARGETS_TO_BUILD="host" \
    -DLLVM_INCLUDE_TESTS=OFF \
    -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_INCLUDE_BENCHMARKS=OFF \
    -DLLVM_INCLUDE_DOCS=OFF
```

---

## 1.2.6 练习

<div class="exercise">

### 基础练习

1. 查看你当前构建目录的 CMakeCache.txt，找到 `LLVM_ENABLE_PROJECTS` 和 `LLVM_TARGETS_TO_BUILD` 的值。
2. 用 `ccache -s` 查看缓存统计，理解 `hit rate` 的含义。

### 进阶练习

3. 实验：构建一个 Debug 模式的 LLVM，用 `time opt --version` 测量启动时间。然后重建为 Release + Assertions，对比启动时间的差异。
4. 尝试 `-DLLVM_TARGETS_TO_BUILD="X86;AArch64"` 构建，然后用 `llc -mtriple=aarch64-linux-gnu` 为 AArch64 生成汇编，理解多目标后端的价值。

</div>
