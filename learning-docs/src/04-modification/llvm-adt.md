# 4.6 LLVM 容器与工具类

> **学习目标**：掌握 LLVM 特有的容器和工具类——SmallVector、DenseMap、StringRef、Twine、raw_ostream 等。

---

## 4.6.1 为什么不用 STL？

LLVM 提供了自己的一套"标准库"替代品。原因：
1. **更高效**：针对编译器工作负载优化（小容量栈分配、自定义哈希）
2. **统一接口**：所有 LLVM 代码使用相同的容器，减少碎片化
3. **Debug 友好**：LLVM 的 Debug 构建提供越界检查、迭代器验证

---

## 4.6.2 SmallVector —— 最常用的容器

```cpp
#include "llvm/ADT/SmallVector.h"

// SmallVector<T, N> — 栈上预分配 N 个元素
SmallVector<Instruction *, 8> Worklist;

Worklist.push_back(I);
Worklist.push_back(I2);

for (Instruction *I : Worklist) { ... }
```

核心优化：当元素 ≤ N 时完全避免堆分配。编译器中大量"收集少量元素"的操作（收集操作数、遍历候选）都受益于这个优化。

**选择 N 的原则**：选择最常见的数量 + 一些余量。例如，函数调用通常 ≤ 4 个参数 → `SmallVector<Value *, 4>`。

---

## 4.6.3 SmallPtrSet / SmallString

```cpp
SmallPtrSet<Value *, 16> Visited;
Visited.insert(V);
if (Visited.contains(OtherV)) { ... }

SmallString<256> Path;
raw_svector_ostream OS(Path);
OS << "/path/to/" << Name << ".ll";
StringRef Result = Path.str();
```

---

## 4.6.4 DenseMap —— 高密度哈希表

```cpp
#include "llvm/ADT/DenseMap.h"

DenseMap<Value *, unsigned> RefCount;
RefCount[V] = 1;
unsigned Count = RefCount[V];
RefCount.erase(V);
```

> ⚠️ **警告**：DenseMap 的迭代器在插入/删除后失效。不能在遍历中修改 DenseMap。先收集 key 到 SmallVector：

```cpp
SmallVector<Value *, 8> KeysToRemove;
for (auto &KV : Map)
    if (shouldRemove(KV.first))
        KeysToRemove.push_back(KV.first);
for (Value *K : KeysToRemove)
    Map.erase(K);
```

---

## 4.6.5 StringRef —— 零拷贝字符串

```cpp
#include "llvm/ADT/StringRef.h"

StringRef S = F.getName();       // 不拷贝
if (S.startswith("__")) { ... }
if (S.endswith(".cpp")) { ... }

// 分割
StringRef Left, Right;
std::tie(Left, Right) = S.split(':');
```

> ⚠️ **警告**：StringRef 不拥有内存。不要将 StringRef 绑定到临时对象：

```cpp
// 错误！
StringRef Bad = std::string("temp");  // temp 立即销毁，Bad 悬空

// 正确：
std::string Temp = "temp";
StringRef Good = Temp;  // Temp 存活，Safe
```

---

## 4.6.6 Twine —— 零拷贝字符串拼接

```cpp
#include "llvm/ADT/Twine.h"

// 零拷贝拼接（只在 .str() 或输出时才分配）
errs() << Twine("Processing function: ") + F.getName() + "\n";
```

> ⚠️ **警告**：Twine 的生命周期仅在表达式内有效。不要存储到变量中跨越原始数据的生命周期。

---

## 4.6.7 ArrayRef —— 数组视图

```cpp
#include "llvm/ADT/ArrayRef.h"

void processOperands(ArrayRef<Value *> Ops) {
    for (Value *Op : Ops) { ... }
}

std::vector<Value *> V = {A, B, C};
processOperands(V);        // 隐式转换
processOperands({X, Y});   // 初始化列表
```

---

## 4.6.8 raw_ostream —— 输出流

```cpp
#include "llvm/Support/raw_ostream.h"

errs() << "Error: " << Msg << "\n";    // stderr
outs() << "Result: " << Val << "\n";    // stdout
nulls() << "discarded\n";              // /dev/null

// 输出到字符串
std::string Buffer;
raw_string_ostream StrStream(Buffer);
StrStream << "Generated: " << Name;
StrStream.flush();  // 必须 flush！
```

---

## 4.6.9 LLVM 的智能类型转换

```cpp
// isa<T>(V) — 类型判断
if (isa<PHINode>(I)) { ... }

// cast<T>(V) — 强制转换（debug 检查，release 下 = static_cast）
PHINode &PN = cast<PHINode>(I);

// dyn_cast<T>(V) — 安全转换（失败返回 nullptr）
if (PHINode *PN = dyn_cast<PHINode>(I)) {
    PN->getIncomingValue(0);
}
```

这些比 C++ 的 `dynamic_cast` 快很多，因为 LLVM 使用自己的类型标识系统（每个 Value 有 SubclassID 字段）。

---

## 4.6.10 容器选择速查

| 需求 | 推荐 |
|------|------|
| 变长数组（元素少） | `SmallVector<T, N>` |
| 变长数组（元素多） | `SmallVector<T, 0>` |
| 唯一元素集合 | `SmallPtrSet<T, N>` |
| 键值映射 | `DenseMap<K, V>` |
| 字符串参数 | `StringRef` |
| 字符串拼接 | `Twine` |
| 数组视图 | `ArrayRef<T>` |
| 输出流 | `raw_ostream` (errs/outs) |
| 字符串构建 | `raw_string_ostream` + `SmallString` |

---

## 4.6.11 练习

1. 浏览 `llvm/include/llvm/ADT/SmallVector.h`，理解其内存布局
2. 在你的 Pass 中用 SmallVector 替换 std::vector
3. 用 raw_string_ostream 构建一个复杂字符串
4. 理解 Twine 的生命周期限制，写一个"错误使用"的例子

