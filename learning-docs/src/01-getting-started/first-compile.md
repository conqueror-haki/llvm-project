# 1.3 第一次编译

> **学习目标**：理解从 C 源代码到可执行文件的完整编译管线，能够分阶段查看每个步骤的输出，建立编译器工作流程的全局概念模型。
>
> **前置知识**：完成 1.1 的环境搭建，基本的 C 语言知识。

---

## 本章导读

编译器不是黑盒子。一个 `clang test.c -o test` 命令的背后，隐藏着一个精密的流水线：预处理 → 词法分析 → 语法分析 → 语义分析 → IR 生成 → IR 优化 → 指令选择 → 寄存器分配 → 汇编生成 → 链接。每一个环节都可以单独暂停、观察、分析。

本章通过一个简单的 C 程序，带你逐步穿越整条流水线。我们不展开源码细节（那是卷三的任务），而是建立对"编译器在做什么"的朴素认知——这对后续学习 LLVM IR、优化 Pass、后端代码生成都至关重要。

---

## 1.3.1 准备实验材料

创建一个包含一些"有意思的 C 语言特性"的测试程序：

```c
/* test.c — 我们的实验样本 */
#include <stdio.h>

int global_counter = 0;

int add(int a, int b) {
    return a + b;
}

int multiply_and_add(int x, int y, int z) {
    return add(x * y, z);
}

int main() {
    int a = 10, b = 20, c = 30;
    int result = multiply_and_add(a, b, c);
    printf("Result: %d (after %d calls)\n", result, global_counter + 1);

    // 故意加入一些可以被优化消除的代码
    int dead_variable = 42;
    int unused = dead_variable * 2;  // 无用，会被消除

    return 0;
}
```

这个程序包含了 LLVM 优化器擅长处理的多种模式：
- **函数调用**（`add`、`multiply_and_add`）：给 Inliner 提供材料
- **算术表达式**（`x * y + z`）：给 InstCombine 提供模式匹配材料
- **常量参数**（`10, 20, 30`）：给常量折叠提供材料
- **死代码**（`unused` 变量）：给 DCE 提供材料

---

## 1.3.2 编译管线全景图

```
                    ┌─────────────────────────────────────────────┐
                    │           Clang 驱动 (clang 可执行文件)        │
                    │  解析命令行 → 调度子进程 → 调用系统工具        │
                    └─────────────────────────────────────────────┘
                                        │
        ┌───────────┬───────────┬───────┴───────┬───────────┬───────────┐
        ▼           ▼           ▼               ▼           ▼           ▼

   ┌─────────┐ ┌─────────┐ ┌─────────┐   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │预处理    │→│词法分析  │→│语法分析  │→  │语义分析  │→│IR 生成   │→│IR 优化   │
   │-E       │ │Lexer    │ │Parser   │   │Sema     │ │CodeGen  │ │opt      │
   │test.c   │ │Token流  │ │AST      │   │带类型AST │ │LLVM IR  │ │优化后IR  │
   │  ↓      │ │  ↓      │ │  ↓      │   │  ↓      │ │  ↓      │ │  ↓      │
   │test.i   │ │         │ │         │   │         │ │test.ll  │ │(内部)    │
   └─────────┘ └─────────┘ └─────────┘   └─────────┘ └─────────┘ └─────────┘
                                                             │
                                    ┌────────────────────────┘
                                    ▼
   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
   │指令选择       │→│寄存器分配     │→│指令调度       │→│汇编输出       │
   │ISel          │ │RegAlloc      │ │Scheduler     │ │AsmPrinter    │
   │DAG→MachineI  │ │VirtReg→Phys  │ │重排指令顺序    │ │MI→文本 .s    │
   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
                                                                    │
                                                                    ▼
                                                             ┌──────────────┐
                                                             │汇编器 + 链接器│
                                                             │as + ld (或lld)│
                                                             │.s→.o→a.out   │
                                                             └──────────────┘
```

> 💡 **关键认知**：`clang` 这个可执行文件是一个**驱动（Driver）**，它自己不直接做编译工作。它解析命令行参数，然后调用 `clang -cc1`（真正的编译器核心）、系统汇编器（或 LLVM 集成汇编器）和链接器（或 LLD）。`clang -###` 可以看到完整的命令序列。

---

## 1.3.3 阶段一：预处理（-E）

预处理是编译管线的第一步，在**词法分析之前**执行。它处理 C/C++ 的预处理器指令：

```bash
./build/bin/clang -E test.c -o test.i
```

`test.i` 的内容是什么？让我们检查：

```bash
# 查看预处理后文件的行数
wc -l test.i
# 典型输出：约 20000 行！

# 查看最后几十行（我们自己的代码）
tail -40 test.i
```

预处理做了以下事情：

1. **展开 `#include`**：将 `stdio.h`（以及它间接包含的几十个头文件）的内容插入文件
2. **替换宏**：处理 `#define` 定义
3. **条件编译**：根据 `#ifdef`/`#ifndef` 选择保留哪些代码
4. **删除注释**：所有 `//` 和 `/* */` 被移除
5. **添加行号标记**：`# linenum "filename"` — 用于后续阶段的错误报告

预处理的输出可能非常巨大（2 万行！），因为 `stdio.h` 会递归包含 `<stddef.h>`, `<stdarg.h>`, `<bits/types.h>` 等。但这就是为什么编译阶段需要高效的原因之一。

---

## 1.3.4 阶段二：查看词法分析（Token 流）

虽然不能直接在命令行查看 Token 流，但可以用 `clang -dump-tokens`：

```bash
./build/bin/clang -dump-tokens test.c 2>&1 | head -40
```

输出示例：
```
int 'int'        [StartOfLine]  Loc=<test.c:5:1>
identifier 'add'               Loc=<test.c:5:5>
l_paren '('                    Loc=<test.c:5:8>
int 'int'                      Loc=<test.c:5:9>
identifier 'a'                 Loc=<test.c:5:13>
comma ','                      Loc=<test.c:5:14>
int 'int'                      Loc=<test.c:5:16>
identifier 'b'                 Loc=<test.c:5:20>
r_paren ')'                    Loc=<test.c:5:21>
l_brace '{'                    Loc=<test.c:5:23>
return 'return'                Loc=<test.c:6:5>
identifier 'a'                 Loc=<test.c:6:12>
plus '+'                       Loc=<test.c:6:14>
identifier 'b'                 Loc=<test.c:6:16>
semi ';'                       Loc=<test.c:6:17>
r_brace '}'                    Loc=<test.c:7:1>
...
```

关键观察：
- 注释已经没了（预处理消除了）
- 每个语言元素被识为一个 **Token**：关键字（`int`、`return`）、标识符（`add`、`a`）、标点（`(`、`)`、`{`）、运算符（`+`）、分隔符（`;`）
- Token 携带了其**源代码位置**（文件、行号、列号），这对错误报告至关重要

---

## 1.3.5 阶段三：查看 AST（抽象语法树）

AST 是源代码的树状结构表示。查看完整 AST：

```bash
./build/bin/clang -Xclang -ast-dump -fsyntax-only test.c 2>&1 | head -80
```

这个命令的输出可能非常大（数百行）。AST 中的每个节点代表一个语法结构。以 `add` 函数为例，简化后的 AST 结构：

```
FunctionDecl 'add' (int (int, int))
├── ParmVarDecl 'a' (int)
├── ParmVarDecl 'b' (int)
└── CompoundStmt
    └── ReturnStmt
        └── BinaryOperator '+'
            ├── ImplicitCastExpr (LValueToRValue)
            │   └── DeclRefExpr 'a'
            └── ImplicitCastExpr (LValueToRValue)
                └── DeclRefExpr 'b'
```

注意 AST 中出现了 `ImplicitCastExpr`（隐式类型转换）——Clang 在语义分析阶段插入了这些转换，使 AST 完整反映了 C 语言的语义。

**`-ast-dump` vs `-ast-view`**：

```bash
# 文本形式的 AST（总是可用）
clang -Xclang -ast-dump -fsyntax-only test.c

# 图形化 AST（需要 Graphviz）
clang -Xclang -ast-view -fsyntax-only test.c
# 会生成一个 .dot 文件并用 dot 渲染为图像
```

---

## 1.3.6 阶段四：生成 LLVM IR — 未优化的版本

这是最关键的一步。Clang CodeGen 将 AST 转换为 LLVM IR：

```bash
# 生成未优化的 LLVM IR（-O0）
./build/bin/clang -S -emit-llvm -O0 test.c -o test_O0.ll
```

查看生成的 IR：

```llvm
; test_O0.ll — 未优化的 LLVM IR

; ModuleID 标识了编译单元
; ModuleID = 'test.c'
source_filename = "test.c"
target datalayout = "e-m:e-p270:32:32-p271:32:32-p272:64:64-i64:64-i128:128-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-linux-gnu"

; 常量字符串
@.str = private unnamed_addr constant [31 x i8] c"Result: %d (after %d calls)\0A\00", align 1
; 全局变量
@global_counter = dso_local global i32 0, align 4

; add 函数 — 注意 O0 的"冗长"翻译
define dso_local i32 @add(i32 noundef %a, i32 noundef %b) #0 {
entry:
  %a.addr = alloca i32, align 4       ; 在栈上为 %a 分配空间
  %b.addr = alloca i32, align 4       ; 在栈上为 %b 分配空间
  store i32 %a, ptr %a.addr, align 4  ; 将参数存入栈
  store i32 %b, ptr %b.addr, align 4  ; 将参数存入栈
  %0 = load i32, ptr %a.addr, align 4 ; 从栈读出
  %1 = load i32, ptr %b.addr, align 4 ; 从栈读出
  %add = add nsw i32 %0, %1           ; 执行加法
  ret i32 %add                         ; 返回结果
}

; multiply_and_add 函数
define dso_local i32 @multiply_and_add(i32 noundef %x, i32 noundef %y,
                                        i32 noundef %z) #0 {
entry:
  %x.addr = alloca i32, align 4
  %y.addr = alloca i32, align 4
  %z.addr = alloca i32, align 4
  store i32 %x, ptr %x.addr, align 4
  store i32 %y, ptr %y.addr, align 4
  store i32 %z, ptr %z.addr, align 4
  %0 = load i32, ptr %x.addr, align 4
  %1 = load i32, ptr %y.addr, align 4
  %mul = mul nsw i32 %0, %1           ; x * y
  %2 = load i32, ptr %z.addr, align 4
  %call = call i32 @add(i32 noundef %mul, i32 noundef %2)  ; add(x*y, z)
  ret i32 %call
}

; main 函数 — 包含死代码
define dso_local i32 @main() #0 {
entry:
  %retval = alloca i32, align 4
  %a = alloca i32, align 4
  %b = alloca i32, align 4
  %c = alloca i32, align 4
  %result = alloca i32, align 4
  %dead_variable = alloca i32, align 4
  %unused = alloca i32, align 4
  store i32 0, ptr %retval, align 4
  store i32 10, ptr %a, align 4
  store i32 20, ptr %b, align 4
  store i32 30, ptr %c, align 4
  %0 = load i32, ptr %a, align 4
  %1 = load i32, ptr %b, align 4
  %2 = load i32, ptr %c, align 4
  %call = call i32 @multiply_and_add(i32 noundef %0,
                                      i32 noundef %1,
                                      i32 noundef %2)
  store i32 %call, ptr %result, align 4
  store i32 42, ptr %dead_variable, align 4
  %3 = load i32, ptr %dead_variable, align 4
  %mul = mul nsw i32 %3, 2
  store i32 %mul, ptr %unused, align 4
  %4 = load i32, ptr %result, align 4
  %5 = load i32, ptr @global_counter, align 4
  %add = add nsw i32 %5, 1
  %call1 = call i32 (ptr, ...) @printf(ptr noundef @.str,
                                        i32 noundef %4,
                                        i32 noundef %add)
  ret i32 0
}
```

### 理解 O0 IR 的关键特征

1. **每个局部变量 = alloca + store + load 序列**：即使是简单函数如 `add`，参数也要 `alloca`（栈分配）、`store`（存入）、`load`（读出）。这种"啰嗦"是刻意的——简化了 CodeGen 的实现，后续的 `mem2reg` Pass 会自动消除它们。

2. **`noundef` 属性**：表示参数不会传递 `undef` 值。Clang 在已知参数来源合法时会自动添加这个属性，让优化器可以做更多假设。

3. **`dso_local`**：表示符号在同一个动态共享对象中可见。这是 ELF 的细节，与主要逻辑无关。

4. **`nsw`（No Signed Wrap）**：`add nsw i32 ...` 保证不会发生有符号溢出。来自 C 语言的有符号整数溢出是 UB（未定义行为）的语义。

---

## 1.3.7 阶段五：IR 优化 — 从 O0 到 O2 的蜕变

现在我们见证优化的力量。分别生成四个优化级别的 IR：

```bash
./build/bin/clang -S -emit-llvm -O1 test.c -o test_O1.ll
./build/bin/clang -S -emit-llvm -O2 test.c -o test_O2.ll
./build/bin/clang -S -emit-llvm -O3 test.c -o test_O3.ll
./build/bin/clang -S -emit-llvm -Oz test.c -o test_Oz.ll
```

让我们逐函数对比：

### add 函数的优化

| 优化级别 | IR 代码 | 说明 |
|---------|---------|------|
| O0 | 6 行（alloca+store+load+add+ret） | 直接翻译 |
| O1/O2/O3 | `%add = add nsw i32 %b, %a` + `ret` | mem2reg 消除了 alloca/store/load |

### multiply_and_add 函数的优化

O0：
```llvm
define i32 @multiply_and_add(i32 %x, i32 %y, i32 %z) {
  %x.addr = alloca i32
  %y.addr = alloca i32
  %z.addr = alloca i32
  store i32 %x, ptr %x.addr
  store i32 %y, ptr %y.addr
  store i32 %z, ptr %z.addr
  %0 = load i32, ptr %x.addr
  %1 = load i32, ptr %y.addr
  %mul = mul nsw i32 %0, %1
  %2 = load i32, ptr %z.addr
  %call = call i32 @add(i32 %mul, i32 %2)
  ret i32 %call
}
```

O2：
```llvm
define i32 @multiply_and_add(i32 %x, i32 %y, i32 %z) {
  %mul = mul nsw i32 %y, %x
  %add.i = add nsw i32 %mul, %z
  ret i32 %add.i
}
```

发生了什么？
1. **mem2reg**：消除了 alloca/store/load
2. **Inliner**：将 `add` 内联（`add.i = mul + z`），整个函数变成两条指令
3. `add` 是一个极小的函数（单条指令），内联阈值计算认为"内联的收益 > 代价"

### main 函数的优化 — 最戏剧性

O0 的 main 有 30+ 条指令。O2 的 main（简化显示）：

```llvm
define i32 @main() local_unnamed_addr {
  %1 = load i32, ptr @global_counter, align 4
  %add.i = add nsw i32 %1, 1
  %call1 = call i32 (ptr, ...) @printf(ptr @.str, i32 230, i32 %add.i)
  ret i32 0
}
```

发生的变换：

1. **常量传播 + 常量折叠**：
   - `a = 10, b = 20, c = 30` → 常量
   - `multiply_and_add(10, 20, 30)` → 内联 → `10*20 + 30 = 200 + 30 = 230`
   - 整个 `multiply_and_add` 调用消失！被折叠为常量 `230`

2. **死代码消除（DCE）**：
   - `dead_variable = 42` → 从未被读取使用 → 消除
   - `unused = dead_variable * 2` → 同样消除

3. **常量折叠**：
   - `global_counter + 1` 中，`global_counter` 的初始值是 0（可以被追踪到），但因为是全局变量（可能被其他编译单元修改），不能折叠为 1

> 💡 **关键认知**：优化的"连锁反应"——内联暴露常量，常量简化算术，简化后的算术让更多指令成为死代码，死代码消除后进一步暴露优化机会。这就是为什么优化 Pass 需要重复多次执行（InstCombine 在 O2 管线中运行 5-6 次）。

---

## 1.3.8 手动运行优化 Pass

我们可以用 `opt` 手动控制优化 Pass，观察每个 Pass 的独立效果：

```bash
# 只运行 mem2reg（标量替换，将栈变量提升为 SSA 寄存器）
./build/bin/opt -passes=mem2reg test_O0.ll -S -o test_mem2reg.ll

# 只运行 instcombine
./build/bin/opt -passes=instcombine test_O0.ll -S -o test_instcombine.ll

# 只运行内联
./build/bin/opt -passes=inline test_O0.ll -S -o test_inline.ll

# 完整 O2 优化管线（新 Pass 管理器）
./build/bin/opt -passes='default<O2>' test_O0.ll -S -o test_full_O2.ll
```

**观察每个 Pass 的变换**：

```bash
# 打印每个 Pass 前后的 IR，过滤只看 main 函数
./build/bin/opt -passes='mem2reg,instcombine,inline' \
    -print-changed -filter-print-funcs=main \
    test_O0.ll -S -o /dev/null 2>&1
```

---

## 1.3.9 阶段六：从 IR 到汇编

```bash
# 用 llc 生成汇编
./build/bin/llc -O2 test_O2.ll -o test.s
```

查看生成的汇编代码（精简显示）：

```asm
    .text
    .globl  add
    .type   add, @function
add:                                    # @add
    leal    (%rdi,%rsi), %eax           # dst = src1 + src2 (一条指令！)
    retq

    .globl  multiply_and_add
    .type   multiply_and_add, @function
multiply_and_add:                       # @multiply_and_add
    imull   %esi, %edi                  # %edi = x * y
    leal    (%rdi,%rdx), %eax           # %eax = (x*y) + z
    retq

    .globl  main
    .type   main, @function
main:
    pushq   %rbx
    movl    global_counter(%rip), %ebx
    leal    1(%rbx), %esi
    leaq    .L.str(%rip), %rdi
    movl    $230, %esi
    xorl    %eax, %eax
    callq   printf@PLT
    xorl    %eax, %eax
    popq    %rbx
    retq
```

关键观察：
1. `add` 变成了一条 `leal` 指令（X86 的"加载有效地址"指令常被用于简单算术）
2. `multiply_and_add` 变成了两条指令（`imull` + `leal`），完全内联
3. `main` 中出现了 `$230` —— 编译期计算出的 `10*20+30` 的结果
4. 没有 `$42`、没有 `dead_variable` —— 死代码已被消除

---

## 1.3.10 阶段七：目标文件（.o）和反汇编

```bash
# 生成目标文件
./build/bin/clang -c -O2 test.c -o test.o

# 用 llvm-objdump 反汇编
./build/bin/llvm-objdump -d test.o

# 查看 Section Header
./build/bin/llvm-objdump -h test.o

# 查看符号表
./build/bin/llvm-nm test.o

# 查看重定位表
./build/bin/llvm-readelf -r test.o
```

---

## 1.3.11 阶段八：链接

```bash
# 一步链接
./build/bin/clang -O2 test.c -o test

# 查看内部的链接命令
./build/bin/clang -### -O2 test.c -o test 2>&1 | grep -E '"ld"|"lld"|collect2'

# 运行
./test
# 输出: Result: 230 (after 1 calls)
```

---

## 1.3.12 用 -### 看全貌

这是理解 Clang 驱动行为的最佳命令：

```bash
./build/bin/clang -### -O2 test.c -o test 2>&1
```

输出示例（简化）：
```
"/path/to/clang" "-cc1" "-triple" "x86_64-pc-linux-gnu" "-emit-obj"
    "-O2" "-o" "/tmp/test-abc123.o" "-x" "c" "test.c"
"/usr/bin/ld" "-o" "test" "/tmp/test-abc123.o" "-lc" "-lstdc++" ...
```

注意：
- `-cc1` 是真正的编译器进程（前端 + 中端优化 + 后端代码生成）
- 链接器（`/usr/bin/ld` 或 `lld`）是独立的系统工具
- 驱动负责协调这些组件

---

## 1.3.13 完整命令速查

```bash
# 分步编译
clang -E test.c -o test.i                  # 1. 预处理
clang -fsyntax-only test.c                 # 2. 只做语法语义检查
clang -S -emit-llvm -O0 test.c -o test.ll  # 3. 生成 IR (未优化)
opt -passes='default<O2>' test.ll -S -o test_opt.ll  # 4. 优化 IR
llc test_opt.ll -o test.s                  # 5. 生成汇编
clang -c test.s -o test.o                  # 6. 汇编为目标文件
clang test.o -o test                       # 7. 链接

# 最常用的快捷键
clang -S -emit-llvm -O2 test.c   # 一步生成优化后的 IR
clang -S -O2 test.c              # 一步生成汇编
clang -### -O2 test.c            # 查看内部命令
clang -save-temps -O2 test.c     # 保留所有中间文件
```

---

## 1.3.14 练习

<div class="exercise">

### 基础练习

1. 用 `-E` 预处理一个包含 `#include <stdio.h>` 的 C 程序，统计预处理后的代码行数。寻找你的原始代码在预处理后文件的什么位置。
2. 用 `-S -emit-llvm -O0` 和 `-O2` 分别生成 IR，对比 `add` 函数的差异。解释每个指令的消失原因。
3. 用 `-ast-dump` 查看一个包含 `if/else` 语句的程序的 AST，注意 AST 中如何处理条件分支。

### 进阶练习

4. 写一个递归阶乘函数 `int factorial(int n)`，对比 O0 和 O2 的 IR 差异。O2 是否将递归优化掉了？（提示：LLVM 的 TailRecursionElimination Pass）
5. 实验死代码消除：在 `main` 中添加各种无用的计算（如 `int x = 1+2+3+4; int y = x * 0;`），观察 O2 如何优化它们。
6. 用 `opt -passes='mem2reg,instcombine,simplifycfg'` 逐步优化一个包含 if/else 的 O0 IR，观察每个 Pass 对齐变换的贡献。

### 挑战练习

7. 用 `-mllvm -print-after-all` 观察完整的 O2 优化过程（大约 50 个 Pass），查看每个 Pass 对 IR 的修改。尝试识别以下关键 Pass 的效果：
   - `mem2reg`（消除 alloca/store/load）
   - `instcombine`（组合简化指令）
   - `inline`（内联函数调用）
   - `simplifycfg`（简化控制流图）
   - `gvn`（消除冗余 load）
8. 写一个包含 `volatile` 变量的 C 程序，观察 `volatile` 如何阻止优化器消除看似"无用的" load/store 指令。

</div>

---

<div class="exercise">

### 本章要点回顾

- `clang` 是一个驱动，`clang -cc1` 是真正的编译器核心
- O0 IR 是 C 代码的直译（alloca + store + load），O2 IR 经过 mem2reg + 内联 + 常量折叠 + DCE
- 优化的本质是"连锁反应"：内联暴露常量 → 常量简化算术 → 简化后出现死代码 → DCE 消除
- `-emit-llvm` 查看 IR，`-S` 查看汇编，`-###` 查看驱动调用的所有子命令
- `llvm-objdump` 是分析目标文件的瑞士军刀

</div>
