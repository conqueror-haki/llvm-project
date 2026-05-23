# 3.5 InstCombine 走读

> **学习目标**：理解 InstCombine 的算法原理、模式匹配框架和代码组织方式。
>
> **前置知识**：理解 LLVM IR 指令集（第 2.3 章），了解 Pass 基本结构（第 3.3 章）。

---

## 3.5.1 InstCombine 的设计哲学

InstCombine 做的是**局部窥孔优化**——它不依赖全局分析，只检查每条指令及其直接操作数，寻找可简化的模式。它的威力来自三个因素：

1. **上千种已知模式**：覆盖了绝大多数常见的冗余情况
2. **迭代执行**：一个模式的简化可能暴露下一个可简化的模式
3. **极低的每指令代价**：每个模式检查只需几次指针比较

---

## 3.5.2 代码组织结构

```
llvm/lib/Transforms/InstCombine/
├── InstructionCombining.cpp  (主入口 + 迭代控制)
├── InstCombineInternal.h     (InstCombiner 类定义)
│
├── InstCombineAddSub.cpp     (add/sub 的模式)
├── InstCombineMulDivRem.cpp  (mul/div/rem)
├── InstCombineShifts.cpp     (shl/lshr/ashr)
├── InstCombineAndOrXor.cpp   (and/or/xor)
├── InstCombineCasts.cpp      (zext/sext/trunc/bitcast)
├── InstCombineCompares.cpp   (icmp/fcmp)
├── InstCombineSelect.cpp     (select)
├── InstCombinePHI.cpp        (PHI 节点)
├── InstCombineCalls.cpp      (内置函数调用)
├── InstCombineLoadStoreAlloca.cpp (内存操作)
└── InstCombineVectorOps.cpp  (向量操作)
```

---

## 3.5.3 主循环

```cpp
// 简化版主循环
bool InstCombinerImpl::run() {
    bool Changed = false;
    
    for (BasicBlock &BB : *Func) {
        // 使用 Worklist 方式遍历（不是简单的 for-each）
        while (!Worklist.isEmpty()) {
            Instruction *I = Worklist.removeOne();
            
            if (I == nullptr || I->use_empty() && isTriviallyDead(I))
                continue;
            
            // 尝试合并这条指令
            if (Instruction *Result = visit(*I)) {
                // Result 替换了 I（I 被移除）
                ReplaceInstWithValue(I, Result);
                Changed = true;
            }
        }
    }
    return Changed;
}
```

Worklist 的使用是关键——当 Pass 简化一条指令时，被简化的指令的使用者（users）可能也有优化机会，被加入 Worklist 重新处理。

---

## 3.5.4 模式匹配示例

### 代数恒等式

```cpp
// InstCombineAddSub.cpp
Instruction *InstCombinerImpl::visitAdd(BinaryOperator &I) {
    Value *Op0 = I.getOperand(0), *Op1 = I.getOperand(1);
    
    // X + 0 → X
    if (match(Op1, m_Zero()))
        return replaceInstUsesWith(I, Op0);
    
    // X + X → X << 1
    if (Op0 == Op1)
        return BinaryOperator::CreateShl(Op0, ConstantInt::get(I.getType(), 1));
    
    // (X + C1) + C2 → X + (C1 + C2)
    // 嵌套匹配...
}
```

### PatternMatch 库

LLVM 提供了一个简洁的模式匹配 DSL：

```cpp
using namespace llvm::PatternMatch;

Value *X, *Y;
ConstantInt *C;

// 匹配 X + C
if (match(I.getOperand(0), m_Add(m_Value(X), m_ConstantInt(C)))) { ... }

// 匹配 X * 2
if (match(I, m_Mul(m_Value(X), m_SpecificInt(2)))) { ... }

// 匹配 xor X, -1 (即 NOT X)
if (match(I, m_Not(m_Value(X)))) { ... }
```

常见模式：
- `m_Zero()`, `m_One()`, `m_AllOnes()` — 特定常量
- `m_Add(L, R)`, `m_Sub(L, R)` — 二元运算
- `m_Shl(V, C)`, `m_LShr(V, C)` — 移位
- `m_ICmp(P, L, R)` — 整数比较
- `m_Select(C, T, F)` — select 指令
- `m_Not(V)` — xor V, -1（按位取反）

---

## 3.5.5 关键变换举例

| 模式 | 结果 |
|------|------|
| X + 0 | X |
| X - 0 | X |
| X * 1 | X |
| X & 0 | 0 |
| X & X | X |
| X \| X | X |
| X xor X | 0 |
| X xor -1 | ~X |
| (X << C) >> C (逻辑右移) | X & ((1<<(BW-C))-1) |
| (X << C1) >> C2 | 折叠为简单移位（条件允许时） |
| icmp eq X, 0 → icmp eq (and X, ...), 0 | 从比较中提取位测试 |

---

## 3.5.6 为什么 InstCombine 运行多次？

在 O2 管线中，InstCombine 运行 5-6 次，分布在管线的不同阶段：

```
循环 1: 在 mem2reg 之后 → 清理栈变量提升产生的冗余
循环 2: 在 SimplifyCFG 之后 → 控制流简化暴露出新的算术模式
循环 3: 在 Inliner 之前 → 为内联决策提供更准确的代价信息
循环 4: 在 Inliner 之后 → 内联暴露常量参数
循环 5: 在向量化之后 → 向量化引入的 extract/insert 模式
循环 6: 最终清理 → 优化管线最后残余
```

---

## 3.5.7 练习

1. 阅读 `InstCombineAddSub.cpp` 中的前 5 个变换规则
2. 尝试为 InstCombine 添加一个新的模式，并用 lit 测试验证
3. 用 `-debug-only=instcombine` 观察 InstCombine 如何逐步简化 IR

