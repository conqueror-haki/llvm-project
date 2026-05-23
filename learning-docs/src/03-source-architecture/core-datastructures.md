# 3.2 核心数据结构

> **学习目标**：深入理解 LLVM IR 在内存中的表示——Value、User、Use、Type 四大核心体系及其关系。
>
> **前置知识**：理解 LLVM IR 的文本格式（第 2.3 章），基本的 C++ 面向对象概念。

---

## 3.2.1 一切皆 Value

LLVM 设计中最核心的哲学：**IR 中几乎所有的东西都是 `Value`**。

```
                      Value
         ┌─────────────┼─────────────┬──────────────┐
         │             │             │              │
    Argument     BasicBlock     Constant       Instruction
                              ┌──┴──┐         ┌──┴──┐
                         ConstantInt  ...   BinaryOp  PHINode ...
```

`Value` 类提供了所有 IR 元素共享的接口：
- `getType()` — 返回值的类型
- `getName()` / `setName()` — 值的名称（如 `%x`、`@main`）
- `replaceAllUsesWith(Value *V)` — 将所有使用此值的地方替换为另一个值
- `uses()` — 遍历所有使用此值的 User
- `dump()` — 打印值的表示

---

## 3.2.2 Use-User-Value 三角关系

这是 LLVM 中最精妙但也最难理解的设计。它解决了一个根本问题：

> **给定一个 Value，如何找到所有使用它的指令？给定一条 Instruction，如何找到它的操作数？**

### Use 类

```cpp
// llvm/include/llvm/IR/Use.h
class Use {
    Value *Val;           // 指向被使用的 Value
    User *Parent;         // 指向使用者（父指令）
    Use *Prev, *Next;     // 双向链表节点（挂在 Value 的 UseList 上）

public:
    Value *get() const { return Val; }
    User *getUser() const { return Parent; }
    void set(Value *V);
};
```

每个 Use 对象同时存在于**两个**数据结构中：
1. 作为 User 操作数数组的一个元素
2. 作为被使用 Value 的 UseList 双向链表的一个节点

### User 类

```cpp
class User : public Value {
    Use *OperandList;     // 操作数数组（内联分配的）
    unsigned NumOperands;

public:
    Value *getOperand(unsigned i) const;
    void setOperand(unsigned i, Value *V);
    unsigned getNumOperands() const;
    using op_iterator = Use *;
    op_iterator op_begin() { return OperandList; }
    op_iterator op_end() { return OperandList + NumOperands; }
};
```

### 内联分配（Trailing Objects）

指令的内存布局使用 C++ 的"尾随对象"技术。一条 `add i32 %a, %b` 指令在堆上的实际内存布局是：

```
[Instruction 对象头]  ← 包含 opcode, parent block 等
[Use: %a]             ← 操作数 0
[Use: %b]             ← 操作数 1
```

Use 数组紧跟在 Instruction 对象之后，避免额外的指针间接引用和独立的内存分配。

### 使用关系的数据流动

```
想要找到所有使用 %a 的 Instruction：
  %a (Value) → uses() → UseList head → 遍历 Use 链表
    每个 Use.getUser() → 返回使用该 Value 的 User (通常是 Instruction)

想要找到指令 add 的操作数：
  add (User) → getOperand(0) → 返回 Use[0]
    Use[0].get() → 返回 %a
```

---

## 3.2.3 Type 系统

LLVM 的类型系统有两个重要特性：

### 特性 1：全局唯一（去重）

同一个类型在 `LLVMContext` 中只有一份实例：

```cpp
IntegerType *Ty1 = IntegerType::get(Context, 32);
IntegerType *Ty2 = IntegerType::get(Context, 32);
// Ty1 == Ty2 —— 指针相等！
```

这使得类型比较从 O(n) 降到 O(1)（指针比较）。

### 特性 2：丰富的子类层次

```
Type
├── IntegerType       — i1, i8, i32, ...
├── FunctionType      — void (i32, i32)*
├── StructType        — { i32, float }
├── ArrayType         — [10 x i32]
├── VectorType        — <4 x i32>
├── PointerType       — ptr
└── TargetExtType     — 目标扩展类型（GPU 纹理等）
```

判断类型的常用 C++ API：

```cpp
if (isa<IntegerType>(Ty)) { unsigned W = cast<IntegerType>(Ty)->getBitWidth(); }
if (Ty->isVoidTy()) { ... }
if (Ty->isIntegerTy()) { ... }
if (Ty->isFloatingPointTy()) { ... }
```

---

## 3.2.4 LLVMContext — IR 的"宇宙"

`LLVMContext` 拥有所有 IR 元素的去重管理。一个 Context = 一个独立的 IR 宇宙。

```cpp
LLVMContext Ctx1, Ctx2;
IntegerType *I32_1 = IntegerType::get(Ctx1, 32);
IntegerType *I32_2 = IntegerType::get(Ctx2, 32);
// I32_1 != I32_2 —— 不同宇宙，不同的对象！

// 不能混用不同 Context 的 Value！
// 如果要在 Context 间移动 Module，需要使用 IRMover
```

---

## 3.2.5 Module、Function、BasicBlock 的遍历

```cpp
// 遍历 Module 中的所有函数
for (Function &F : *TheModule) {
    errs() << F.getName() << "\n";
}

// 遍历函数中的所有基本块
for (BasicBlock &BB : F) {
    // 遍历基本块中的所有指令
    for (Instruction &I : BB) {
        I.dump();
    }
}
```

---

## 3.2.6 关键方法速查

| 方法 | 用途 |
|------|------|
| `Value::replaceAllUsesWith(V)` | 将所有引用此值的地方替换为 V |
| `Instruction::eraseFromParent()` | 从基本块中删除这条指令 |
| `Instruction::moveBefore(Pos)` | 将指令移动到 Pos 之前 |
| `Instruction::removeFromParent()` | 从基本块移除但不删除 |
| `Value::dump()` | 调试打印 |
| `Value::getType()` | 获取值的类型 |
| `User::getOperand(i)` | 获取第 i 个操作数 |
| `User::setOperand(i, V)` | 设置第 i 个操作数为 V |
| `isa<T>(V)` | 判断 V 是否为类型 T |
| `dyn_cast<T>(V)` | 安全转换，失败返回 nullptr |
| `cast<T>(V)` | 强制转换（debug 检查） |

---

## 3.2.7 练习

1. 打开 Value.h, User.h, Use.h，画一张图描述它们的内存关系
2. 写一个简单的 LLVM Pass（参考 10.2），遍历所有使用某个 Value 的指令
3. 在源码中找到 `Value::replaceAllUsesWith()` 的实现，理解其算法

