# 2.3 LLVM IR 深入

> **学习目标**：掌握 LLVM IR 的类型系统、指令集、SSA 形式和控制流结构，能够阅读和手动编写 LLVM IR。
>
> **前置知识**：完成第一次编译章节，了解基本的 CPU 指令概念。

---

## 本章导读

LLVM IR 是整个 LLVM 生态系统的**通用语言**。无论你的源代码是 C、C++、Rust、Swift 还是 Julia，最终都会变成 LLVM IR。所有优化、分析、代码生成都围绕 IR 展开。

理解 IR 的好处：
1. **调试编译问题**：当生成的代码不对时，看 IR 比看汇编容易 10 倍
2. **理解优化行为**：为什么某个优化没有触发？看 IR 是最好的答案
3. **写测试**：LLVM 的回归测试大量使用手写的 IR
4. **设计自己的语言**：如果你想写一个新语言的前端，只需要生成 LLVM IR，后面的事情 LLVM 全包了

本章将系统介绍 IR 的每个方面，从类型系统到指令集到控制流。这不是一次性读完的章节——你可以把它当作参考手册，需要时回来查阅。

---

## 2.3.1 IR 的模块层次结构

LLVM IR 组织为严格的树状层次：

```
Module                                           # 一个编译单元
│
├── Target Information (DataLayout, Triple)      # 目标平台描述
│
├── Global Variables                             # 全局变量
│   ├── @counter = global i32 0                  # 可写全局
│   └── @greeting = constant [13 x i8] c"...\00" # 只读常量
│
├── Functions                                    # 函数
│   └── Function
│       ├── Argument 0 (i32 %a)                  # 函数参数
│       ├── Argument 1 (i32 %b)
│       ├── AttributeList                        # 属性
│       └── BasicBlock List
│           ├── BasicBlock "entry"
│           │   ├── Instruction (alloca)
│           │   ├── Instruction (store)
│           │   ├── Instruction (load)
│           │   └── Instruction (br)             # 终结指令
│           ├── BasicBlock "loop"
│           │   └── ...
│           └── BasicBlock "exit"
│               └── Instruction (ret)
│
├── Aliases                                      # 符号别名
│   └── @alias = alias i32, ptr @original
│
└── Metadata                                     # 元数据
    ├── !dbg (debug info)
    ├── !tbaa (type-based alias analysis)
    └── !llvm.loop (loop hints)
```

对应的 C++ 类层次：

| IR 元素 | C++ 类 | 头文件 |
|---------|--------|--------|
| Module | `llvm::Module` | `llvm/IR/Module.h` |
| Function | `llvm::Function` | `llvm/IR/Function.h` |
| BasicBlock | `llvm::BasicBlock` | `llvm/IR/BasicBlock.h` |
| Instruction | `llvm::Instruction` | `llvm/IR/Instruction.h` |
| Value | `llvm::Value` | `llvm/IR/Value.h` |
| Type | `llvm::Type` | `llvm/IR/Type.h` |

---

## 2.3.2 类型系统

LLVM IR 是**强类型的**。每个 Value 都有明确的 Type。

### 基本类型

```llvm
; void — 空类型（函数不返回值）
void

; 整数类型（iN，N = 1 到 2^23-1）
i1          ; 1 位（布尔值）
i8          ; 8 位（char、byte）
i16         ; 16 位（short）
i32         ; 32 位（int）
i64         ; 64 位（long long）
i128        ; 128 位（__int128）

; 浮点类型
half        ; 16 位浮点（IEEE 754 binary16）
bfloat      ; 16 位脑浮点（brain floating point）
float       ; 32 位浮点（IEEE 754 single）
double      ; 64 位浮点（IEEE 754 double）
fp128       ; 128 位浮点（IEEE 754 quad）
x86_fp80    ; 80 位浮点（x86 扩展精度）
ppc_fp128   ; 128 位浮点（PowerPC 双精度对）
```

LLVM 的整数类型没有"有符号/无符号"之分——`i32` 就是 32 个位。有符号/无符号的语义由**指令**决定（如 `sdiv` vs `udiv`，`sgt` vs `ugt`）。

### 复合类型

```llvm
; 数组 — 元素数量是编译期常量
[10 x i32]              ; 10 个 i32 的数组
[4 x [3 x float]]       ; 嵌套数组：4 个 3-float 数组

; 向量 (SIMD)
<4 x i32>               ; 4 个 i32 的向量（128 位 SSE 向量）
<8 x half>              ; 8 个 half（128 位）
<2 x double>            ; 2 个 double（128 位）

; 结构体
{ i32, float, i8 }      ; 匿名结构体
%Point = type { i32, i32 }  ; 命名结构体（x, y 坐标）
{ i32, { float, i8 } }  ; 嵌套结构体
<{ i32 }>               ; 紧凑结构体（packed struct，无填充）
```

### 指针——不透明指针（LLVM 15+）

**重要变更**：从 LLVM 15 开始，类型化指针（`i32*`、`float**`）已被弃用。所有指针统一为 `ptr`。

```llvm
; 旧语法（已弃用，不应在新代码中使用）：
; i32*         指向 i32 的指针
; i32**        指向"指向 i32 的指针"的指针

; 新语法（LLVM 15+）：
ptr                          ; 不透明指针
ptr addrspace(5)              ; 地址空间 5 的指针（GPU 局部内存等）
```

不透明指针意味着 `load` 和 `store` 指令需要显式指定操作的类型：

```llvm
; 旧：  %v = load i32* %p         （类型从指针类型推导）
; 新：  %v = load i32, ptr %p     （需要显式指定）

; 旧：  %p2 = getelementptr i32, i32* %arr, i64 5
; 新：  %p2 = getelementptr i32, ptr %arr, i64 5
```

### 函数类型

```llvm
; 接受两个 i32，返回 i32
i32 (i32, i32)

; 接受一个 ptr，返回 void
void (ptr)

; 变参函数（类似 printf）
i32 (ptr, ...)

; 元组形式（某些后端使用）
[i32, i1] (i32)     ; 返回 {i32, i1}（如带 carry 的加法）
```

### 类型是全局唯一的

每个类型在 `LLVMContext` 中只有一份。这意味着类型比较可以用指针相等（O(1)）：

```cpp
IntegerType *I32Ty1 = IntegerType::get(Context, 32);
IntegerType *I32Ty2 = IntegerType::get(Context, 32);
assert(I32Ty1 == I32Ty2);  // 同一个对象！
```

---

## 2.3.3 SSA 形式与 PHI 节点

### 静态单赋值（SSA）

SSA 的核心规则：**每个虚拟寄存器只能被赋值一次**。

```c
// C 代码（非 SSA）：
int x = 0;
if (cond) {
    x = 10;  // 第二次赋值！非 SSA
} else {
    x = 20;  // 第三次赋值！
}
printf("%d\n", x);
```

翻译为 SSA 形式的 LLVM IR，使用 PHI 节点：

```llvm
entry:
  br i1 %cond, label %then, label %else

then:
  br label %merge

else:
  br label %merge

merge:
  %x = phi i32 [ 10, %then ], [ 20, %else ]
  call void @print_int(i32 %x)
```

**PHI 节点的语义**：`%x = phi i32 [10, %then], [20, %else]` 表示：
- 如果从基本块 `%then` 进入 `%merge`，则 `%x = 10`
- 如果从基本块 `%else` 进入 `%merge`，则 `%x = 20`

### 循环中的 PHI 节点

```c
int result = 0;
for (int i = 0; i < 10; i++) {
    result += i;
}
```

```llvm
entry:
  br label %loop

loop:
  %i = phi i32 [ 0, %entry ], [ %next_i, %loop_body ]   ; i 的 PHI
  %result = phi i32 [ 0, %entry ], [ %new_result, %loop_body ]  ; result 的 PHI
  %cmp = icmp slt i32 %i, 10
  br i1 %cmp, label %loop_body, label %exit

loop_body:
  %new_result = add i32 %result, %i
  %next_i = add i32 %i, 1
  br label %loop
```

PHI 节点构成了 SSAS 形式的核心。但**你通常不需要手写它们**——Clang CodeGen 使用 `alloca + mem2reg` 的模式（先 alloca 所有局部变量，然后自动提升为 SSA 的 PHI 形式）。

---

## 2.3.4 指令全集（分类详解）

### 终结指令 (Terminator Instructions)

终结指令是每个基本块的**最后一条指令**。它的作用是跳转到下一个基本块或返回。

| 指令 | 语法 | 说明 |
|------|------|------|
| `ret` | `ret void` / `ret i32 %val` | 从函数返回 |
| `br` | `br label %dest` / `br i1 %cond, label %t, label %f` | 跳转/条件跳转 |
| `switch` | `switch i32 %val, label %default [i32 0, label %case0 ...]` | 多路分支 |
| `indirectbr` | `indirectbr ptr %addr, [label %d1, label %d2]` | 间接跳转（GCC 的 goto *addr） |
| `invoke` | `invoke ... to label %normal unwind label %exception` | 带异常处理的函数调用 |
| `callbr` | `callbr ... to label %fallthrough [label %indirect]` | GNU C 内联汇编的 goto 形式 |
| `resume` | `resume {i8*, i32} %exn` | 恢复异常传播 |
| `catchswitch` | 复杂 | 异常处理的子结构 |
| `catchret` / `cleanupret` | 复杂 | 异常的清理 |
| `unreachable` | `unreachable` | 告诉优化器：这个点不可达 |

> 💡 **`unreachable` 是强大的优化提示**。如果优化器能证明某条路径必然到达 `unreachable`，它可以消除该路径的所有前置代码。因此，插入 `unreachable` 常常是 Pass 优化效果的关键。

### 二元运算指令

LLVM 将算术指令分为整数和浮点两类。

**整数运算**：

```llvm
%r = add  i32 %a, %b    ; 加法
%r = sub  i32 %a, %b    ; 减法
%r = mul  i32 %a, %b    ; 乘法
%r = sdiv i32 %a, %b    ; 有符号除法（向零舍入）
%r = udiv i32 %a, %b    ; 无符号除法
%r = srem i32 %a, %b    ; 有符号取余
%r = urem i32 %a, %b    ; 无符号取余
```

**浮点运算**：

```llvm
%r = fadd float %a, %b   ; 浮点加
%r = fsub float %a, %b   ; 浮点减
%r = fmul float %a, %b   ; 浮点乘
%r = fdiv float %a, %b   ; 浮点除
%r = frem float %a, %b   ; 浮点取余
%r = fneg float %a       ; 浮点取反
```

**位运算**：

```llvm
%r = shl  i32 %a, 3     ; 左移
%r = lshr i32 %a, 3     ; 逻辑右移（填 0）
%r = ashr i32 %a, 3     ; 算术右移（填符号位）
%r = and  i32 %a, %b    ; 按位与
%r = or   i32 %a, %b    ; 按位或
%r = xor  i32 %a, %b    ; 按位异或
```

**整数运算的 nsw/nuw 标记**：

```llvm
%r = add nsw i32 %a, %b      ; No Signed Wrap —— 保证不会有符号溢出
%r = add nuw i32 %a, %b      ; No Unsigned Wrap —— 保证不会无符号溢出
%r = add nsw nuw i32 %a, %b  ; 两者皆保证
```

这些标记来自 C 语言的"有符号整数溢出是 UB"语义。优化器利用它们做更多变换。例如：
```llvm
; 已知 %x = add nsw i32 %a, 1
; 那么 %x > %a 一定为真（如果是 nsw，说明没有溢出，结果大于原值）
```

### 内存操作指令

```llvm
; 栈分配
%ptr = alloca i32                       ; 在栈上分配一个 i32

; 读写
%val = load i32, ptr %ptr               ; 从指针读
store i32 %val, ptr %ptr                ; 写入指针

; GEP（GetElementPtr）— 计算地址偏移
%elem = getelementptr i32, ptr %arr, i64 3     ; arr[3] 的地址
%field = getelementptr {i32, float}, ptr %s, i64 0, i32 1  ; s.f 的地址（字段 float）
```

**GEP 详解**：GEP 只计算地址，不访问内存。它类似于 C 的 `&arr[3]`。

```
对于一个结构体 { i32, float, i8 }，内存布局可能是：
+0:  i32 (4 bytes)
+4:  float (4 bytes, 可能需要 padding)
+8:  i8 (1 byte, 可能填充到 4 bytes)

getelementptr {i32,float,i8}, ptr %s, i64 0, i32 1
= 基址 %s + offsetof(字段 1) = %s + 4
```

### 类型转换指令

```llvm
; 整数扩展/截断
%r = zext i8 %x to i32        ; 零扩展（用于无符号数）
%r = sext i8 %x to i32        ; 符号扩展（用于有符号数）
%r = trunc i32 %x to i8       ; 截断

; 整数 ↔ 浮点
%r = sitofp i32 %x to float   ; 有符号整数 → 浮点
%r = uitofp i32 %x to float   ; 无符号整数 → 浮点
%r = fptosi float %x to i32   ; 浮点 → 有符号整数
%r = fptoui float %x to i32   ; 浮点 → 无符号整数

; 浮点精度转换
%r = fpext half %x to float   ; 低精度 → 高精度
%r = fptrunc double %x to float ; 高精度 → 低精度

; 指针 ↔ 整数
%r = ptrtoint ptr %p to i64   ; 指针 → 整数
%p2 = inttoptr i64 %r to ptr  ; 整数 → 指针

; 位重解释（bitcast）
%r = bitcast float %x to i32  ; 保持相同的位模式，改变类型
%r = bitcast ptr %p2 to ptr   ; 指针 to 指针（改变地址空间等）
```

### 比较指令

```llvm
; 整数比较
%cmp = icmp eq  i32 %a, %b    ; 等于
%cmp = icmp ne  i32 %a, %b    ; 不等于
%cmp = icmp sgt i32 %a, %b    ; 有符号大于
%cmp = icmp sge i32 %a, %b    ; 有符号大于等于
%cmp = icmp slt i32 %a, %b    ; 有符号小于
%cmp = icmp sle i32 %a, %b    ; 有符号小于等于
%cmp = icmp ugt i32 %a, %b    ; 无符号大于
%cmp = icmp uge i32 %a, %b    ; 无符号大于等于
%cmp = icmp ult i32 %a, %b    ; 无符号小于
%cmp = icmp ule i32 %a, %b    ; 无符号小于等于

; 浮点比较（ordered/unordered 区分 NaN 语义）
%cmp = fcmp oeq float %a, %b  ; ordered and equal
%cmp = fcmp ogt float %a, %b  ; ordered and greater than
%cmp = fcmp ole float %a, %b  ; ordered and less or equal
%cmp = fcmp ueq float %a, %b  ; unordered or equal
%cmp = fcmp une float %a, %b  ; unordered or not equal
; ... 更多组合
```

"ordered" 表示**操作数没有 NaN**。如果任一操作数是 NaN，ordered 比较返回 false。unordered 比较在操作数包含 NaN 时返回 true。

### 其他指令

```llvm
; 函数调用
%result = call i32 @foo(i32 42, i32 10)
call void @bar()

; 间接调用（函数指针）
%result = call i32 %func_ptr(i32 %x)

; Select（C 的 ?: 三元运算符）
%val = select i1 %cond, i32 %a, i32 %b

; 向量操作
%el = extractelement <4 x i32> %vec, i32 2        ; 提取第 2 个元素
%new = insertelement <4 x i32> %vec, i32 %v, i32 0 ; 插入
%shuf = shufflevector <4 x i32> %a, <4 x i32> %b,
        <4 x i32> <i32 0, i32 4, i32 1, i32 5>     ; 重组

; 原子操作
%old = atomicrmw add ptr %ptr, i32 1 seq_cst
```

---

## 2.3.5 控制流结构的 IR 表示

### if/else

```c
if (x > 0) {
    result = x;
} else {
    result = -x;
}
```

```llvm
entry:
  %cmp = icmp sgt i32 %x, 0
  br i1 %cmp, label %positive, label %negative

positive:
  br label %merge

negative:
  %neg = sub i32 0, %x
  br label %merge

merge:
  %result = phi i32 [ %x, %positive ], [ %neg, %negative ]
  ret i32 %result
```

简化版（如果用 `select` 指令）：

```llvm
  %cmp = icmp sgt i32 %x, 0
  %neg = sub i32 0, %x
  %result = select i1 %cmp, i32 %x, i32 %neg
  ret i32 %result
```

### for 循环

```c
for (int i = 0; i < n; i++) {
    sum += i;
}
```

```llvm
entry:
  br label %loop

loop:
  %i = phi i32 [ 0, %entry ], [ %next_i, %loop_body ]
  %sum = phi i32 [ 0, %entry ], [ %new_sum, %loop_body ]
  %cmp = icmp slt i32 %i, %n
  br i1 %cmp, label %loop_body, label %exit

loop_body:
  %new_sum = add i32 %sum, %i
  %next_i = add nsw i32 %i, 1
  br label %loop

exit:
  ret i32 %sum
```

每个循环包含三个关键部分：
- **Preheader**：循环之前的唯一前驱块（`entry` 在这里就是 preheader）
- **Header**：循环入口块（`loop`）
- **Latch**：回到 header 的块（`loop_body` 最后 jump 到 `loop`）

### while 循环

```c
while (x > 0) {
    sum += x;
    x--;
}
```

```llvm
entry:
  br label %while_cond

while_cond:
  %x = phi i32 [ %init_x, %entry ], [ %new_x, %while_body ]
  %sum = phi i32 [ 0, %entry ], [ %new_sum, %while_body ]
  %cmp = icmp sgt i32 %x, 0
  br i1 %cmp, label %while_body, label %exit

while_body:
  %new_sum = add i32 %sum, %x
  %new_x = sub i32 %x, 1
  br label %while_cond

exit:
  ret i32 %sum
```

---

## 2.3.6 全局变量和常量

```llvm
; 可写全局变量（初始值为 0）
@counter = global i32 0

; 只读常量
@greeting = constant [13 x i8] c"Hello World!\00"

; 外部全局（在其他编译单元定义）
@external_var = external global i32

; 线程局部变量
@tls_counter = thread_local global i32 0

; 带对齐的全局
@aligned_var = global i32 0, align 16
```

---

## 2.3.7 函数声明与调用

```llvm
; 声明（外部函数的 Declare）
declare i32 @printf(ptr noundef, ...)
declare void @exit(i32 noundef)

; 定义（我们的函数）
define i32 @add(i32 %a, i32 %b) {
entry:
  %sum = add nsw i32 %a, %b
  ret i32 %sum
}

; 带属性的函数
define void @noexcept_func() nounwind { ... }
define i32 @hot_func() hot { ... }
define i32 @cold_func() cold noinline { ... }

; 内置函数
declare float @llvm.sqrt.f32(float)
```

常用函数属性：

| 属性 | 含义 |
|------|------|
| `nounwind` | 不会抛出异常 |
| `readonly` | 只读内存，不写 |
| `readnone` | 完全不访问内存 |
| `noinline` | 禁止内联 |
| `alwaysinline` | 强制内联 |
| `noreturn` | 不会返回（如 `exit()`） |
| `hot` / `cold` | 热/冷函数标记 |

---

## 2.3.8 通过实例学习 IR

### C → IR 完整对照

```c
int factorial(int n) {
    if (n <= 1)
        return 1;
    return n * factorial(n - 1);
}
```

O0 IR（直译 + alloca）：
```llvm
define i32 @factorial(i32 %n) {
entry:
  %n.addr = alloca i32
  store i32 %n, ptr %n.addr
  %0 = load i32, ptr %n.addr
  %cmp = icmp sle i32 %0, 1
  br i1 %cmp, label %if.then, label %if.else

if.then:
  ret i32 1

if.else:
  %1 = load i32, ptr %n.addr
  %sub = sub nsw i32 %1, 1
  %call = call i32 @factorial(i32 %sub)
  %2 = load i32, ptr %n.addr
  %mul = mul nsw i32 %2, %call
  ret i32 %mul
}
```

O2 IR（mem2reg + 尾调用消除）：
```llvm
define i32 @factorial(i32 %n) {
entry:
  %cmp = icmp slt i32 %n, 2
  br i1 %cmp, label %return, label %tailrecurse

tailrecurse:
  %sub = add nsw i32 %n, -1
  %call = tail call i32 @factorial(i32 %sub)
  %mul = mul nsw i32 %n, %call
  ret i32 %mul

return:
  ret i32 1
}
```

注意 LLVM 将 `n <= 1` 优化为 `n < 2`（因为整数）并且将 `n - 1` 优化为 `n + (-1)`。

O2 IR（进一步优化，展开了尾调用）：
```llvm
define i32 @factorial(i32 %n) {
entry:
  %cmp5 = icmp slt i32 %n, 2
  br i1 %cmp5, label %for.end, label %for.body.preheader

for.body.preheader:
  br label %for.body

for.body:
  %result.07 = phi i32 [ %mul, %for.body ], [ 1, %for.body.preheader ]
  %i.06 = phi i32 [ %inc, %for.body ], [ %n, %for.body.preheader ]
  %mul = mul nsw i32 %result.07, %i.06
  %inc = add nsw i32 %i.06, -1
  %cmp = icmp sgt i32 %i.06, 2
  br i1 %cmp, label %for.body, label %for.end

for.end:
  %result.0.lcssa = phi i32 [ 1, %entry ], [ %mul, %for.body ]
  ret i32 %result.0.lcssa
}
```

观察 LLVM 如何将递归调用**转换**为迭代循环——这是一种优化技巧，递归变成循环后可以用循环 Pass 进一步优化。

---

## 2.3.9 关键洞察

1. **SSA 赋予优化器超能力**：因为每个值只有一个定义点，优化器可以安全地替换、移动、消除指令。
2. **PHI 节点是 SSA 的精髓**：它们使得条件分支后的值可以表示为"一个"值。
3. **GEP 只是地址计算**：它不访问内存，这使得别名分析可以精确判断两个指针是否可能重叠。
4. **IR 信息冗余但可被消除**：O0 IR 中的 alloca/store/load 是冗余的，但其忠实性简化了 CodeGen。

---

## 2.3.10 练习

<div class="exercise">

### 基础练习

1. 手写一个 `abs` 函数的 LLVM IR（包含条件分支和 PHI 节点），用 `lli` 运行验证。
2. 写一个 for 循环的 C 代码，然后手动翻译为 LLVM IR。
3. 用 `clang -S -emit-llvm -O0` 和 `-O2` 分别生成同一个函数的 IR，逐行对比差异。

### 进阶练习

4. 手写一个带有 `select` 指令的函数，然后用 `opt -passes=simplifycfg` 观察是否被转换为 if/else。
5. 理解 GEP：写一个包含结构体数组遍历的 C 代码，查看 IR 中的 GEP 索引。
6. 编写一个使用 `volatile` 变量的 C 函数，对比 IR 中 volatile 如何影响 `load`/`store` 的优化。

### 挑战练习

7. 手写一个包含嵌套循环的完整 IR 函数，用 `opt -passes='loop-rotate,licm,loop-unroll'` 逐步优化，观察每个 Pass 的贡献。

</div>
