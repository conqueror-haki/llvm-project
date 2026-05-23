# 3.3 Pass 体系

> **学习目标**：深入理解 New Pass Manager 的架构，掌握编写、注册和动态加载 Pass 的方法。
>
> **前置知识**：理解 LLVM IR 的核心数据结构（第 3.2 章），了解 opt 的使用（第 2.4 章）。

---

## 3.3.1 New Pass Manager 的四种 Pass 类型

| 类型 | 基类 | 操作范围 | 使用场景 |
|------|------|---------|---------|
| FunctionPass | `PassInfoMixin` on `Function` | 每个函数独立 | InstCombine, GVN, DCE |
| ModulePass | `PassInfoMixin` on `Module` | 整个 Module | Inliner, GlobalOpt, IPO |
| LoopPass | `PassInfoMixin` on `Loop` | 每个循环独立 | LICM, LoopVectorize |
| CGSCCPass | `PassInfoMixin` on `LazyCallGraph::SCC` | 调用图 SCC | 自底向上的过程间优化 |

---

## 3.3.2 FunctionPass 的完整模板

```cpp
#include "llvm/IR/PassManager.h"
#include "llvm/Passes/PassBuilder.h"
#include "llvm/Passes/PassPlugin.h"

using namespace llvm;

namespace {

class MyPass : public PassInfoMixin<MyPass> {
public:
    PreservedAnalyses run(Function &F, FunctionAnalysisManager &AM) {
        bool Changed = false;

        for (BasicBlock &BB : F) {
            for (Instruction &I : BB) {
                // 在这里修改 IR
            }
        }

        return Changed ? PreservedAnalyses::none()
                       : PreservedAnalyses::all();
    }
};

} // namespace
```

---

## 3.3.3 PreservedAnalyses — 分析失效管理

LLVM 会缓存分析结果（支配树、循环信息等）以提高效率。当 Pass 修改了 IR，一些分析结果可能失效。

```cpp
// 没有修改任何东西 → 所有分析有效
return PreservedAnalyses::all();

// 修改了指令操作数，但没有改变控制流
PreservedAnalyses PA;
PA.preserve<DominatorTreeAnalysis>();  // 支配树仍然有效
PA.preserve<LoopAnalysis>();           // 循环信息仍然有效
return PA;

// 几乎修改了所有东西（插入/删除了基本块）
return PreservedAnalyses::none();
```

**常见规则**：
- 只替换操作数 → `all()` 通常安全
- 插入/删除基本块 → `none()` 最安全
- 修改了控制流（br 指令的目标变了）→ 至少需要重新计算支配树

---

## 3.3.4 Pass 注册的三种方式

### 方式一：动态插件（独立开发）

```cpp
extern "C" LLVM_ATTRIBUTE_WEAK PassPluginLibraryInfo
llvmGetPassPluginInfo() {
    return {LLVM_PLUGIN_API_VERSION, "MyPass", "v0.1",
            [](PassBuilder &PB) {
                PB.registerPipelineParsingCallback(
                    [](StringRef Name, FunctionPassManager &FPM,
                       ArrayRef<PassBuilder::PipelineElement>) {
                        if (Name == "my-pass") {
                            FPM.addPass(MyPass());
                            return true;
                        }
                        return false;
                    });
            }};
}
```

使用：
```bash
clang++ -shared -fPIC MyPass.cpp -o MyPass.so
opt -load-pass-plugin=./MyPass.so -passes=my-pass input.ll -S
```

### 方式二：在 LLVM 源码树内注册（PassRegistry.def）

在 `llvm/include/llvm/Passes/PassRegistry.def` 中添加：

```
FUNCTION_PASS("my-pass", MyPass())
```

### 方式三：在 Pass Builder 中注册

在 `llvm/lib/Passes/PassBuilderPipelines.cpp` 中修改管线构建函数：

```cpp
FPM.addPass(MyPass());
```

---

## 3.3.5 Pass 管线构建过程

在 `PassBuilderPipelines.cpp` 中，`buildFunctionSimplificationPipeline` 函数构建 O2 的函数 Pass 管线。简化版：

```cpp
void PassBuilder::buildFunctionSimplificationPipeline(
    FunctionPassManager &FPM, OptimizationLevel Level) {
    
    // 第一阶段：标量清理
    FPM.addPass(SROAPass());
    FPM.addPass(EarlyCSEPass());
    FPM.addPass(SimplifyCFGPass());
    
    // 第二阶段：指令合并 + 内联（循环）
    FPM.addPass(InstCombinePass());
    
    // 第三阶段：循环优化（内嵌的 LoopPassManager）
    LoopPassManager LPM;
    LPM.addPass(LoopRotatePass());
    LPM.addPass(LICMPass());
    LPM.addPass(SimpleLoopUnswitchPass());
    FPM.addPass(createFunctionToLoopPassAdaptor(std::move(LPM)));
    
    // 第四阶段：标量优化
    FPM.addPass(GVNPass());
    FPM.addPass(InstCombinePass());
    FPM.addPass(SimplifyCFGPass());
}
```

---

## 3.3.6 使用分析 Pass

```cpp
#include "llvm/IR/Dominators.h"

PreservedAnalyses MyPass::run(Function &F, FunctionAnalysisManager &AM) {
    // 获取支配树（如果尚未计算，会自动计算）
    DominatorTree &DT = AM.getResult<DominatorTreeAnalysis>(F);
    
    // 使用支配树
    BasicBlock *Entry = &F.getEntryBlock();
    for (BasicBlock &BB : F) {
        DomTreeNode *Node = DT.getNode(&BB);
        if (Node) {
            BasicBlock *IDom = Node->getIDom()->getBlock();
            errs() << BB.getName() << " is dominated by " 
                   << IDom->getName() << "\n";
        }
    }
    
    return PreservedAnalyses::all();
}
```

---

## 3.3.7 Legacy PM 对照

| 概念 | Legacy PM | New PM |
|------|-----------|--------|
| 基类 | `FunctionPass` | `PassInfoMixin<MyPass>` |
| 入口 | `runOnFunction(F)` | `run(Function &F, AnalysisManager &AM)` |
| 获取分析 | `getAnalysis<DominatorTree>()` | `AM.getResult<DominatorTreeAnalysis>(F)` |
| 注册 | `char ID` + `RegisterPass<>` | `PassPluginLibraryInfo` |
| CLI | `opt -mypass` | `opt -passes=my-pass` |
| 动态加载 | 不支持 | `-load-pass-plugin=lib.so` |

---

## 3.3.8 常见错误

### 在遍历中修改 IR

```cpp
// 错误！迭代器失效
for (Instruction &I : BB) {
    if (shouldDelete(I))
        I.eraseFromParent();
}

// 正确：先收集，后删除
SmallVector<Instruction *, 8> ToDelete;
for (Instruction &I : BB)
    if (shouldDelete(I))
        ToDelete.push_back(&I);
for (Instruction *I : ToDelete)
    I->eraseFromParent();
```

### return PreservedAnalyses::all() 但修改了 IR

如果你的 Pass 修改了 IR 但声称所有分析有效，后续 Pass 可能使用无效的缓存分析结果，导致神秘崩溃。

---

## 3.3.9 练习

1. 从第 4.2 章的模板开始，编写并测试一个打印函数信息的 Pass
2. 在 Pass 中获取并使用 DominatorTree 分析
3. 阅读 `PassBuilderPipelines.cpp` 中的 O2 管线构建函数

