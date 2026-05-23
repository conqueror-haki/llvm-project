# 2.5 llc 代码生成

> **学习目标**：掌握 llc 的使用——从 IR 到汇编、到目标文件，理解后端选项和调试工具。
>
> **前置知识**：理解 LLVM IR（第 2.3 章），了解基本的 CPU 指令概念。

---

## 本章导读

`llc`（LLVM Static Compiler）将 LLVM IR 翻译为目标平台的汇编代码或目标文件。它是 LLVM 后端的入口。

---

## 2.5.1 基本用法

```bash
# IR → 汇编（默认目标为当前主机）
llc input.ll -o output.s

# IR → 目标文件
llc -filetype=obj input.ll -o output.o

# 查看输出类型
llc -filetype=asm input.ll    # 文本汇编（默认）
llc -filetype=obj input.ll    # 二进制目标文件
llc -filetype=null input.ll   # 无输出（只检查编译是否成功）
```

---

## 2.5.2 指定目标平台

通过 `-mtriple` 选择目标架构和操作系统：

```bash
# X86-64 Linux
llc -mtriple=x86_64-pc-linux-gnu input.ll -o x64.s

# AArch64 (ARM64)
llc -mtriple=aarch64-linux-gnu input.ll -o a64.s

# RISC-V 64
llc -mtriple=riscv64-linux-gnu input.ll -o riscv.s

# WebAssembly
llc -mtriple=wasm32-unknown-unknown input.ll -o wasm.o

# BPF (eBPF，Linux 内核)
llc -mtriple=bpf input.ll -o bpf.o

# 32 位 ARM
llc -mtriple=arm-linux-gnueabihf input.ll -o arm32.s
```

triple 的格式：`<architecture>-<vendor>-<operating_system>[-<environment>]`。

---

## 2.5.3 指定 CPU 微架构

```bash
# X86
llc -mcpu=skylake input.ll -o skylake.s
llc -mcpu=znver4 input.ll -o znver4.s     # AMD Zen 4

# AArch64
llc -mcpu=cortex-a76 input.ll -o a76.s
llc -mcpu=apple-m1 input.ll -o m1.s

# 启用/禁用目标特性
llc -mattr=+avx2 input.ll -o avx2.s       # 启用 AVX2
llc -mattr=-sse input.ll -o nosse.s       # 禁用 SSE

# 查看目标 CPU 支持的特性
llc -mcpu=help 2>&1 | head -40
```

---

## 2.5.4 后端优化级别

`llc` 也有自己的 `-O` 选项——它控制的是**后端**（指令选择、寄存器分配、指令调度）的优化强度：

| 级别 | 指令选择 | 寄存器分配 | 指令调度 | 优化范围 |
|------|---------|----------|---------|---------|
| -O0 | FastISel | Fast | 无 | 基本块内 |
| -O1 | SelectionDAG | Basic | 简单列表调度 | 函数内 |
| -O2 | SelectionDAG | Greedy | 标准调度 | 函数内（默认） |
| -O3 | SelectionDAG | Greedy | 激进调度 | 函数间 |

```bash
# 典型用法：IR 已经优化过，后端用 O2
llc -O2 input_optimized.ll -o output.s

# 快速编译：后端不优化（+ 前端优化的组合很好用）
llc -O0 input_optimized.ll -o output.s
```

---

## 2.5.5 后端调试工具

```bash
# 查看指令选择过程（SelectionDAG）
llc -debug-only=isel input.ll -o /dev/null 2>&1

# 查看寄存器分配过程
llc -debug-only=regalloc input.ll -o /dev/null 2>&1

# 在每个后端 Pass 前后打印 Machine IR
llc -print-before-all -print-after-all input.ll -o /dev/null 2>&1

# 停止在特定 Pass 之后，输出 MIR
llc -stop-after=regalloc input.ll -o pre_ra.mir

# 输出后端 Pass 管线
llc -debug-pass=Structure input.ll -o /dev/null 2>&1
```

---

## 2.5.6 常用后端选项

```bash
# 重定位模型
llc -relocation-model=static input.ll    # 静态链接
llc -relocation-model=pic input.ll       # 位置无关代码（共享库用）

# 帧指针控制
llc -frame-pointer=all input.ll          # 总是保留帧指针（方便调试）
llc -frame-pointer=none input.ll         # 省略帧指针（O2 默认）

# 异常处理模型
llc -exception-model=dwarf input.ll       # DWARF 栈展开
llc -exception-model=sjlj input.ll        # setjmp/longjmp 方式

# 生成的调试信息 DWARF 版本
llc -dwarf-version=5 input.ll

# 代码模型
llc -code-model=small input.ll           # 小代码模型（符号在 2GB 内）
llc -code-model=large input.ll           # 大代码模型
```

---

## 2.5.7 从 IR 到机器码的完整历程

```
LLVM IR (.ll)
    ↓
SelectionDAG 构建 (DAG Builder)
    ↓
DAG 合法化 (LegalizeTypes + LegalizeDAG)
    ↓
DAG 合并 (DAGCombiner)
    ↓
指令选择 (ISel: DAG → Machine DAG)
    ↓
PHI 消除 + SSA 销毁 (指令从 SSA 形式转为机器形式)
    ↓
寄存器分配 (VirtReg → PhysReg + Spill)
    ↓
指令调度 (重排指令顺序以利用流水线)
    ↓
帧索引消除 (FrameIndex → 实际栈偏移)
    ↓
序言/尾声插入 (函数入口/出口的栈操作)
    ↓
MC 层降低 (MachineInstr → MCInst)
    ↓
汇编输出 / 目标文件写入
```

---

## 2.5.8 练习

<div class="exercise">

### 基础练习

1. 用 `-mtriple` 将同一个 IR 编译到 3 个不同的目标平台，对比生成的汇编。
2. 用 `-mcpu=pentium4` 和 `-mcpu=skylake` 编译同一 IR，观察指令差异。

### 进阶练习

3. 用 `-debug-only=isel` 观察指令选择的详细过程。
4. 用 `-print-after-all` 观察后端 Pass 管线完整执行过程。

</div>
