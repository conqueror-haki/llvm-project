# 4.4 修改 Clang

> **学习目标**：理解如何修改 Clang 前端——添加编译警告、自定义属性、Pragma 指令。

---

## 4.4.1 添加编译警告

### Step 1：在 DiagnosticKinds.td 中定义警告

`clang/include/clang/Basic/DiagnosticSemaKinds.td`：

```tablegen
def warn_my_custom : Warning<
    "variable '%0' is declared but unused">,
    InGroup<UnusedVariable>;
```

### Step 2：在 Sema 中发出警告

`clang/lib/Sema/SemaDecl.cpp`：

```cpp
if (!VD->isUsed() && !VD->isReferenced()) {
    Diag(VD->getLocation(), diag::warn_my_custom) << VD->getName();
}
```

---

## 4.4.2 添加自定义属性

### Step 1：在 Attr.td 中定义

`clang/include/clang/Basic/Attr.td`：

```tablegen
def MyCustom : InheritableAttr {
    let Spellings = [Clang<"my_custom">];
    let Subjects = SubjectList<[Function, Var], ErrorDiag>;
    let Args = [StringArgument<"Message">];
}
```

### Step 2：在 SemaDeclAttr 中处理

`clang/lib/Sema/SemaDeclAttr.cpp`：

```cpp
static void handleMyCustomAttr(Sema &S, Decl *D, const ParsedAttr &AL) {
    StringRef Msg;
    if (!S.checkStringLiteralArgumentAttr(AL, 0, Msg))
        return;
    D->addAttr(::new (S.Context) MyCustomAttr(S.Context, AL, Msg));
}
```

---

## 4.4.3 添加 Pragma

### 关键文件

- `clang/include/clang/Basic/TokenKinds.def` — 添加 `ANNOTATION(pragma_my_pragma)`
- `clang/lib/Parse/ParsePragma.cpp` — 实现解析逻辑
- `clang/lib/Sema/SemaAttr.cpp` — 实现语义动作

---

## 4.4.4 练习

1. 添加一个警告：当用户使用 `goto` 时给出警告
2. 添加 `[[clang::my_custom]]` 属性，在编译时打印消息
3. 编写测试验证你的修改

