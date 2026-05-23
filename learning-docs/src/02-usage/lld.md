# 2.6 LLD 链接器

> **学习目标**：掌握 LLD 的核心用法——链接目标文件、使用链接脚本、ThinLTO、调试链接问题。

---

## 2.6.1 基本使用

```bash
# 直接调用（需要指定目标格式）
ld.lld -m elf_x86_64 file1.o file2.o -o output

# 通过 Clang 驱动调用（推荐）
clang -fuse-ld=lld file1.o file2.o -o output

# 全局设置
export LLD_DEFAULT_LD=lld
clang test.c -o test
```

---

## 2.6.2 ELF 链接常用操作

```bash
# 生成共享库
ld.lld -shared file1.o file2.o -o libfoo.so

# 生成位置无关可执行文件
ld.lld -pie file.o -o output

# 静态链接
ld.lld -static file.o -o output

# 指定入口点
ld.lld -e _start file.o -o output

# 使用链接脚本
ld.lld -T script.ld file.o -o output

# GC Sections（移除未引用节）
ld.lld --gc-sections file.o -o output

# 查看详细链接过程
ld.lld --verbose file.o -o output 2>&1
```

---

## 2.6.3 ThinLTO

ThinLTO 在链接时执行全程序优化：

```bash
# 编译时生成 ThinLTO 摘要
clang -c -flto=thin -O2 file1.c -o file1.o
clang -c -flto=thin -O2 file2.c -o file2.o

# LLD 自动执行 ThinLTO 优化
clang -fuse-ld=lld -flto=thin -O2 file1.o file2.o -o output
```

---

## 2.6.4 ICF（重复代码合并）

```bash
# 检测相同函数并合并
ld.lld --icf=safe file1.o file2.o -o output
```

---

## 2.6.5 调试链接问题

```bash
# 跟踪符号解析
ld.lld --trace file.o -o output

# 查看为什么某个 .o 被包含
ld.lld --why-extract=some_obj.o lib.a -o output

# 打印被 GC 移除的节
ld.lld --print-gc-sections file.o -o output 2>&1

# 输出完整的内存映射
ld.lld -Map=output.map file.o -o output

# 查看未定义符号
ld.lld --allow-shlib-undefined file.o -o output 2>&1
```

---

## 2.6.6 LLD 与其他链接器对比

| 特性 | GNU ld (bfd) | GNU gold | LLD |
|------|-------------|---------|-----|
| 链接速度 | 慢 | 快 | **最快** |
| 内存使用 | 低 | 中 | 中-低 |
| LTO 支持 | 有限 | ThinLTO | FullLTO + ThinLTO |
| 链接脚本 | 完整 | 有限 | 大部分 |
| ELF 兼容性 | 最广 | 好 | 好 |

---

## 2.6.7 练习

<div class="exercise">

### 练习

1. 链接两个 `.o` 文件（一个定义 `main`、一个定义辅助函数），用 LLD 链接。
2. 用 `--Map=output.map` 查看链接后的内存布局。
3. 对比 LLD 和 GNU ld 的链接速度。

</div>
