# 3.6 GVN 与 Inliner

> **学习目标**：理解 GVN（全局值编号）和 Inliner（函数内联）的算法原理。

---

## 3.6.1 GVN — Global Value Numbering

### 目的

消除冗余的 Load 和计算。如果两个值有相同的"编号"，它们一定相同。

### 核心算法

```
1. 按支配树深度优先遍历基本块
2. 对每个指令：
   a. 计算值编号（操作码 + 操作数的值编号的哈希）
   b. 在当前支配上下文中查找是否有相同编号的值
   c. 如果有，将当前指令替换为已有的值
   d. 如果没有，将新编号插入表
3. 将编号表传播到支配树子节点
```

### 场景一：冗余 Load

```llvm
%a = load i32, ptr %p
call void @func()           ; 假设不修改 %p
%b = load i32, ptr %p       ; 冗余！GVN 证明 %a == %b
```

### 场景二：冗余计算

```llvm
%x = add i32 %a, %b
; ... 不修改 %a %b 的指令
%y = add i32 %a, %b         ; 冗余！GVN 证明 %x == %y
```

### 依赖分析

GVN 依赖 `MemoryDependenceAnalysis` 判断 Load 之间是否有别名写操作。如果两个 Load 之间没有被别名分析证明有冲突的 Store/函数调用，它们可以被合并。

### 代码位置

`llvm/lib/Transforms/Scalar/GVN.cpp`

---

## 3.6.2 Inliner — 函数内联

### 收益 vs 代价

| 收益 | 代价 |
|------|------|
| 消除 call/ret 开销 | 代码膨胀（函数体被复制） |
| 暴露常量参数（内联后 常量传播 + 折叠） | 编译时间增加 |
| 过程间优化机会更多 | 指令缓存压力 |
| 间接跳变直接跳 | Debug 信息更复杂 |

### InlineCost 代价模型

```cpp
// llvm/lib/Analysis/InlineCost.cpp
class InlineCost {
    int Cost;        // 越低越好
    int Threshold;   // Cost < Threshold → 内联
};
```

代价计算考虑：
- 每条指令有基本代价（1-2 分）
- 常量参数导致大量死代码消除 → 减分（增加内联意愿）
- 函数内有调用 → 加分（减少内联意愿）
- 向量指令 → 加分

### 内联后的连锁反应

```
原始代码：
  int add(int a, int b) { return a + b; }
  int main() { return add(10, 20); }

内联后的 IR：
  main:
    %r = add i32 10, 20    ; add 内联后，参数变为常量

InstCombine 折叠：
  main:
    ret i32 30              ; 10+20 = 30
```

---

## 3.6.3 GVN 和 Inliner 的协同

Inliner 创造 GVN 的机会（内联后函数体的 Load 可以与调用者的 Load 共享），GVN 使内联后的代码更简洁（消除冗余 Load/计算）。

### 练习

1. 用 `opt -passes=gvn` 优化一个有冗余 Load 的 IR，观察效果
2. 用 `opt -passes=inline` 内联一个小函数，观察内联后 InstCombine 的附加优化

