# 2.2 Clang 编译器

> **学习目标**：掌握 Clang 的所有核心用法——从基本编译到诊断、优化、Sanitizer、交叉编译，建立"Clang 是 LLVM 的窗口"的认知。
>
> **前置知识**：了解 C/C++ 基本编译流程，至少用过一种编译器（GCC 或 MSVC）。

---

## 本章导读

Clang 是 LLVM 项目中使用最广泛的工具。它不仅是一个 C/C++ 编译器前端，更是一个**编译基础设施**——提供丰富的诊断、分析、工具接口。本章不是罗列手册中的每个选项，而是回答以下问题：

- Clang 如何比 GCC 提供更好的错误信息？（诊断系统）
- Sanitizer 如何检测内存错误？（运行时插桩）
- PGO 如何使编译出的程序更快？（Profile-Guided Optimization）
- Clang 的交叉编译为何如此简单？（Target Triple 机制）

---

## 2.2.1 Clang 的架构：驱动层与核心层

```
┌─────────────────────────────────────────┐
│         clang (Driver/驱动层)             │
│  解析命令行、确定编译阶段、调度子进程      │
├─────────────────────────────────────────┤
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Lexer   │→│  Parser  │→│  Sema  │  │
│  │ 词法分析  │  │ 语法分析  │  │ 语义分析│  │
│  └──────────┘  └──────────┘  └────────┘ │
│                     │                    │
│                     ▼                    │
│  ┌──────────────────────────────────┐   │
│  │         CodeGen (AST → IR)        │   │
│  └──────────────────────────────────┘   │
│                     │                    │
│  clang -cc1 (核心层)  ← 通过 -Xclang 传参│
└─────────────────────────────────────────┘
```

---

## 2.2.2 控制编译阶段

### 分步编译

```bash
clang -E test.c              # 只预处理（输出到 stdout）
clang -fsyntax-only test.c   # 只做词法/语法/语义检查，不生成代码
clang -S test.c              # 生成汇编文件 test.s
clang -c test.c              # 编译为目标文件 test.o（不链接）
clang test.c -o test         # 编译 + 链接（默认行为）
```

### 使用场景

| 命令 | 何时用 |
|------|--------|
| `-E` | 调试宏展开问题、查看预处理结果 |
| `-fsyntax-only` | 快速检查代码是否有语法错误（比完整编译快） |
| `-S -emit-llvm` | 查看生成的LLVM IR（最常用！） |
| `-c` | 多文件项目的增量编译 |
| `-save-temps` | 保留所有中间文件用于调试 |

---

## 2.2.3 诊断系统：Clang 的招牌功能

Clang 以**极其清晰的错误和警告信息**著称。这得益于它的诊断基础设施。

### 基本诊断控制

```bash
# 开启常见警告
clang -Wall -Wextra test.c

# 将所有警告视为错误
clang -Werror test.c

# 将特定警告视为错误
clang -Werror=unused-variable test.c

# 禁用特定警告
clang -Wno-unused-variable test.c

# 显示控制每个诊断的旗标
clang -fdiagnostics-show-option test.c

# 彩色输出
clang -fcolor-diagnostics test.c

# 将警告/错误格式化为 IDE 可解析的格式
clang -fdiagnostics-format=msvc test.c      # Visual Studio 格式
clang -fdiagnostics-format=vi test.c        # vi 兼容格式
```

### 错误信息的质量对比

GCC 的错误信息：
```
test.c: In function 'main':
test.c:5:5: error: 'x' undeclared (first use in this function)
    5 |     x = 10;
      |     ^
```

Clang 的错误信息：
```
test.c:5:5: error: use of undeclared identifier 'x'
    x = 10;
    ^
test.c:3:9: note: 'y' declared here
    int y = 20;
        ^
test.c:5:5: note: did you mean 'y'?
    x = 10;
    ^
```

Clang 不仅指出错误位置，还**主动猜测你的意图**（"did you mean 'y'?"）并在相关声明处附加信息。这种"主动帮助"的设计贯穿整个诊断系统。

### Fix-It 提示

Clang 可以**自动建议修复**：

```bash
# 某些诊断包含 Fix-It 提示
clang -fixit test.c
# 直接修改源文件！
```

示例：缺少分号
```
test.c:5:18: error: expected ';' after expression
    int x = 10
                 ^
                 ;
```
Clang 不仅告诉你缺少 `;`，还精确指出**应该插入的位置**。

---

## 2.2.4 优化级别详解

### 从 O0 到 Oz 的实际意义

```
-O0  →  不优化，编译最快，生成代码最慢
         用途：调试（-g 配合使用）

-O1  →  基础优化（约 30 个 Pass）
         用途：需要一定性能但编译不能太慢时

-O2  →  标准优化（约 50 个 Pass，生产环境默认）
         用途：大多数场景的最优选择

-O3  →  激进优化（O2 + 更激进的内联和循环展开）
         用途：计算密集型应用（数值模拟、视频编解码等）

-Os  →  优化代码体积（-O2 + 体积优化）
         用途：嵌入式、移动端、固件

-Oz  →  最小化体积（-Os 的激进版本）
         用途：极小内存设备
```

### 深入各优化级别的 Pass 组合

你可以查看每个级别实际执行的 Pass 列表：

```bash
# Legacy PM 方式
clang -O1 -mllvm -debug-pass=Arguments test.c -c 2>&1 | tr ' ' '\n' | head -20

# New PM 方式（LLVM 16+）
opt -passes='default<O1>' /dev/null -S -debug-pass-manager 2>&1
```

**O1 的核心 Pass**（简化列表）：
```
tti, targetlibinfo, tbaa, scoped-noalias,
assumption-cache-tracker, profile-summary-info,
forceattrs, inferattrs, ipsccp, globalopt, mem2reg,
deadargelim, instcombine, simplifycfg, sroa,
early-cse, lower-expect, ...
```

**O2 在 O1 基础上增加的**：
```
inline (更深阈值), gvn, loop-rotate, licm,
loop-unroll, loop-vectorize, slp-vectorize,
aggressive-instcombine, ...
```

---

## 2.2.5 运行时分析工具（Sanitizers）

Sanitizer 是 LLVM 最实用的功能之一：通过编译时插桩，在运行时检测内存错误、未定义行为、数据竞争等。

### AddressSanitizer (ASan) — 内存错误检测

```bash
clang -fsanitize=address -g test.c -o test
./test
```

ASan 可以检测：
- **Use-after-free**（使用已释放的内存）
- **Heap buffer overflow**（堆缓冲区越界）
- **Stack buffer overflow**（栈缓冲区越界）
- **Global buffer overflow**（全局缓冲区越界）
- **Use-after-return**（使用已返回函数的栈变量）
- **Memory leaks**（内存泄漏，通过设置 `ASAN_OPTIONS=detect_leaks=1`）

ASan 的工作原理：
1. 在编译时，ASan 将每次内存访问（load/store）替换为"检查 + 访问"对
2. 在运行时，ASan 使用"影子内存"（shadow memory）跟踪每个字节的分配状态
3. 当检测到非法访问时，打印详细的调用栈并终止程序

性能代价：约 2x 减速，约 2-3x 内存增长。**绝不应在生产环境使用**，但测试和 CI 中使用价值极高。

### UndefinedBehaviorSanitizer (UBSan)

```bash
clang -fsanitize=undefined test.c -o test
```

UBSan 可以检测：
- 有符号整数溢出：`INT_MAX + 1`
- 移位越界：`x << 64`（x 为 64 位整数）
- 空指针解引用
- 除以零
- 浮点转换为越界整数
- 非平凡类型的 memcpy/memset

### ThreadSanitizer (TSan) — 数据竞争检测

```bash
clang -fsanitize=thread -g test.c -o test -lpthread
```

TSan 在运行时检测多线程程序中的数据竞争。性能代价约 5-10x 减速。

### MemorySanitizer (MSan) — 未初始化读检测

```bash
clang -fsanitize=memory -g test.c -o test
```

MSan 检测"读取未经初始化的内存"这种错误。这需要整个程序（包括依赖的库）都用 MSan 编译。

### Sanitizer 组合使用

```bash
# 同时启用 ASan + UBSan + LeakSanitizer
clang -fsanitize=address,undefined,leak -g test.c -o test
```

---

## 2.2.6 Profile-Guided Optimization (PGO)

PGO 是一个两阶段过程，基于真实运行时数据优化程序。

### 阶段 1：插桩编译（Instrumentation）

```bash
clang -fprofile-instr-generate test.c -o test_instr
```

编译出的程序运行时，会记录每个函数被调用的次数、每个分支的实际方向、每个表达式的值范围等。

### 阶段 2：收集运行数据

```bash
# 用代表性数据运行程序
./test_instr < train_data.txt

# 产生 default.profraw
```

### 阶段 3：使用 Profile 重新编译

```bash
# 将原始 profile 转为可用格式
llvm-profdata merge -output=test.profdata default.profraw

# 使用 profile 重新编译
clang -fprofile-instr-use=test.profdata test.c -o test_opt
```

PGO 的效果：
- **改善分支预测**：编译器根据实际方向排列基本块
- **更精准的内联决策**：热函数更多内联，冷函数不内联
- **寄存器分配优化**：热路径上的变量优先级更高
- **循环优化决策**：根据实际次数决定展开量

---

## 2.2.7 链接时优化（LTO）

LTO 在**链接阶段**对所有目标文件包含的 IR 运行全程序优化。

### Full LTO

```bash
clang -flto -O2 -c test1.c -o test1.o
clang -flto -O2 -c test2.c -o test2.o
clang -flto -O2 test1.o test2.o -o test
```

### ThinLTO（增量 LTO，推荐）

```bash
clang -flto=thin -O2 -c test1.c -o test1.o
clang -flto=thin -O2 -c test2.c -o test2.o
clang -flto=thin -O2 test1.o test2.o -o test
```

ThinLTO 的优势：
- 并行化（不同函数可以独立优化）
- 增量编译（修改一个文件不需要重新分析整个程序）
- 内存友好（不需要加载全程序 IR 到内存）

---

## 2.2.8 交叉编译

LLVM/Clang 内建支持交叉编译——不需要为目标平台构建特殊的交叉编译器。

```bash
# 在 x86 上编译 ARM64 程序
clang --target=aarch64-linux-gnu test.c -o test_arm

# 在 x86 上编译 RISC-V 64 程序
clang --target=riscv64-linux-gnu test.c -o test_riscv

# 编译 Windows 程序（MinGW）
clang --target=x86_64-w64-mingw32 test.c -o test.exe

# 编译 WebAssembly
clang --target=wasm32 -nostdlib test.c -o test.wasm

# 指定 CPU 微架构
clang --target=aarch64-linux-gnu -mcpu=cortex-a76 test.c
clang --target=aarch64-linux-gnu -mcpu=apple-m1 test.c
```

---

## 2.2.9 完整速查

```bash
# === 查看内部命令 ===
clang -### -O2 test.c -o test

# === 预处理 ===
clang -E test.c
clang -dM -E -x c /dev/null              # 查看预定义宏
clang -v -E -x c /dev/null 2>&1 | grep ^\#  # 查看 include 路径

# === 诊断 ===
clang -Wall -Wextra -Wpedantic test.c
clang -Werror -Wno-unused test.c
clang -fdiagnostics-show-option test.c

# === 优化 ===
clang -O0 / -O1 / -O2 / -O3 / -Os / -Oz
clang -flto / -flto=thin

# === 调试 ===
clang -g test.c
clang -gline-tables-only test.c

# === Sanitizer ===
clang -fsanitize=address test.c
clang -fsanitize=undefined test.c

# === 代码生成 ===
clang -S -emit-llvm test.c              # IR
clang -S test.c                          # 汇编
clang -c test.c                          # 目标文件

# === 链接 ===
clang -fuse-ld=lld test.c
clang -static test.c
clang -Wl,-Map=output.map test.c

# === 向 LLVM 后端传参 ===
clang -mllvm -print-after-all test.c
clang -mllvm -debug-only=instcombine test.c
clang -mllvm -time-passes test.c
```

---

## 2.2.10 练习

<div class="exercise">

### 基础练习

1. 故意写一段有多个类型错误的 C 代码，用 Clang 编译，对比其错误信息与 GCC 的差异。
2. 对一个包含循环的 C 程序，分别用 `-O0` 和 `-O2` 编译，用 `time` 测量运行时间差异。

### 进阶练习

3. 写一个包含堆越界的 C 程序，用 `-fsanitize=address` 编译运行，分析 ASan 的错误报告。
4. 对一个小程序启用 PGO（3 个阶段），对比优化前后的运行时间。
5. 尝试交叉编译：将一个简单的 `hello.c` 编译到 ARM64 debug，用 QEMU 运行验证。

### 挑战练习

6. 启用 ThinLTO 将一个多文件项目链接，对比无 LTO 和有 LTO 的可执行文件大小和运行速度。
7. 写一个包含未初始化变量读取的 C 程序，用 `-fsanitize=memory` 检测并分析 MSan 报告。

</div>
