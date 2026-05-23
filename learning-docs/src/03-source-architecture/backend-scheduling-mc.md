# 3.9 指令调度与 MC 层

> **学习目标**：理解指令调度器的原理和 MC 层（Machine Code 层）的工作方式。

---

## 3.9.1 指令调度

指令调度重排指令顺序以利用 CPU 流水线，同时不改变程序语义：

```
未调度：
  ADD EAX, EBX           ← EAX ready at cycle 2
  MOV [mem], EAX         ← 在周期 1 必须停顿！等待 EAX

调度后：
  ADD EAX, EBX           ← 周期 0
  XOR EDX, EDX           ← 周期 0（无依赖，并行执行）
  MOV [mem], EAX          ← 周期 2（EAX 已就绪）
```

### 列表调度算法

```
1. 构建调度 DAG（数据依赖 + 内存依赖）
2. 每个节点计算"高度"（到根的路径长度）
3. 维护"就绪列表"（所有前驱已调度的节点）
4. 每个周期，选高度最高的就绪节点调度
5. 重复直到所有节点被调度
```

### 代码位置

```
llvm/lib/CodeGen/MachineScheduler.cpp       # 主调度器
llvm/lib/CodeGen/PostRASchedulerList.cpp    # 分配后微调
```

---

## 3.9.2 MC 层（Machine Code Layer）

MC 层是 LLVM 最底层的模块，处理从 MachineInstr 到最终输出的所有工作。

### MC 对象

| 对象 | 说明 |
|------|------|
| `MCInst` | 最终的指令表示（轻量，只有 opcode + 操作数） |
| `MCOperand` | 操作数（寄存器/立即数/表达式/浮点数） |
| `MCExpr` | 可重定位表达式（符号引用、加法、减法） |
| `MCSymbol` | 符号（如 `main`, `printf`） |
| `MCSection` | Section（如 `.text`, `.data`） |
| `MCFragment` | Section 内的片段 |

### MCStreamer — 输出流

两种主要实现：
- `MCAsmStreamer`：将 MCInst 格式化为文本汇编（`.s` 文件）
- `MCObjectStreamer`：将 MCInst 编码为二进制，写入 `.o` 文件

### 从 MachineInstr 到 MCInst

```
MachineInstr (MIR层, 包含虚拟寄存器、操作数种类)
    ↓ X86MCInstLower::Lower()
MCInst (MC层, opcode + MCOperand 列表)
    ↓ MCStreamer
文本汇编 (.s) 或 目标文件 (.o)
```

---

## 3.9.3 集成汇编器（IAS）

LLVM 内置了完整的汇编器，可直接从 IR 生成目标文件，无需调用外部 `as`：

```bash
llc -filetype=obj input.ll -o output.o   # 生成 .o（使用集成汇编器）
llc -filetype=asm input.ll -o output.s   # 生成 .s（文本汇编）
```

### 练习

1. 用 `-print-after-all` 观察指令调度前后的指令顺序变化
2. 对比 `-filetype=asm` 和 `-filetype=obj` 的输出

