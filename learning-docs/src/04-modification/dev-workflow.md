# 4.1 开发工作流

> **学习目标**：掌握 LLVM 开发的完整循环——修改代码→增量构建→测试→格式化→提交。

---

## 4.1.1 典型开发循环

```
  ┌──────────────────────────────────┐
  │  1. 修改源代码（C++ / .td）       │
  └───────────────┬──────────────────┘
                  ▼
  ┌──────────────────────────────────┐
  │  2. 增量构建（只构建修改的组件）  │
  │     ninja -C build opt           │
  └───────────────┬──────────────────┘
                  ▼
  ┌──────────────────────────────────┐
  │  3. 运行测试（只跑相关的测试）    │
  │     llvm-lit llvm/test/Subdir/   │
  └───────────────┬──────────────────┘
         ┌────────┴─────────┐
         ▼                  ▼
      通过               失败 → 调试 → 回到步 1
         │
         ▼
  ┌──────────────────────────────────┐
  │  4. 编写/更新 lit 测试文件       │
  └───────────────┬──────────────────┘
                  ▼
  ┌──────────────────────────────────┐
  │  5. 格式化代码                   │
  │     git-clang-format main        │
  └───────────────┬──────────────────┘
                  ▼
  ┌──────────────────────────────────┐
  │  6. 提交                        │
  │     git commit -m "[Tag] desc"  │
  └──────────────────────────────────┘
```

---

## 4.1.2 增量构建

**永远不要重新构建整个项目！** 针对你修改的模块做增量构建：

```bash
# 修改了 Pass 代码 → 只构建 opt
ninja -C build opt

# 修改了后端代码 → 只构建 llc
ninja -C build llc

# 修改了 Clang 代码 → 只构建 clang
ninja -C build clang

# 修改了 TableGen 文件 → 构建 llc + llvm-tblgen
ninja -C build llc
```

如何确定应该构建哪个目标？修改了 `llvm/lib/Transforms/InstCombine/` 的代码 → `ninja -C build opt`。修改了 `clang/lib/Sema/` 的代码 → `ninja -C build clang`。

### 快速原型（插件）

如果你在做实验性开发，可以使用 Pass 插件动态加载，避免重新构建 opt：

```bash
clang++ -shared -fPIC MyPass.cpp `llvm-config --cxxflags --ldflags --libs` -o MyPass.so
opt -load-pass-plugin=./MyPass.so -passes=my-pass test.ll -S
```

---

## 4.1.3 运行测试

```bash
# 运行 LLVM 全部测试
ninja -C build check-llvm

# 只运行你修改的模块的测试
./build/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/

# 运行单个测试文件
./build/bin/llvm-lit -sv llvm/test/Transforms/InstCombine/add.ll

# 运行匹配名称的测试
./build/bin/llvm-lit -sv --filter 'MyPass' llvm/test/

# 显示失败测试的完整输出
./build/bin/llvm-lit -a llvm/test/Transforms/MyPass/
```

---

## 4.1.4 编写测试

### lit 测试模板

```llvm
; RUN: opt -passes=my-pass -S < %s | FileCheck %s

define i32 @test(i32 %x) {
; CHECK-LABEL: @test(
; CHECK: ret i32 42
  ret i32 %x
}
```

### 自动生成检查行

```bash
./llvm/utils/update_test_checks.py llvm/test/Transforms/MyPass/test.ll
```

---

## 4.1.5 代码格式

```bash
# 格式化所有修改的文件（相对于 main 分支）
git-clang-format main

# 只格式化特定文件
clang-format -i llvm/lib/Transforms/Scalar/MyPass.cpp
```

LLVM 使用 `BasedOnStyle: LLVM`，行尾 LF。CI 会在 PR 时检查格式。

---

## 4.1.6 Commit 消息

```
[Tag] 简短描述（≤72 字符）

详细描述（每行 ≤72 字符）：
- 做了什么
- 为什么这样做
- 对性能/测试的影响
```

示例：
```
[InstCombine] Fold (X << C1) >> C2 into X << (C1 - C2)

When C1 >= C2, (X << C1) >> C2 is equivalent to X << (C1 - C2).
This pattern appears frequently in bit-manipulation code.
```

---

## 4.1.7 常见开发任务速查

| 任务 | 修改位置 | 构建目标 | 测试目录 |
|------|---------|---------|---------|
| LLVM Pass | `llvm/lib/Transforms/` | `opt` | `llvm/test/Transforms/` |
| 后端指令 | `llvm/lib/Target/X86/*.td` | `llc` | `llvm/test/CodeGen/X86/` |
| Clang 警告 | `clang/lib/Sema/` | `clang` | `clang/test/Sema/` |
| Clang AST 属性 | `clang/include/clang/Basic/Attr.td` | `clang` | `clang/test/Sema/` |

---

## 4.1.8 快速开发配置

```bash
cmake -S llvm -B build -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON \
    -DLLVM_CCACHE_BUILD=ON \
    -DLLVM_USE_LINKER=lld \
    -DLLVM_TARGETS_TO_BUILD="X86" \
    -DLLVM_ENABLE_PROJECTS="clang"
ninja -C build opt llc clang
```

---

## 4.1.9 练习

1. 修改 `clang/lib/Sema/SemaDecl.cpp` 中的注释，只构建 clang，观察增量构建速度
2. 写一个最简单的 lit 测试文件并运行
3. 运行 `git-clang-format main` 检查代码格式

