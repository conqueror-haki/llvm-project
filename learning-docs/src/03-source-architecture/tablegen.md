# 3.10 TableGen

> **学习目标**：理解 TableGen DSL 的语法和代码生成流程，能够阅读和修改 `.td` 文件。

---

## 3.10.1 TableGen 解决了什么问题

不启用 TableGen，后端开发者需要手写数万行重复的 C++ 代码（指令编码表、匹配模式、汇编/反汇编器）。TableGen 用声明式的 `.td` 文件替代这些重复代码。

---

## 3.10.2 核心概念

### Record

每个 `def` 生成一个 Record，包含一组字段值：

```tablegen
def ADD : Instruction {
    let AsmString = "add";
    let Encoding = 0x01;
}
```

### Class

类是可参数化的模板。类本身不生成 Record：

```tablegen
class Animal<string name, int legs> {
    string Name = name;
    int Legs = legs;
}

def Dog : Animal<"dog", 4>;   // Record: {Name:"dog", Legs:4}
```

### Multiclass

一次生成多个 Record（如同一指令的不同形式）：

```tablegen
multiclass AddInst<bits<8> opc> {
    def rr : Inst<(outs GR32:$dst), (ins GR32:$s1, GR32:$s2), ...>;
    def ri : Inst<(outs GR32:$dst), (ins GR32:$s1, i32imm:$s2), ...>;
}

defm ADD : AddInst<0x01>;
// 生成: ADDrr, ADDri
```

### let 语句

临时改变字段值：

```tablegen
let isTerminator = 1, isBranch = 1 in {
    def JMP : Inst<...>;
    def RET : Inst<...>;
}
```

### 内置函数

```tablegen
!strconcat("add", " ", "{$dst}")   // 字符串拼接
!add(1, 2)                          // 3
!if(cond, a, b)                     // 条件选择
!cast<Type>(value)                  // 类型转换
!foreach(var, list, expr)           // 迭代
```

---

## 3.10.3 后端 TableGen 文件结构（以 X86 为例）

```
llvm/lib/Target/X86/
├── X86.td                    # 主入口（include 所有其他 .td）
├── X86RegisterInfo.td        # 寄存器定义
├── X86InstrInfo.td           # 指令定义（最大）
├── X86InstrArithmetic.td     # 算术指令
├── X86InstrSSE.td            # SSE 指令
├── X86Sched*.td              # 调度模型
└── X86CallingConv.td         # 调用约定
```

### 指令定义示例

```tablegen
def ADD32rr : I<0x01, MRMDestReg,
    (outs GR32:$dst),
    (ins GR32:$src1, GR32:$src2),
    "add{l}\t{$src2, $dst|$dst, $src2}",
    [(set GR32:$dst, (add GR32:$src1, GR32:$src2))]>;
```

字段解释：
- `0x01`：指令操作码
- `MRMDestReg`：ModRM 字节的编码方式
- `(outs ...)` / `(ins ...)`：输出/输入操作数
- `"add{l}\t..."`：汇编格式串（AT&T / Intel 两种格式）
- `[(set ...)]`：SDAG 匹配模式

### 寄存器定义示例

```tablegen
def EAX : X86Reg<"EAX", 0>;     # 名称 = "EAX", 编码 = 0
def EBX : X86Reg<"EBX", 3>;

def GR32 : RegisterClass<"X86", [i32], 32,
    (add EAX, ECX, EDX, EBX, ESI, EDI, R8D, ...)>;
```

---

## 3.10.4 llvm-tblgen — 从 .td 到 C++

```bash
llvm-tblgen X86.td -gen-emitter         # → X86GenMCCodeEmitter.inc
llvm-tblgen X86.td -gen-register-info    # → X86GenRegisterInfo.inc
llvm-tblgen X86.td -gen-instr-info       # → X86GenInstrInfo.inc
llvm-tblgen X86.td -gen-dag-isel         # → X86GenDAGISel.inc (匹配表字节码)
llvm-tblgen X86.td -gen-asm-writer       # → X86GenAsmWriter.inc
llvm-tblgen X86.td -gen-disassembler     # → X86GenDisassemblerTables.inc
llvm-tblgen X86.td -gen-subtarget        # → X86GenSubtargetInfo.inc
```

这些 `.inc` 文件在构建时自动生成，被对应的 C++ 文件包含。

---

## 3.10.5 练习

1. 在 `X86RegisterInfo.td` 中找到 X86-64 通用寄存器的定义
2. 在 `X86InstrArithmetic.td` 中找到 `ADD32rr` 的完整定义
3. 尝试修改一条指令的汇编格式字符串，重建后验证 `llvm-mc` 的输出变化

