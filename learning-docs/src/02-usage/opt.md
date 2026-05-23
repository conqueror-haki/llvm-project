# 2.4 opt 优化器

> **学习目标**：掌握 `opt` 的使用方法，理解 Pass 管理器的两代架构，能够查看、调试和自定义优化管线。
>
> **前置知识**：理解 LLVM IR 的基本结构（第 2.3 章）。

---

## 本章导读

`opt` 是 LLVM 的 IR 到 IR 优化器。它是理解 LLVM 优化体系的**最佳实践工具**——你可以逐个 Pass 地观察 IR 如何被变换，也可以组合不同的 Pass 来实验优化效果。

本章从实用角度出发：如何运行 opt、如何查看 Pass 管线、如何调试 Pass 的行为、如何选择最佳的 Pass 组合。深入 Pass 的内部实现将在卷三（源码架构）中讨论。

---

## 2.4.1 Pass 管理器的两代架构

LLVM 有两代 Pass 管理器（Pass Manager, PM），目前（LLVM 16+）处于从 Legacy PM 到 New PM 的迁移期。

| 特性 | Legacy PM | New PM（默认，LLVM 16+） |
|------|-----------|--------------------------|
| CLI 语法 | `opt -instcombine` | `opt -passes=instcombine` |
| 注册方式 | `RegisterPass<MyPass>` 宏 | `PassInfoMixin` + 回调 |
| 分析缓存 | 手动管理 | 自动缓存 + 惰性计算 |
| 并行化 | 不支持 | 支持函数级并行 |
| 动态加载 | 无标准方式 | `-load-pass-plugin=libMyPass.so` |

> 📌 **后续所有例子使用 New PM 语法**（`-passes=...`）。

---

## 2.4.2 opt 的基本用法

```bash
# 查看 IR 文本（不运行任何 Pass）
opt -S input.ll -o /dev/null

# 运行单个 Pass
opt -passes=instcombine input.ll -S -o output.ll

# 运行 O2 优化管线
opt -passes='default<O2>' input.ll -S -o output.ll

# 运行多个 Pass（按顺序，逗号分隔）
opt -passes='mem2reg,instcombine,simplifycfg,gvn' input.ll -S

# 输入为 bitcode (.bc)
opt -passes=instcombine input.bc -S -o output.ll

# 不输出（只运行分析）
opt -passes='print<domtree>' input.ll -disable-output
```

常用选项：
| 选项 | 说明 |
|------|------|
| `-S` | 输出文本 IR（不加则输出二进制 bitcode） |
| `-o <file>` | 指定输出文件 |
| `-disable-output` | 不输出 IR（只运行 Pass） |
| `-time-passes` | 打印每个 Pass 的运行时间 |
| `-stats` | 打印 Pass 的变换统计 |

---

## 2.4.3 优化管线：O0 到 O3 详解

### 查看管线的 Pass 列表

```bash
# 查看 New PM 的 O2 管线
opt -passes='default<O2>' input.ll -S -debug-pass-manager 2>&1

# 查看 Legacy PM 的 O2 管线  
opt -O2 input.ll -S -debug-pass=Arguments 2>&1
```

### O0 管线

几乎不做任何优化。Pass 列表是空的（除了必要的规范化）。O0 的输出 ≈ 输入。

### O1 管线（约 30 个 Pass）

```
tti, targetlibinfo, ...
forceattrs, inferattrs       # 函数属性推断
ipsccp                       # 过程间稀疏条件常量传播
globalopt                    # 全局变量优化
mem2reg                      # 栈变量提升为 SSA 寄存器 ★
deadargelim                  # 死参数消除
instcombine                   # 指令合并 ★
simplifycfg                   # 控制流图简化 ★
sroa                          # 标量替换聚合体（aggregate scalar replacement）
early-cse                     # 早期公共子表达式消除
lower-expect                  # lower __builtin_expect
...
inline                        # 函数内联（阈值较低）★
...
```

### O2 管线（约 50 个 Pass）

在 O1 基础上增加：
```
gvn                          # 全局值编号 ★
loop-rotate                   # 循环旋转
licm                         # 循环不变量外提 ★
loop-unroll                   # 循环展开 ★
loop-vectorize                # 循环向量化 ★
slp-vectorize                # 基本块级向量化
aggressive-instcombine        # 激进指令合并
early-cse-memssa             # 内存 SSA 下的 CSE
```

### O3 管线（约 55 个 Pass）

在 O2 基础上进一步激进：
```
argpromotion                 # 参数提升（按引用 → 按值）
globalopt 更激进             
inline 更深的阈值
loop-unroll 更大的展开因子
```

### Os / Oz（体积优化）

使用一套**不同的管线的 Pass 组合**，优先减少代码体积：循环不展开、较少内联、不使用 loop-vectorize。

---

## 2.4.4 调试 Pass 的执行过程

### 查看每个 Pass 对 IR 的修改

```bash
# 在每个 Pass 之前打印 IR
opt -print-before-all -passes='default<O1>' input.ll -S 2>&1

# 在每个 Pass 之后打印 IR
opt -print-after-all -passes='default<O1>' input.ll -S 2>&1

# 只显示被修改的部分（推荐，输出更少）
opt -print-changed -passes='default<O1>' input.ll -S 2>&1

# 只过滤特定函数的变化
opt -print-changed -filter-print-funcs=foo -passes='default<O1>' input.ll -S 2>&1
```

### 查看特定 Pass 的调试日志

```bash
# 查看 InstCombine 的每一步变换
opt -debug-only=instcombine -passes=instcombine input.ll -S 2>&1

# 查看循环向量化的分析过程
opt -debug-only=loop-vectorize -passes=loop-vectorize input.ll -S 2>&1

# 查看所有可用的调试类型
opt -debug-only=help 2>&1
```

### 验证 IR 合法性

```bash
# 每个 Pass 后验证 IR 是否合法
opt -verify-each -passes='default<O1>' input.ll -S
```

---

## 2.4.5 常用分析 Pass

分析 Pass 不修改 IR，只提供分析结果：

```bash
# 打印支配树
opt -passes='print<domtree>' input.ll -disable-output

# 打印循环信息
opt -passes='print<loops>' input.ll -disable-output

# 打印调用图
opt -passes='print<cg>' input.ll -disable-output

# 打印别名分析结果
opt -passes='print<aa>' input.ll -disable-output

# 打印内存 SSA 形式
opt -passes='print<memoryssa>' input.ll -disable-output

# 打印标量演化
opt -passes='print<scalar-evolution>' input.ll -disable-output

# 打印所有函数属性
opt -passes='print<function-attrs>' input.ll -disable-output
```

---

## 2.4.6 常用优化 Pass 及其效果

### InstCombine（指令合并）

最频繁运行的 Pass。合并冗余的指令模式：

```
; 模式：  X + 0  →  X
;         X - 0  →  X
;         X * 1  →  X
;         X & 0  →  0
;         X | 0  →  X
;         X xor X →  0
;         (X << C1) >> C1 → 取决于类型和标记
;         ...
```

InstCombine 运行**5-6 次**（在 O2 管线中），因为每次合并可能暴露新的模式。

### SimplifyCFG（控制流图简化）

```
; if (true) { A } else { B }  →  A
; if (false) { A } else { B } →  B
; 消除只有一个前驱的基本块
; 将 if/else 转为 select（有利于后续优化）
```

### GVN（全局值编号）

```
; 消除冗余的 load（同一指针，中间无别名写）
; 消除冗余的计算（相同操作数 + 相同操作码）
; 在支配树上全局操作
```

### Inliner（函数内联）

```
; 将小函数体嵌入调用者的位置
; 消除 call/ret 指令开销
; 暴露常量参数给被调用函数
; 阈值：body 指令数 < 某个值（在 -O2 中约 225 条）
```

### LoopUnroll（循环展开）

```
; for i = 0..4: A[i] = B[i] + 1
; 展开为：
; A[0] = B[0] + 1; A[1] = B[1] + 1; A[2] = B[2] + 1; A[3] = B[3] + 1
```

---

## 2.4.7 性能分析工具

```bash
# 查看每个 Pass 的运行时间
opt -time-passes -passes='default<O2>' large_input.ll -S -o /dev/null 2>&1

# 查看每个 Pass 的变换统计
opt -stats -passes='default<O1>' input.ll -S -o /dev/null 2>&1
```

输出示例（-time-passes）：
```
---Pass execution timing report---
Total Execution Time: 0.1234 seconds (0.1234 wall clock)

  InstCombine:   0.0456 (37.0%)
  GVN:           0.0234 (19.0%)
  Inliner:       0.0189 (15.3%)
  ...
```

输出示例（-stats）：
```
15 instcombine - Number of instructions combined
 8 simplifycfg - Number of blocks simplified
 3 inline       - Number of functions inlined
 2 gvn          - Number of redundant loads removed
```

---

## 2.4.8 常用 Pass 组合场景

| 场景 | 推荐命令 |
|------|---------|
| 标准化 IR（测试前消除噪声） | `opt -passes='mem2reg,instcombine,simplifycfg' input.ll -S` |
| 完全优化（O2） | `opt -passes='default<O2>' input.ll -S` |
| 只做内联 + 清理 | `opt -passes='inline,instcombine,simplifycfg' input.ll -S` |
| 只做死代码消除 | `opt -passes='dce,bdce,adce' input.ll -S` |
| 调试循环优化 | `opt -passes='loop-rotate,licm,loop-unroll' input.ll -S` |
| 向量化 + 展开 | `opt -passes='loop-vectorize,slp-vectorize,loop-unroll' input.ll -S` |

---

## 2.4.9 练习

<div class="exercise">

### 基础练习

1. 写一个包含冗余指令（如 `x+0`、`x*1`）的 IR，用 `instcombine` 优化并观察差异。
2. 用 `-print-changed` 观察 O1 优化管线对一个循环函数的逐步变换。
3. 用 `-debug-only=loop-vectorize` 观察循环向量化 Pass 的分析输出。

### 进阶练习

4. 对一个 IR 文件分别运行 `gvn` 和 `instcombine`，比较两者消除冗余的能力和范围差异。
5. 用 `-time-passes` 对比 O1、O2、O3 管线在大型 IR 文件上的运行时间和 Pass 数量。

</div>
