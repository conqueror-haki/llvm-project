# 4.3 添加一条新指令

> **学习目标**：理解从 TableGen 定义到 ISel 匹配的完整指令添加流程。

---

## 4.3.1 流程概览

```
1. 在 .td 文件中定义指令
2. (可选) 定义自定义 SDNode
3. 在 ISelLowering 中处理 lowering
4. 在 ISelDAGToDAG 中添加手动匹配
5. 构建并测试
```

---

## 4.3.2 Step 1：TableGen 定义

在 `llvm/lib/Target/X86/X86InstrArithmetic.td` 中添加：

```tablegen
def MYADD32rr : I<0xA0, MRMDestReg,
    (outs GR32:$dst),
    (ins GR32:$src1, GR32:$src2),
    "myadd{l}\t{$src2, $dst|$dst, $src2}",
    []>;  // 空 pattern — 暂不自动匹配
```

字段解释：
- `0xA0`：操作码
- `MRMDestReg`：ModRM 字节编码方式
- `(outs ...)` / `(ins ...)`：操作数
- 汇编格式中的 `{l}` 表示 32 位后缀

---

## 4.3.3 Step 2：验证汇编/反汇编

```bash
ninja -C build llc llvm-mc

# 测试汇编
echo "myaddl %eax, %ebx" | ./build/bin/llvm-mc -triple=x86_64 \
    --show-encoding

# 测试反汇编
echo "0x0f 0xa0 0xc3" | ./build/bin/llvm-mc -triple=x86_64 --disassemble
```

---

## 4.3.4 Step 3：添加 SDAG Pattern

让 LLVM 自动匹配 IR 并生成你的指令：

```tablegen
// 定义自定义 SDNode
def X86myadd : SDNode<"X86ISD::MYADD", SDTIntBinOp>;

// 更新指令定义，添加 pattern
def MYADD32rr : I<0xA0, MRMDestReg,
    (outs GR32:$dst),
    (ins GR32:$src1, GR32:$src2),
    "myadd{l}\t{$src2, $dst|$dst, $src2}",
    [(set GR32:$dst, (X86myadd GR32:$src1, GR32:$src2))]>;
```

在 `X86ISelLowering.h` 中定义 SDNode：

```cpp
namespace X86ISD {
    enum NodeType {
        MYADD,  // 自定义节点
    };
}
```

---

## 4.3.5 Step 4：ISelLowering 实现

在 `X86ISelLowering.cpp` 中实现对 IR 操作的 lowering：

```cpp
SDValue X86TargetLowering::LowerADD(SDValue Op, SelectionDAG &DAG) const {
    // emit X86ISD::MYADD node for IR's add instruction
    return DAG.getNode(X86ISD::MYADD, SDLoc(Op), Op.getValueType(),
                       Op.getOperand(0), Op.getOperand(1));
}
```

---

## 4.3.6 完整流程总结

```
1. 定义指令 (X86InstrArithmetic.td)
2. 定义 SDNode (X86ISelLowering.h)
3. 添加 SDAG Pattern (X86InstrArithmetic.td)
4. 实现 Lowering (X86ISelLowering.cpp)
5. 构建 + 汇编/反汇编验证
6. 编写 lit 测试 (llvm/test/CodeGen/X86/)
```

---

## 4.3.7 练习

1. 在 X86 后端添加一条"虚拟"指令 `NOP2`，编码为 `0x0F 0x1F 0x00`
2. 验证 `llvm-mc` 能正确汇编和反汇编你的指令
3. 添加一个自定义 SDNode 并编写 pattern

