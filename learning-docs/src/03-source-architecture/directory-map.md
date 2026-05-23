# 3.1 代码目录地图

> **学习目标**：认知 LLVM 源码树的组织结构，能根据功能快速定位到对应的源文件。
>
> **前置知识**：完成卷二的使用篇学习。

---

## 本章导读

LLVM 源码有 10M+ 行代码，分布在数千个文件中。盲目打开文件是最低效的学习方式。本章提供一张"代码地图"——按功能而非文件名的逻辑组织。

每个目录条目包含：
- **定位** — 目录路径
- **职责** — 这个目录做什么
- **关键文件** — 该从哪里开始阅读
- **依赖关系** — 它被谁依赖，依赖谁

---

## 3.1.1 llvm/ 核心目录

### lib/IR/ — LLVM IR 核心实现

```
llvm/lib/IR/      (源码)
llvm/include/llvm/IR/  (头文件)
```

| 文件 | 职责 | 阅读优先级 |
|------|------|----------|
| `Value.cpp` | Value 基类——IR 中几乎所有东西都是 Value | ★★★★★ |
| `User.cpp` | User 基类——使用其他 Value 的对象 | ★★★★★ |
| `Use.cpp` | Use 类——连接 User 和 Value 的"边" | ★★★★★ |
| `Type.cpp` | 类型系统（IntegerType, StructType 等） | ★★★★ |
| `Function.cpp` | 函数——包含 BasicBlock 列表 | ★★★★★ |
| `BasicBlock.cpp` | 基本块——包含 Instruction 列表 | ★★★★★ |
| `Instruction.cpp` | 指令基类 | ★★★★★ |
| `Instructions.cpp` | 所有具体指令类（BinaryOperator、PHINode 等） | ★★★ |
| `Constants.cpp` | 常量（ConstantInt, ConstantFP 等） | ★★★ |
| `Verifier.cpp` | IR 验证器 | ★★★ |
| `Module.cpp` | 编译单元 | ★★★★ |
| `DataLayout.cpp` | 目标平台数据布局 | ★★★ |

### lib/Transforms/ — 优化 Pass 集合

```
llvm/lib/Transforms/
├── Scalar/          ★★★★★ 标量优化（GVN、SimplifyCFG、LICM 等）
├── IPO/             ★★★★★ 过程间优化（Inliner、GlobalOpt 等）
├── Vectorize/       ★★★★ 向量化（LoopVectorize、SLPVectorize）
├── InstCombine/     ★★★★★ 指令合并（最大的单 Pass，~30000 行）
├── Utils/           ★★★ Pass 辅助工具
├── Instrumentation/ ★★★ 插桩（ASan、PGO）
└── ...
```

关键文件：
| 文件 | 职责 | 难度 |
|------|------|------|
| `Scalar/GVN.cpp` | 全局值编号 | 中 |
| `Scalar/SimplifyCFG.cpp` | 控制流图简化 | 中 |
| `Scalar/LICM.cpp` | 循环不变量外提 | 中 |
| `Scalar/SROA.cpp` | 标量替换聚合体 | 难 |
| `IPO/Inliner.cpp` | 内联决策和执行 | 中 |
| `IPO/GlobalOpt.cpp` | 全局变量优化 | 中 |
| `Vectorize/LoopVectorize.cpp` | 循环向量化 | 很难 |
| `InstCombine/InstCombineAddSub.cpp` | add/sub 的合并 | 简单 |
| `InstCombine/InstCombineCasts.cpp` | 类型转换合并 | 简单 |

### lib/CodeGen/ — 后端基础设施（目标无关）

```
llvm/lib/CodeGen/
├── SelectionDAG/       ★★★★★ 指令选择框架核心
│   ├── SelectionDAGBuilder.cpp    # IR → DAG
│   ├── DAGCombiner.cpp           # DAG 上的 InstCombine
│   ├── LegalizeTypes.cpp         # 类型合法化
│   └── LegalizeDAG.cpp           # DAG 操作合法化
├── MachineScheduler.cpp  ★★ 指令调度
├── RegisterCoalescer.cpp  ★★★ 寄存器合并
├── PrologEpilogInserter.cpp  ★★ 函数序言/尾声
└── ...
```

### lib/Target/ — 各目标架构后端

```
llvm/lib/Target/
├── X86/            ★★★★★ 最成熟的后端，学习首选
│   ├── X86.td                    # TableGen 入口
│   ├── X86ISelLowering.cpp       # 自定义 Lowering（~10000 行）
│   ├── X86ISelDAGToDAG.cpp       # 手动指令选择
│   ├── X86InstrInfo.td           # 指令定义
│   └── X86RegisterInfo.td        # 寄存器定义
├── AArch64/        ★★★★ ARM64 后端，第二成熟
├── RISCV/          ★★★  开源 ISA，快速成长
└── ...
```

### lib/Analysis/ — 分析 Pass

```
llvm/lib/Analysis/
├── BasicAliasAnalysis.cpp    # 基本别名分析
├── TypeBasedAliasAnalysis.cpp # TBAA
├── LoopInfo.cpp              # 循环分析
├── Dominators.cpp            # 支配树
├── ScalarEvolution.cpp       # 标量演化（最重要也最复杂的分析）
├── InlineCost.cpp            # 内联代价计算
└── ValueTracking.cpp         # 值追踪
```

### lib/Support/ — LLVM 的标准库

```
llvm/lib/Support/
├── raw_ostream.cpp         # 输出流（替代 std::ostream）
├── CommandLine.cpp         # 命令行参数解析
├── MemoryBuffer.cpp        # 内存映射文件
├── Error.cpp / ErrorHandling.cpp  # 错误处理
└── ...
```

### lib/MC/ — 机器码层

```
llvm/lib/MC/
├── MCAsmStreamer.cpp       # 汇编文本输出
├── MCELFStreamer.cpp       # ELF 二进制输出
├── MCInst.cpp              # MC 指令表示
└── MCDisassembler.cpp      # 反汇编器接口
```

---

## 3.1.2 clang/ 目录

### 前端核心模块

```
clang/lib/
├── Lex/             ★★★ 词法分析（Lexer、Preprocessor）
├── Parse/           ★★★ 语法分析（递归下降 Parser）
├── Sema/            ★★★★★ 语义分析（最大的模块，~40000 行）
│   ├── SemaExpr.cpp    — 表达式语义分析（>6000 行）
│   ├── SemaDecl.cpp    — 声明处理
│   ├── SemaOverload.cpp — C++ 重载决议
│   └── SemaTemplate.cpp — 模板实例化
├── CodeGen/         ★★★★★ IR 生成（AST → LLVM IR）
│   ├── CodeGenModule.cpp — Module 级代码生成
│   ├── CodeGenFunction.cpp — Function 级
│   └── CGExpr.cpp — 表达式代码生成（>6000 行）
├── AST/             ★★★★ AST 节点实现
├── StaticAnalyzer/  ★★ 静态分析
└── ...
```

---

## 3.1.3 阅读路径建议

### 路径 A：新手（从工具到核心）

```
第1天：llvm/lib/Support/           → 理解"LLVM 的标准库"
第2天：llvm/lib/IR/                 → 理解 IR 的核心数据结构
第3天：llvm/lib/Transforms/InstCombine/ → 看最大的 Pass 如何工作
第4天：llvm/lib/Target/X86/         → 理解后端的 TableGen 体系
```

### 路径 B：前端倾向

```
第1天：clang/lib/Lex/              → 词法分析器
第2天：clang/lib/Parse/            → 语法分析器
第3天：clang/lib/Sema/             → 语义分析（重点）
第4天：clang/lib/CodeGen/          → AST → IR 转换
```

### 路径 C：后端倾向

```
第1天：llvm/lib/Target/X86/X86RegisterInfo.td  → 寄存器定义
第2天：llvm/lib/Target/X86/X86InstrInfo.td     → 指令定义
第3天：llvm/lib/CodeGen/SelectionDAG/          → 指令选择
第4天：llvm/lib/CodeGen/RegisterAllocation/    → 寄存器分配
```

---

## 3.1.4 练习

1. 在 llvm/lib/IR/ 中打开 Value.cpp，找到 Value::replaceAllUsesWith() 的实现
2. 在 llvm/lib/Transforms/InstCombine/ 中任选一个文件，阅读 visit 函数
3. 在 clang/lib/Sema/SemaExpr.cpp 中搜索 "CheckAssignment"，理解类型检查逻辑

