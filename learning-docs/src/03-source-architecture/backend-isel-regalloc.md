# 3.8 指令选择与寄存器分配

> **学习目标**：理解指令选择的三种方式（SelectionDAG、FastISel、GlobalISel）和寄存器分配的算法（线性扫描、Greedy）。

---

## 3.8.1 三种指令选择策略

| 策略 | 速度 | 质量 | 使用场景 |
|------|------|------|---------|
| SelectionDAG ISel | 慢 | 最佳 | O1+ |
| FastISel | 快 | 差 | O0 |
| GlobalISel | 中 | 接近SDAG | 未来（AArch64 成熟） |

---

## 3.8.2 FastISel — 快速指令选择

O0 编译时，LLVM 跳过 SelectionDAG，直接在基本块内做简单的一对一翻译：

```cpp
// X86FastISel.cpp
bool X86FastISel::fastLowerInstruction(Instruction *I) {
    switch (I->getOpcode()) {
    case Instruction::Add: return fastLowerAdd(I);
    case Instruction::Load: return fastLowerLoad(I);
    // ...
    }
}
```

如果某个指令不能被 FastISel 处理，整个基本块"fallback"到 SelectionDAG。典型 fallback 原因：跨越基本块的指令（PHI 节点）、复杂调用。

---

## 3.8.3 GlobalISel — 未来的指令选择

GlobalISel 是 LLVM 的第三代指令选择框架。与 SelectionDAG 的核心差异：

- **不使用 DAG**：直接在 MachineInstr 上操作（MIR ↔ MIR）
- **统一框架**：所有后端共享相同核心逻辑
- **更适合 JIT**：延迟更低的前期处理

目前 AArch64 上最成熟。其他架构仍在迁移中。

---

## 3.8.4 寄存器分配

### 问题

```
输入：vreg0 = ADD32 vreg1, vreg2      # 虚拟寄存器有几百个
                                     # 物理寄存器只有 16 个 (X86-64)
输出：EAX = ADD32 EBX, ECX
```

### 两种分配器

| 分配器 | 算法 | 质量 |
|--------|------|------|
| Greedy（默认） | 改进的线性扫描 | O2/O3 用 |
| Fast | 简单线性扫描 | O0 用 |

### LiveInterval（活跃区间）

```cpp
class LiveInterval {
    unsigned Reg;                    // 寄存器
    SmallVector<LiveRange, 4> Ranges; // 活跃范围
    float Weight;                    // 权重（热路径高）
};
```

### 分配步骤

```
1. 计算 LiveInterval（从 def 到 last use 的 SlotIndex 范围）
2. 构建干涉图（重叠的 LiveInterval 不能共享同一物理寄存器）
3. 贪心分配（按权重排序，为每个虚拟寄存器分配物理寄存器）
4. 溢出（没有可用寄存器时，将值写入栈）
5. 合并 COPY 指令（消除因 PHI 消除产生的冗余 COPY）
```

---

## 3.8.5 练习

1. 用 `-debug-only=regalloc` 观察寄存器分配过程
2. 写一个使用 10+ 个变量的函数，查看哪些被 spill 到栈

