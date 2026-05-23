# 4.7 测试指南

> **学习目标**：掌握 LLVM 的测试框架——lit 测试、FileCheck、Google Test 单元测试的编写和运行。

---

## 4.7.1 测试框架概览

| 测试类型 | 框架 | 位置 | 运行 |
|---------|------|------|------|
| 回归测试 | lit + FileCheck | `llvm/test/` | `llvm-lit` |
| 单元测试 | Google Test | `llvm/unittests/` | `check-llvm-unit` |

---

## 4.7.2 lit 测试基础

### 最小测试文件

```llvm
; RUN: opt -passes=instcombine -S < %s | FileCheck %s

define i32 @test(i32 %x) {
; CHECK-LABEL: @test(
; CHECK-NEXT: ret i32 %x
  %r = add i32 %x, 0
  ret i32 %r
}
```

- `RUN:` — 执行命令
- `%s` — 当前测试文件路径
- `FileCheck` — 输出验证工具

### 替换变量

| 变量 | 含义 |
|------|------|
| `%s` | 测试文件路径 |
| `%t` | 临时文件路径 |
| `%S` | 测试文件所在目录 |
| `%clang` | clang 可执行文件 |
| `%opt` | opt 可执行文件 |

---

## 4.7.3 FileCheck 语法

### 基本指令

| 指令 | 说明 |
|------|------|
| `CHECK:` | 后续输出包含此行 |
| `CHECK-NEXT:` | 紧接着的下一行完全匹配 |
| `CHECK-SAME:` | 在同一行后面 |
| `CHECK-NOT:` | 后续输出**不**包含此行 |
| `CHECK-LABEL:` | 分隔不同函数的检查区域 |
| `CHECK-DAG:` | 包含此行但不要求顺序 |

### 变量捕获

```llvm
; CHECK: [[REG:%[a-z]+]] = add i32 %x, 1
; CHECK: ret i32 [[REG]]
```

### 多次 RUN

```llvm
; RUN: opt -passes=pass1 -S < %s | FileCheck --check-prefix=AFTER1 %s
; RUN: opt -passes=pass2 -S < %s | FileCheck --check-prefix=AFTER2 %s
```

---

## 4.7.4 update_test_checks.py — 自动生成断言

```bash
# 1. 写一个没有 CHECK 行但包含 RUN 行的测试文件
# 2. 运行这个脚本自动生成 CHECK 行
./llvm/utils/update_test_checks.py llvm/test/MyPass/test.ll

# 3. 检查生成的 CHECK 行是否合理
```

其他 update 工具：
- `update_cc_test_checks.py` — C/C++ 测试
- `update_analyze_test_checks.py` — 分析输出测试

---

## 4.7.5 测试约束

```llvm
; REQUIRES: x86-registered-target       # 需要 X86 后端
; REQUIRES: asserts                     # 需要断言开启的构建
; UNSUPPORTED: system-windows           # Windows 上跳过
; XFAIL: arm                           # ARM 上预期失败（已知 bug）
```

---

## 4.7.6 lit 命令行技巧

```bash
# 运行单个测试
./build/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/add.ll

# 运行整个目录
./build/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/

# 运行匹配名称的测试
./build/bin/llvm-lit -sv --filter 'MyPass' llvm/test/

# 显示失败测试的完整输出
./build/bin/llvm-lit -a llvm/test/Transforms/MyPass/
```

---

## 4.7.7 Google Test 单元测试

```cpp
#include "gtest/gtest.h"
#include "llvm/IR/Type.h"

TEST(TypeTest, GetInt32) {
    LLVMContext Ctx;
    IntegerType *I32Ty = IntegerType::get(Ctx, 32);
    EXPECT_EQ(I32Ty->getBitWidth(), 32u);
    EXPECT_TRUE(I32Ty->isIntegerTy());
}
```

```bash
ninja -C build check-llvm-unit
```

---

## 4.7.8 最佳实践

1. **最小化测试输入**：手写最小的 IR，不要用 clang 生成的几千行 IR
2. **正性 + 负性测试**：既要测"应该被优化"，也要测"不应被优化"
3. **永远不要用 grep**：用 FileCheck，不用 `grep | count`
4. **使用 stdin**：`opt < %s` 而不是 `opt %s`，避免路径差异
5. **使用 update_test_checks.py**：自动生成断言，避免手写错误

---

## 4.7.9 练习

1. 写一个 lit 测试验证 `instcombine` 对 `sub %x, 0` 的优化
2. 用 `update_test_checks.py` 为一个新 Pass 自动生成断言
3. 写一个 Google Test 测试 Type 类的去重行为

