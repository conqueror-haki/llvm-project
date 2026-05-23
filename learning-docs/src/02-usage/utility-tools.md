# 2.7 辅助工具

> **学习目标**：掌握 LLVM 辅助分析工具——objdump、readelf、nm、mca 等的实际使用。

---

## 2.7.1 llvm-objdump —— 目标文件反汇编

```bash
# 反汇编所有代码节
llvm-objdump -d binary.o

# 使用 Intel 语法
llvm-objdump -d -M intel binary.o

# 反汇编并混入源代码（需要调试信息）
llvm-objdump -S binary.o

# 查看所有 Section Headers
llvm-objdump -h binary.o

# 查看符号表
llvm-objdump -t binary.o

# 查看重定位
llvm-objdump -r binary.o

# 查看文件头
llvm-objdump -f binary.o
```

---

## 2.7.2 llvm-readelf / llvm-readobj —— ELF 分析

```bash
# readelf 兼容模式
llvm-readelf -h binary.o       # ELF 文件头
llvm-readelf -l binary.o       # Program Headers
llvm-readelf -S binary.o       # Section Headers
llvm-readelf -s binary.o       # 符号表
llvm-readelf -a binary.o       # 所有信息

# readobj 模式（更详细）
llvm-readobj --file-header binary.o
llvm-readobj --sections binary.o
```

---

## 2.7.3 llvm-nm —— 符号表查看

```bash
llvm-nm binary.o                # 列出所有符号
llvm-nm -g binary.o             # 只显示外部符号
llvm-nm -u binary.o             # 只显示未定义符号
llvm-nm -n binary.o             # 按地址排序
llvm-nm -D libfoo.so            # 动态符号
```

---

## 2.7.4 llvm-mca —— 微架构性能分析

`llvm-mca` 分析汇编代码在特定 CPU 上的期望性能，而不实际运行它：

```bash
# 分析循环体在 Skylake 上的吞吐量
llvm-mca -march=x86-64 -mcpu=skylake loop.s

# 详细流水线视图
llvm-mca -march=x86-64 -mcpu=znver4 -all-views loop.s

# 只显示摘要
llvm-mca -march=x86-64 -mcpu=cortex-a76 -summary-view loop.s
```

---

## 2.7.5 其他常用工具

```bash
# 静态库打包
llvm-ar rcs libfoo.a foo.o bar.o

# 剥离符号
llvm-strip binary
llvm-strip -g binary            # 只去除调试信息

# 提取字符串
llvm-strings binary.o

# PGO 数据处理
llvm-profdata merge -o merged.profdata *.profraw

# 代码覆盖率
llvm-cov show ./test -instr-profile=default.profdata

# DWARF 调试信息分析
llvm-dwarfdump binary

# 地址转符号
llvm-symbolizer 0x401234 -e ./binary
```

---

## 2.7.6 练习

<div class="exercise">

### 练习

1. 用 `llvm-objdump -d -S` 分析一个带调试信息的可执行文件。
2. 用 `llvm-mca` 分析一段循环在两个不同 CPU 上的预期吞吐量。
3. 用 `llvm-size` 查看可执行文件中各段的体积分布。

</div>
