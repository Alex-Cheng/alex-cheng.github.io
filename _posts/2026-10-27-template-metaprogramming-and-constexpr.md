# 模板元编程与 constexpr：把计算搬到编译期

运行时的每一次计算都要消耗 CPU 时间。但如果一个结果在编译期就能确定，为什么还要等到运行时？C++ 的回答延续了零成本抽象的思路：能在编译期做的，就不要拖到运行时。这篇文章讲两件事——模板元编程（Template Metaprogramming）如何最早打开编译期计算的大门，以及 constexpr 如何把这件事从"黑魔法"变成普通写法。

## 模板元编程：藏在编译器里的语言

模板元编程是利用模板的实例化与特化机制，在编译期完成计算、条件分支、递归展开和代码生成的技术。它有三样基本工具：

| 需求 | 手段 |
| ---- | ---- |
| 计算 | 用模板参数做数值和类型运算 |
| 循环 | 模板递归实例化 |
| 分支 | SFINAE 或特化 |

> 模板元编程在理论上是图灵完备的——编译器在实例化模板时，跑的是一台完整的图灵机。

最经典的例子是编译期算阶乘：

```cpp
// 经典模板元编程写法（早于 constexpr，C++11 起可用 constexpr 成员）
template <int N>
struct Factorial {
    static constexpr int value = N * Factorial<N - 1>::value;
};

template <>
struct Factorial<0> {
    static constexpr int value = 1;
};

constexpr int result = Factorial<5>::value;  // 编译期得到 120
```

递归用特化终止，循环变成了实例化链。运行时 `result` 就是常量 120，没有任何计算开销——但代价是代码形态：把乘法写成类型系统里的递归，可读性一目了然。

## SFINAE：晦涩但强大的条件选择

SFINAE（Substitution Failure Is Not An Error）让编译器在模板实例化时做条件选择：某个候选模板在替换参数时失败，不算编译错误，只是这个候选被排除。编译器在剩下的候选里挑唯一匹配的那个：

```cpp
#include <type_traits>

// 只对整数类型启用
template <typename T>
typename std::enable_if<std::is_integral<T>::value, T>::type
process(T value) {
    return value * 2;
}

// 只对浮点类型启用
template <typename T>
typename std::enable_if<std::is_floating_point<T>::value, T>::type
process(T value) {
    return value * 3.14;
}

int main() {
    auto a = process(10);      // 调用整数版本，返回 20
    auto b = process(3.0);     // 调用浮点版本，返回 9.42
    // auto c = process("hi"); // 编译错误：没有匹配的函数
}
```

SFINAE 是模板元编程实现类型分支的核心技术，但语法极其晦涩——好在它后来被 `if constexpr` 和 concept 大幅简化了。

## constexpr：更现代的写法

同样的阶乘，用 constexpr 写：

```cpp
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

constexpr int result = factorial(5);  // 编译期得到 120
```

语法就是普通函数，既能在编译期调用，也能在运行时调用。能力边界还在持续扩展：

| 版本 | 新增能力 |
| ---- | ---- |
| **C++11** | constexpr 函数（函数体基本只能是一条 return） |
| **C++14** | 函数体支持循环、分支、局部变量 |
| **C++17** | constexpr lambda、if constexpr |
| **C++20** | constexpr 虚函数、try/catch、动态内存分配（new/delete） |
| **C++23** | constexpr 函数内可使用 static 和 thread_local 变量（需常量初始化） |

实际用法上，constexpr 计算可以直接喂给数组大小、模板参数这类必须编译期确定的位置：

```cpp
#include <cstddef>

constexpr size_t str_length(const char* str) {
    size_t len = 0;
    while (str[len] != '\0') {
        ++len;
    }
    return len;
}

constexpr size_t len = str_length("Hello, C++");  // 编译期得到 10

char buffer[str_length("Hello") + 1];  // 编译期确定大小
```

更典型的工程价值在查找表这类"编译期生成、运行时只读"的场景：

```cpp
#include <array>
#include <cstddef>

template <size_t N>
constexpr auto make_square_table() {
    std::array<int, N> table{};
    for (size_t i = 0; i < N; ++i) {
        table[i] = i * i;
    }
    return table;
}

constexpr auto squares = make_square_table<100>();

int main() {
    int result = squares[42];  // 直接读取常量 1764，零计算开销
}
```

复杂计算在编译期完成，运行时只剩查表——典型的"编译期换运行时"。

## if constexpr：编译期分支

C++17 的 `if constexpr` 把 SFINAE 那套 enable_if 手法压缩成了普通 if 的样子：

```cpp
template <typename T>
auto process(T value) {
    if constexpr (std::is_integral_v<T>) {
        return value * 2;
    } else if constexpr (std::is_floating_point_v<T>) {
        return value * 3.14;
    } else {
        return value;
    }
}
```

编译器根据模板参数在编译期选择分支，未选中的分支不会被实例化，也不进入最终代码——生成的代码里根本没有分支判断，这是真正的零成本分支。

## consteval：强制编译期执行

constexpr 只是"可以"在编译期执行：参数不是常量表达式时，函数照常在运行时跑。C++20 的 `consteval` 则强制函数只能在编译期执行：

```cpp
constexpr int square_constexpr(int n) {
    return n * n;
}

consteval int square_consteval(int n) {   // C++20
    return n * n;
}

int x = 5;
int c = square_constexpr(x);  // OK：运行时执行
int d = square_consteval(x);  // 编译错误：consteval 不能运行时调用
```

> constexpr 是"可以"编译期执行，consteval 是"必须"编译期执行。

consteval 适合配置校验、编译期生成哈希值和查找表这类必须坐实在编译期的场景。

## 分工：值归 constexpr，类型归模板

constexpr 更易用，但模板元编程并未退场，两者的分工是：

| 维度 | constexpr | 模板元编程 |
| ---- | ---- | ---- |
| 处理对象 | 值的计算与逻辑 | 类型的萃取、变换与约束 |
| 典型应用 | 编译期常量、查找表 | type_traits、CRTP 静态多态 |
| 可读性 | 接近普通代码 | 晦涩，concept 会改善 |

比如最简单的类型萃取：

```cpp
template <typename T>
using remove_const_ref_t = std::remove_const_t<std::remove_reference_t<T>>;
```

这种操作只作用于类型，constexpr 无能为力，模板是唯一工具。

## 代价在哪里

编译期计算不是免费的午餐，只是把账单换了一张：

- **编译时间**：模板递归实例化、constexpr 求值都在编译期做，重模板代码的编译时间是实打实的支出
- **错误信息**：模板报错动辄几百行，SFINAE 失败的诊断尤其难读（concept 正是在补这个短板）
- **可读性**：把循环写成递归实例化、把分支写成特化，代码逻辑和书写形态严重脱节
- **调试体验**：编译期发生的计算在运行时根本不存在，断点打不进去

所以准确的表述是：**用编译时间和代码可读性，换运行时速度和静态检查**。编译期计算能用，但要花在刀刃上，而不是到处滥用。

下一篇讲模板元编程中的类型萃取（type traits），以及 C++20 的 concept 如何让类型约束变得简单直接。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第四集
