# 4.2 编写一个 Pass

> **学习目标**：从零开始编写一个完整的 LLVM Pass，包括代码、集成到构建系统、注册到 Pass 管线和测试验证。

---

## 4.2.1 目标：Function 统计 Pass

创建 Pass 打印每个函数的名称、基本块数量和指令数量。

---

## 4.2.2 Step 1：创建源文件

```bash
mkdir -p llvm/lib/Transforms/HelloWorld
```

`llvm/lib/Transforms/HelloWorld/HelloWorld.cpp`：

```cpp
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"
#include "llvm/Support/raw_ostream.h"

using namespace llvm;

namespace {

class HelloWorldPass : public PassInfoMixin<HelloWorldPass> {
public:
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM) {
        errs() << "Function: " << F.getName() << "\n"
               << "  BB count: " << F.size() << "\n"
               << "  Instruction count: " << F.getInstructionCount() << "\n\n";
        return PreservedAnalyses::all();
    }
};

} // namespace

extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo
llvmGetPassPluginInfo() {
    return {LLVM_PLUGIN_API_VERSION, "HelloWorld", "v0.1",
            [](PassBuilder &PB) {
                PB.registerPipelineParsingCallback(
                    [](StringRef Name, FunctionPassManager &FPM,
                       ArrayRef<PassBuilder::PipelineElement>) {
                        if (Name == "hello-world") {
                            FPM.addPass(HelloWorldPass());
                            return true;
                        }
                        return false;
                    });
            }};
}
```

---

## 4.2.3 Step 2：集成到 CMake

`llvm/lib/Transforms/HelloWorld/CMakeLists.txt`：

```cmake
add_llvm_component_library(LLVMHelloWorld
    HelloWorld.cpp
    LINK_COMPONENTS Core Support
)
```

在 `llvm/lib/Transforms/CMakeLists.txt` 末尾添加：

```cmake
add_subdirectory(HelloWorld)
```

---

## 4.2.4 Step 3：构建并测试

```bash
cmake -S llvm -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_ENABLE_ASSERTIONS=ON
ninja -C build opt
```

测试 IR：

```llvm
; test.ll
define i32 @foo(i32 %a, i32 %b) {
  %s = add i32 %a, %b
  ret i32 %s
}
```

运行：

```bash
./build/bin/opt -load-pass-plugin=./build/lib/LLVMHelloWorld.so \
    -passes=hello-world test.ll -disable-output
# 输出：
# Function: foo
#   BB count: 1
#   Instruction count: 2
```

---

## 4.2.5 Step 4：完整的 lit 测试

`llvm/test/Transforms/HelloWorld/hello.ll`：

```llvm
; RUN: opt -load-pass-plugin=%shlibdir/LLVMHelloWorld%shlibext \
; RUN:     -passes=hello-world -disable-output < %s 2>&1 | FileCheck %s

; CHECK: Function: foo
; CHECK: BB count: 1

define i32 @foo(i32 %a, i32 %b) {
  %s = add i32 %a, %b
  ret i32 %s
}
```

---

## 4.2.6 Step 5：进阶——修改 IR 的 Pass

将所有的 `add` 替换为 `sub` 的 Pass：

```cpp
class AddToSubPass : public PassInfoMixin<AddToSubPass> {
public:
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM) {
        bool Changed = false;
        for (BasicBlock &BB : F) {
            for (Instruction &I : BB) {
                if (auto *BO = dyn_cast<BinaryOperator>(&I)) {
                    if (BO->getOpcode() == Instruction::Add) {
                        auto *NewBO = BinaryOperator::Create(
                            Instruction::Sub,
                            BO->getOperand(0), BO->getOperand(1),
                            "", BO);
                        BO->replaceAllUsesWith(NewBO);
                        BO->eraseFromParent();
                        Changed = true;
                    }
                }
            }
        }
        return Changed ? PreservedAnalyses::none()
                       : PreservedAnalyses::all();
    }
};
```

---

## 4.2.7 常犯错误

### 错误 1：遍历中删除指令（段错误）

```cpp
// 错误！
for (Instruction &I : BB) {
    if (shouldDelete(I))
        I.eraseFromParent();  // 迭代器失效！
}

// 正确：
SmallVector<Instruction *, 8> ToDelete;
for (Instruction &I : BB)
    if (shouldDelete(I)) ToDelete.push_back(&I);
for (Instruction *I : ToDelete) I->eraseFromParent();
```

### 错误 2：return all() 但修改了 IR

如果修改了 IR 却声称所有分析有效，后续 Pass 可能崩溃。

---

## 4.2.8 练习

1. 在 LLVM 源码树内创建并构建 HelloWorld Pass
2. 修改 HelloWorld 为遍历所有 call 指令，打印被调用者名称
3. 实现 AddToSub Pass，写 lit 测试验证

