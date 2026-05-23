# 5.1 术语表

LLVM 社区有大量专业术语。这里整理了最常见的术语及其简明解释。

## 基础概念

| 术语 | 英文 | 说明 |
|------|------|------|
| IR | Intermediate Representation | 中间表示。LLVM IR 是 LLVM 生态的核心 |
| Bitcode | LLVM Bitcode | IR 的二进制格式（`.bc` 文件） |
| LLVM Assembly | LLVM IR 文本格式 | IR 的人类可读形式（`.ll` 文件） |
| SSA | Static Single Assignment | 静态单赋值形式——每个寄存器只能被赋值一次 |
| PHI 节点 | PHI Node | SSA 中实现分支合并的特殊指令 |

## 编译管线

| 术语 | 说明 |
|------|------|
| 前端 (Frontend) | 源代码 → LLVM IR（如 Clang） |
| 中端 (Middle-end) | IR 上的优化 Passes（opt） |
| 后端 (Backend) | IR → 目标机器码（llc） |
| 驱动 (Driver) | clang 可执行文件——调度子进程 |
| cc1 | Clang 编译器核心进程 |

## Pass 体系

| 术语 | 说明 |
|------|------|
| Pass | 对 IR 的一次扫描/变换 |
| Pass Manager | 调度 Pass 执行的框架 |
| Legacy PM | 旧 Pass 管理器 | 
| New PM | 新 Pass 管理器（推荐） |
| Analysis Pass | 不修改 IR，只提供分析结果 |
| Transform Pass | 修改 IR 的 Pass |

## IR 概念

| 术语 | 说明 |
|------|------|
| Module | 编译单元 |
| Function | 函数，包含基本块列表 |
| BasicBlock | 基本块，一串无分支指令 |
| Value | IR 中几乎所有东西都是 Value |
| User | 使用其他 Value 的对象 |
| Use | 连接 User 和 Value 的边 |
| UndefValue | 未定义值 |
| PoisonValue | 毒化值——使用导致未定义行为 |

## 后端概念

| 术语 | 说明 |
|------|------|
| SelectionDAG | 目标无关的指令选择框架 |
| MachineInstr (MI) | 机器指令 |
| MC | Machine Code 层 |
| ISel | 指令选择 |
| Greedy RA | 贪婪寄存器分配器 |
| Fast RA | 快速寄存器分配器 |

## 编译时技术

| 术语 | 说明 |
|------|------|
| LTO | 链接时优化 |
| ThinLTO | 增量 LTO（推荐） |
| PGO | Profile-Guided Optimization |
| Sanitizer | 运行时检测工具（ASan、TSan、UBSan） |

## Clang 特定

| 术语 | 说明 |
|------|------|
| Lexer | 词法分析器 |
| Parser | 语法分析器（递归下降） |
| Sema | 语义分析器（最大模块） |
| AST | 抽象语法树 |
| CodeGen | AST → LLVM IR 的翻译 |

## 构建与测试

| 术语 | 说明 |
|------|------|
| CMake | 构建系统生成器 |
| Ninja | 快速构建工具 |
| TableGen | LLVM 的 DSL 和代码生成器 |
| lit | LLVM 集成测试工具 |
| FileCheck | 输出验证工具 |
| ccache | 编译缓存 |

