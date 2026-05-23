# 5.2 扩展阅读

以下资源有助于更深入地学习 LLVM。

## 官方文档（源码树内）

| 文档 | 路径 |
|------|------|
| IR 语言参考 | `llvm/docs/LangRef.rst` |
| 入门指南 | `llvm/docs/GettingStarted.rst` |
| 测试指南 | `llvm/docs/TestingGuide.rst` |
| Pass 列表 | `llvm/docs/Passes.rst` |
| TableGen | `llvm/docs/TableGen/` |
| 写 LLVM Pass | `llvm/docs/WritingAnLLVMPass.rst` |
| 写 LLVM 后端 | `llvm/docs/WritingAnLLVMBackend.rst` |
| 程序员手册 | `llvm/docs/ProgrammersManual.rst` |
| Kaleidoscope 教程 | `llvm/examples/Kaleidoscope/` |

## 书籍推荐

| 书名 | 说明 |
|------|------|
| "LLVM Techniques, Tips, and Best Practices" (Hsu, 2021) | 实用开发指南 |
| "Getting Started with LLVM Core Libraries" (Lopes & Auler, 2014) | 入门经典 |
| "LLVM Cookbook" (Pandey & Sarda, 2015) | 场景驱动 |
| "Engineering a Compiler" (Cooper & Torczon, 3rd ed.) | 编译器理论基础 |

## 关键论文

| 论文 | 说明 |
|------|------|
| "LLVM: A Compilation Framework..." (Lattner & Adve, 2004) | LLVM 基础论文 |
| "Simple and Efficient SSA Construction" (Braun et al., 2013) | SSA 构造算法 |
| "Linear Scan Register Allocation on SSA Form" (Wimmer & Mössenböck, 2004) | 寄存器分配 |

## 社区资源

| 资源 | 链接 |
|------|------|
| LLVM Discourse | https://discourse.llvm.org/ |
| LLVM Discord | https://discord.gg/xS7Z362 |
| Bug 追踪 | https://github.com/llvm/llvm-project/issues |
| 代码审查 | https://reviews.llvm.org/ |

## 代码阅读顺序

1. `llvm/examples/Kaleidoscope/` — 从零实现语言
2. `llvm/lib/IR/` — 核心 IR 数据结构
3. `llvm/lib/Transforms/InstCombine/` — 优化 Pass 最佳实践
4. `clang/lib/Lex/` + `clang/lib/Sema/` — 前端
5. `llvm/lib/CodeGen/SelectionDAG/` — 指令选择
6. `llvm/lib/Target/X86/` — 最成熟的后端

## 相关工具

| 工具 | 说明 |
|------|------|
| Compiler Explorer | 在线编译器对比（godbolt.org） |
| Alive2 | IR 优化自动验证 |
| KLEE | 符号执行引擎 |
| SVF | 指针分析框架 |

