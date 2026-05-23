# 3.7 SelectionDAG

> **学习目标**：理解 SelectionDAG 指令选择框架的原理——DAG 构建、合法化、合并和表驱动模式匹配。

---

## 3.7.1 SelectionDAG 在管线中的位置

```
LLVM IR (BasicBlock)
    ↓ SelectionDAGBuilder
原始 DAG
    ↓ DAGCombiner（第一轮）
简化 DAG
    ↓ Legalize（类型 + 操作）
合法 DAG
    ↓ DAGCombiner（第二轮）
再简化 DAG
    ↓ ISel（TableGen 驱动模式匹配）
Machine DAG (SDNode → MachineSDNode)
    ↓ ScheduleDAG
MachineInstr 序列
```

---

## 3.7.2 核心概念

### SDNode — DAG 中的一个节点

```cpp
class SDNode {
    unsigned NodeType;      // ISD::ADD, ISD::LOAD, ISD::STORE, ...
    EVT ValueType;          // i32, float, <4 x i32>, ...
};
```

### 常见 ISD 节点

```cpp
ISD::ADD, ISD::SUB, ISD::MUL     // 算术
ISD::LOAD, ISD::STORE            // 内存
ISD::BR, ISD::BR_CC              // 跳转
ISD::Constant, ISD::ConstantFP   // 常量
ISD::CALL                        // 函数调用
ISD::TokenFactor                 // 合并依赖链
ISD::CopyToReg, ISD::CopyFromReg // 寄存器操作
```

### Chain 和 Glue

- **Chain（链边）**：保证内存操作的顺序
- **Glue（粘合边）**：保证两个操作必须紧密相邻（如 cmp → branch）

---

## 3.7.3 SelectionDAGBuilder

将每条 LLVM IR 指令翻译为 DAG 节点：

```cpp
void SelectionDAGBuilder::visit(Add &I) {
    SDValue LHS = getValue(I.getOperand(0));
    SDValue RHS = getValue(I.getOperand(1));
    SDValue Res = DAG.getNode(ISD::ADD, DL, I.getType(), LHS, RHS);
    setValue(&I, Res);
}
```

---

## 3.7.4 Legalize（合法化）

某些目标架构不支持特定类型或操作。例如：
- 8 位 CPU 不支持 i32 → 需要展开为 4 个 i8 操作
- RISC-V 不支持 frem → 需要展开为库调用

### LegalizeTypes

将不支持的类型分解为支持的类型：
```cpp
// 32 位平台的 i64 → 分解为两个 i32
// <8 x i32> 在不支持 256 位向量 → 分解为 <4 x i32> x2
```

### LegalizeDAG

处理不支持的操作：
- **Expand**：用等价操作序列替换
- **LibCall**：用库函数调用替换
- **Promote**：提升为更大的类型
- **Custom**：用后端自定义代码处理

每个后端在 `*ISelLowering.cpp` 中声明处理方式：

```cpp
setOperationAction(ISD::SDIV, MVT::i64, Expand);
// 64 位有符号除法在 32 位平台 → Expand
```

---

## 3.7.5 DAGCombiner

SelectionDAG 的 InstCombine 等价物：

```
(add (add X, C1), C2) → (add X, C1+C2)
(load (add Ptr, Offset)) → 如果支持，合并到寻址模式
(and X, 0) → 0
```

**运行两次**的意味：
1. 合法化之前：减少需要合法化的节点
2. 合法化之后：消除合法化引入的冗余

---

## 3.7.6 指令选择（ISel）

TableGen 将指令描述转换为匹配字节码：

```
TableGen 描述：
  def ADD32rr : ... [(set GR32:$dst, (add GR32:$src1, GR32:$src2))]

生成的字节码（简化）：
  OPC_CheckOpcode, ISD::ADD,
  OPC_CheckType, MVT::i32,
  OPC_MorphNodeTo, X86::ADD32rr
```

后端通过 `SelectCode()` 解释这个字节码，找到匹配的机器指令。

---

## 3.7.7 练习

1. 用 `-debug-only=isel` 观察 SelectionDAG 指令选择过程
2. 在 `X86InstrArithmetic.td` 中找到 ADD 指令的 pattern

