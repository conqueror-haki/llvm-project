# 2.1 工具链全景

> **学习目标**：建立 LLVM 工具链的全局概念模型，理解每个工具的职责和它们之间的数据流动关系。
>
> **前置知识**：完成第一卷的环境搭建和第一次编译。

---

## 本章导读

LLVM 不是"一个编译器"，而是一套可组合的编译器基础设施。理解每个工具的职责边界和它们之间如何协作，是有效使用 LLVM 的前提。

如果你来自 GCC 世界，需要改变一个观念：GCC 是一个"一体化"编译器（`gcc test.c -o test` 做所有事情），而 LLVM 将编译管线拆分为独立的可组合工具。这既是它的优势（灵活性、可插拔），也是新手困惑的来源（"为什么有这么多可执行文件？"）。

---

## 2.1.1 谁是主角？—— LLVM 工具角色图

```
                        LLVM 编译工具链
 ┌─────────────────────────────────────────────────────────────┐
 │                                                             │
 │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
 │  │ .c .cpp  │   │ .ll .bc  │   │ .ll .bc  │   │   .s     │ │
 │  │ .m .mm   │──▶│  LLVM IR │──▶│ 优化后IR  │──▶│ 汇编代码  │ │
 │  │          │   │          │   │          │   │          │ │
 │  │  clang   │   │ opt      │   │ llc      │   │ lld      │ │
 │  │  前端     │   │  中端     │   │  后端     │   │  链接器   │ │
 │  └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
 │       │              │              │              │        │
 │       ▼              ▼              ▼              ▼        │
 │  语法/语义检查    IR→IR 变换    IR→目标机码    .o→可执行    │
 │                                                             │
 └─────────────────────────────────────────────────────────────┘
```

每个工具的职责是单一的、可替换的：

| 工具 | 输入 | 输出 | 核心职责 |
|------|------|------|---------|
| `clang` | `.c/.cpp` | `.ll/.bc` | 理解 C/C++ 语言，翻译为 LLVM IR |
| `opt` | `.ll/.bc` | `.ll/.bc` | 在 IR 上运行优化 Pass（不改变输入输出格式） |
| `llc` | `.ll/.bc` | `.s/.o` | 将 IR 翻译为特定 CPU 的机器码 |
| `lld` | `.o` | 可执行文件 | 符号解析、重定位、链接 |

---

## 2.1.2 深入：clang 是驱动而不是编译器

很多人认为 `clang` 是编译器。准确地说，`clang`（小写）是一个**驱动（Driver）**。它负责：

1. 解析命令行参数（如 `-O2`、`-Wall`、`-I/path`）
2. 确定编译阶段（预处理、编译、汇编、链接）
3. 调用子进程完成各阶段的工作：
   - `clang -cc1`：编译器核心进程（前端 + 优化 + 后端）
   - `as`（或 LLVM 集成汇编器）：汇编器
   - `ld`（或 LLD）：链接器

```
用户命令：clang -O2 test.c -o test

  clang (驱动) 解析参数
    ├── clang -cc1 -emit-obj -O2 test.c -o /tmp/test.o
    │     ├── Lexer → Parser → Sema → CodeGen → IR
    │     ├── opt (内嵌) → 优化 IR
    │     └── llc (内嵌) → 生成目标文件
    │
    └── ld /tmp/test.o -o test -lc
```

> 💡 **理解 clang -cc1**：`-cc1` 模式跳过驱动层，直接运行编译器核心。这在调试和测试中很有用，但不推荐日常使用（因为失去自动依赖管理和路径配置）。

---

## 2.1.3 三种文件格式的精确区分

LLVM 工作流中涉及三种文件格式，它们的区别经常被混淆：

### .ll — LLVM Assembly（文本 IR）

```
; 人类可读的文本格式
; 可以用文本编辑器查看和编辑
; 用于调试、测试、手动编写

define i32 @add(i32 %a, i32 %b) {
  %sum = add i32 %a, %b
  ret i32 %sum
}
```

**特点**：
- 人类可读、可写
- 文件较大（相对于 .bc）
- 适合版本控制、CI 测试（diff 友好）
- 不适合发行（体积大）

### .bc — LLVM Bitcode（二进制 IR）

```
; 紧凑的二进制格式
; 不可直接阅读（需要 llvm-dis 反编译）
; 用于 LTO（链接时优化）、发行

$ xxd test.bc | head -2
00000000: 4243 c0de 0017 0000 0000 0000 0328  .............(.
```

**特点**：
- 紧凑（比 .ll 小 3-5 倍）
- 快速加载/保存
- 适合 LTO（链接器可以合并 .bc 文件）
- 适合发行（如 Apple 的 bitcode）
- 不人类可读

### .o/.obj — 目标文件（Native Object）

```
; 平台的机器码 + 元数据
; 包含符号表、重定位表、调试信息
; 不可直接执行（需要链接）
```

**特点**：
- 平台相关（ELF on Linux, Mach-O on macOS, COFF on Windows）
- 可以被系统链接器处理
- 包含完整的机器指令

### 三者之间的关系

```
.ll (文本 IR)  ←──llvm-as──→  .bc (二进制 IR)  ←──llvm-dis──→  .ll
                                 │
                            llc  │
                                 ▼
                            .s/.o (机器码)
                                   │
                              lld  │
                                   ▼
                            a.out (可执行文件)
```

**转换是无损的**（在 IR 层面）：
- `.ll ←→ .bc`：语义等价，只有格式不同
- `.bc → .s/.o`：从 IR 语义映射到机器语义（引入平台差异）

---

## 2.1.4 LLVM IR 的三种存在形态

上文提到了文件格式，但 LLVM IR 还有第三种形态——内存中的 C++ 对象：

```
形态 1: 内存表示 (C++ API)
  ┌──────────────────────────────────┐
  │ Module                           │
  │  ├── Function "add"              │
  │  │   ├── BasicBlock "entry"      │
  │  │   │   ├── Instruction "add"   │
  │  │   │   └── Instruction "ret"   │
  │  │   └── ...                     │
  │  └── ...                         │
  └──────────────────────────────────┘
  操作方式：C++ API (llvm::Module, llvm::Function, etc.)

形态 2: 文本格式 (.ll)
  define i32 @add(i32 %a, i32 %b) { ... }
  操作方式：文本编辑器、opt -S

形态 3: 位码格式 (.bc)
  [二进制数据]
  操作方式：opt、llc、llvm-dis
```

这三种形态可以自由转换：
- 内存 → 文本：`Module::print(llvm::outs(), nullptr)`
- 内存 → 位码：`llvm::WriteBitcodeToFile(Module, OS)`
- 文本 → 内存：`llvm::parseIRFile(Filename, Err, Context)`
- 位码 → 内存：同上（自动检测格式）

---

## 2.1.5 LLVM 的编译选项如何穿透各层

当你运行 `clang -O2 test.c` 时，`-O2` 这个选项被**传递到每一层**：

```
clang 驱动解析 "-O2"
  │
  ├─→ clang -cc1 收到 -O2
  │     └─→ CodeGen 根据 O2 选择生成 IR 的策略
  │         （例如：O0 使用 FastISel, O2 使用 SelectionDAG ISel）
  │
  ├─→ opt (内嵌) 根据 O2 构建优化 Pass 管线
  │     └─→ 运行约 50 个 Pass: mem2reg → instcombine → gvn → inline → ...
  │
  └─→ llc (内嵌) 根据 O2 选择后端优化策略
        └─→ 寄存器分配使用 Greedy (非 Fast)
          指令调度使用 MachineScheduler (非 简单调度)
```

---

## 2.1.6 LLVM IR 作为"通用语言"

LLVM 最革命性的设计之一：**无论你写什么语言，最终都会变成 LLVM IR**。

```
C       → Clang    → LLVM IR
C++     → Clang    → LLVM IR
ObjC    → Clang    → LLVM IR
Rust    → rustc    → LLVM IR (通过 llvm-sys)
Swift   → swiftc   → LLVM IR
Julia   → julia    → LLVM IR (JIT)
Fortran → flang     → LLVM IR
Kotlin  → kotlinc  → LLVM IR (通过 Kotlin/Native)
Haskell → GHC      → LLVM IR (通过 -fllvm)
...
```

**这意味着**：任何 LLVM 优化 Pass 对上述任何语言都有效。你在 Rust 中写的内联函数，与在 C++ 中写的完全相同，经过 LLVM 优化后可以达到同等性能。

---

## 2.1.7 工具速查表

| 工具 | 一句话 | 最常见用法 |
|------|--------|-----------|
| `clang` | C/C++ → IR → 可执行文件 | 日常编译 |
| `clang++` | C++ → IR → 可执行文件 | 同上（C++） |
| `opt` | IR → IR（优化） | 实验优化 Pass、调试 |
| `llc` | IR → 机器码 | 跨平台代码生成 |
| `lld` | .o → 可执行文件 | 链接 |
| `lli` | 执行 IR（解释器/JIT） | 运行不完整程序 |
| `llvm-as` | .ll → .bc（汇编器） | 格式转换 |
| `llvm-dis` | .bc → .ll（反汇编器） | 调试 |
| `llvm-link` | .bc + .bc → .bc（IR 链接） | LTO、合并 |
| `llvm-extract` | .bc → .bc（提取函数） | 隔离问题函数 |
| `llvm-objdump` | .o → 人类可读信息 | 分析目标文件 |
| `llvm-nm` | .o → 符号列表 | 检查未定义符号 |
| `llvm-readelf` | .o → ELF 结构 | 调试链接问题 |
| `llvm-mca` | 汇编 → 性能分析 | 微架构分析 |
| `llvm-profdata` | raw profile → 可用 profile | PGO |
| `llvm-cov` | 覆盖率数据 → 报告 | 覆盖率分析 |
| `llvm-strip` | 可执行文件 → 剥离符号 | 减小体积 |
| `llvm-symbolizer` | 地址 → 源文件行号 | 崩溃分析 |
| `FileCheck` | 输入 → 模式匹配 | 测试验证 |
| `llvm-lit` | 运行回归测试 | 测试框架 |

---

## 2.1.8 练习

<div class="exercise">

### 基础练习

1. 写一个包含多个函数的 C 文件，分别用 `clang`、`opt`、`llc` 手动执行完整管线（不使用驱动的一步编译）。
2. 将同一个 .c 文件分别输出为 `.ll` 和 `.bc`，然后用 `llvm-as`/`llvm-dis` 互相转换，验证内容等价。

### 进阶练习

3. 用 `lli` 直接运行一个 LLVM IR 文件（不需要编译为目标文件），理解 JIT 编译和静态编译的差异。
4. 用 `llvm-extract` 从一个包含 10 个函数的 Module 中提取某一个函数，并验证提取后的 IR 可以独立被 `opt` 优化。

</div>
