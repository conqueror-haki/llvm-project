# 4.5 调试技巧

> **学习目标**：掌握 LLVM 开发中的调试工具链——dump、debug-only、print-changed、ASan、bugpoint 等。

---

## 4.5.1 dump() — 万能调试法

LLVM 的几乎所有核心类都实现了 `dump()`：

```cpp
F.dump();              // 打印整个函数
BB.dump();             // 打印基本块
I.dump();              // 打印单条指令
V->dump();             // 打印值及其类型
Ty->dump();            // 打印类型
```

在任何 LLVM 源码位置插入 `errs() << "DEBUG: " << *V << "\n";` 就能看到值的内容。

---

## 4.5.2 debug-only — 查看 Pass 内部工作

```bash
# 查看 InstCombine 的每步变换
opt -debug-only=instcombine -passes=instcombine test.ll -S 2>&1

# 查看循环向量化决策
opt -debug-only=loop-vectorize -passes=loop-vectorize test.ll -S 2>&1

# 查看指令选择过程
llc -debug-only=isel test.ll -o /dev/null 2>&1

# 查看寄存器分配
llc -debug-only=regalloc test.ll -o /dev/null 2>&1

# 查看所有可用的调试类型
opt -debug-only=help 2>&1
```

---

## 4.5.3 print-changed — 观察 IR 如何逐步变换

```bash
# 每个 Pass 后打印 IR（只打印被修改的部分）
opt -print-changed -passes='default<O1>' test.ll -S 2>&1

# 只过滤特定函数
opt -print-changed -filter-print-funcs=foo \
    -passes='default<O1>' test.ll -S 2>&1

# 每个 Pass 之前打印
opt -print-before-all -passes='instcombine,gvn' test.ll -S 2>&1
```

---

## 4.5.4 verify-each — 检查 IR 合法性

```bash
# 每个 Pass 后验证 IR（快速定位哪个 Pass 产生了非法 IR）
opt -verify-each -passes='default<O1>' test.ll -S
```

---

## 4.5.5 性能计时和统计

```bash
# 查看每个 Pass 的耗时
opt -time-passes -passes='default<O1>' test.ll -S -o /dev/null 2>&1

# 查看每个 Pass 做了多少次变换
opt -stats -passes='default<O1>' test.ll -S -o /dev/null 2>&1
```

---

## 4.5.6 隔离问题函数

```bash
# 提取单个函数到独立文件
./build/bin/llvm-extract -func=problem_func input.bc -o func.bc
./build/bin/llvm-dis func.bc -o func.ll

# 对这个独立文件深入调试
./build/bin/opt -debug-only=my-pass func.ll -S
```

---

## 4.5.7 AddressSanitizer 构建

如果遇到段错误，用 ASan 构建 LLVM：

```bash
cmake -S llvm -B build-asan -G Ninja \
    -DCMAKE_BUILD_TYPE=Debug \
    -DLLVM_USE_SANITIZER=Address
ninja -C build-asan opt
./build-asan/bin/opt -passes=my-pass test.ll -S
# ASan 会给出详细的堆栈跟踪和内存错误报告
```

---

## 4.5.8 bugpoint — 自动缩减

```bash
# 自动缩减崩溃的 IR 和 Pass 列表
./build/bin/bugpoint test.ll -passes=my-pass
```

---

## 4.5.9 调试技巧速查

| 问题 | 工具 |
|------|------|
| "这个值是什么？" | `V->dump()` |
| "我的 Pass 修改了什么？" | `-print-changed` |
| "哪个 Pass 破坏了 IR？" | `-verify-each` |
| "为什么这个优化没有触发？" | `-debug-only=passname` |
| "段错误在哪？" | ASan 构建 |
| "为什么这么慢？" | `-time-passes` |

---

## 4.5.10 练习

1. 用 `-debug-only=instcombine` 观察 InstCombine 对 IR 的变换
2. 用 `-print-changed` 和 `-filter-print-funcs` 观察特定函数的变化
3. 用 `bugpoint` 创建一个最小的崩溃用例

