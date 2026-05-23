# 3.4 Clang 前端

> **学习目标**：理解 Clang 如何将 C 源代码逐步转换为 LLVM IR——从词法分析到语义分析到 IR 生成。
>
> **前置知识**：基本的编译原理知识（词法、语法、语义分析），了解 C/C++ 语言。

---

## 3.4.1 前端编译管线

```
C 源码 → Lexer → Token 流 → Parser → AST → Sema → 类型正确的 AST → CodeGen → LLVM IR
```

---

## 3.4.2 Lexer（词法分析器）

### 职责

将字符流转换为 Token 流。例如：

```c
int x = 42;
```
产生 Token：
```
Keyword:int  Identifier:x  Equal  NumericConstant:42  Semi
```

### 关键文件

| 文件 | 说明 |
|------|------|
| `clang/lib/Lex/Lexer.cpp` | 核心词法分析器 |
| `clang/lib/Lex/Preprocessor.cpp` | 预处理器（#include、#define） |
| `clang/include/clang/Basic/TokenKinds.def` | 所有 Token 种类的定义 |

---

## 3.4.3 Parser（语法分析器）

### 职责

将 Token 流转换为 AST。Clang 使用手写的**递归下降**解析器。

### 关键文件

| 文件 | 说明 |
|------|------|
| `clang/lib/Parse/ParseExpr.cpp` | 表达式解析 |
| `clang/lib/Parse/ParseDecl.cpp` | 声明解析 |
| `clang/lib/Parse/ParseStmt.cpp` | 语句解析 |

### 递归下降解析的核心模式

```cpp
// 以 if 语句为例
StmtResult Parser::ParseIfStatement() {
    ConsumeToken();  // 消费 'if'
    ParseParen();     // 消费 '('
    ExprResult Cond = ParseExpression();
    ParseParen();     // 消费 ')'
    StmtResult Then = ParseStatement();
    StmtResult Else;
    if (Tok.is(tok::kw_else)) {
        ConsumeToken();
        Else = ParseStatement();
    }
    return Actions.ActOnIfStmt(Cond, Then, Else);  // 调用 Sema
}
```

---

## 3.4.4 Sema（语义分析器）

### 职责

Sema 是 Clang 中最大、最复杂的模块。它负责：
1. **类型检查**：`int x = "hello"` 是否合法？
2. **符号解析**：`x` 是哪个变量？
3. **作用域管理**：嵌套的 `{}`
4. **C++ 重载决议**：调用哪个重载？
5. **模板实例化**
6. **隐式类型转换的插入**
7. **发出诊断**（警告和错误）

### 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `SemaExpr.cpp` | >6000 行 | 表达式语义分析 |
| `SemaDecl.cpp` | >4000 行 | 声明处理 |
| `SemaOverload.cpp` | >3000 行 | C++ 重载决议 |
| `SemaTemplate.cpp` | >3000 行 | 模板实例化 |

### 类型检查示例（C++ 二元运算符）

```cpp
// SemaExpr.cpp 中的简化逻辑
QualType Sema::CheckAdditionOperands(ExprResult &LHS, ExprResult &RHS) {
    // 如果操作数是 int 和 float
    if (LHS->getType()->isIntegerType() && RHS->getType()->isFloatingType()) {
        // 插入隐式转换：int → float
        LHS = ImpCastExprToType(LHS, RHS->getType());
    }
    // 返回结果的类型
    return UsualArithmeticConversions(LHS, RHS);
}
```

---

## 3.4.5 AST 结构

### AST 节点层次

```
Stmt（语句）
├── Expr（表达式）
│   ├── IntegerLiteral（整数字面量）
│   ├── DeclRefExpr（引用变量声明）
│   ├── BinaryOperator（二元运算）
│   ├── CallExpr（函数调用）
│   └── ImplicitCastExpr（隐式类型转换）
├── IfStmt / ForStmt / WhileStmt
├── ReturnStmt
└── CompoundStmt（{ ... }）

Decl（声明）
├── FunctionDecl
├── VarDecl / ParmVarDecl
├── CXXRecordDecl（C++ class）
└── EnumDecl

Type（类型）
├── BuiltinType（int, float, char, ...）
├── PointerType
├── ArrayType
└── RecordType（struct/class）
```

### AST 查看工具

```bash
# 文本 AST Dump
clang -Xclang -ast-dump -fsyntax-only test.c

# 图形化 AST（需要 Graphviz）
clang -Xclang -ast-view test.c
```

---

## 3.4.6 RecursiveASTVisitor

遍历 AST 的标准方式：

```cpp
class MyVisitor : public RecursiveASTVisitor<MyVisitor> {
public:
    bool VisitFunctionDecl(FunctionDecl *FD) {
        llvm::outs() << "Function: " << FD->getName() << "\n";
        return true;  // 继续遍历子节点
    }
    
    bool VisitIfStmt(IfStmt *S) {
        llvm::outs() << "Found if statement\n";
        return true;
    }
};
```

---

## 3.4.7 CodeGen — AST → LLVM IR

### 职责

将语义分析后类型正确的 AST 翻译为 LLVM IR。

### 关键文件

| 文件 | 大小 | 说明 |
|------|------|------|
| `CGExpr.cpp` | >6000 行 | 表达式代码生成 |
| `CodeGenFunction.cpp` | >4000 行 | 函数级代码生成 |
| `CGStmt.cpp` | 语句代码生成 |
| `CGDecl.cpp` | 声明代码生成 |

### 关键设计：先 alloca 后 mem2reg

Clang CodeGen 生成"粗糙"的初始 IR：每个局部变量用 `alloca` 栈分配。后续 LLVM 的 `mem2reg` Pass 自动提升为 SSA 形式的 PHI 节点。

```
C 断言           →  O0 IR（粗糙）   →  O2 IR（mem2reg + 优化）
---------------------------------------------------------------
int x = a + b;      alloca + store + load   直接使用 a + b
```

这种设计**极大简化了 CodeGen**——CodeGen 不需要关心 SSA 的复杂性，只需要忠实地翻译每个语句。

---

## 3.4.8 练习

1. 用 `-Xclang -ast-dump` 查看一个简单 C 程序的完整 AST
2. 写一个 RecursiveASTVisitor 遍历所有函数声明
3. 在 CodeGen 中搜索 `EmitBinaryOperator`，理解基本的表达式代码生成逻辑

