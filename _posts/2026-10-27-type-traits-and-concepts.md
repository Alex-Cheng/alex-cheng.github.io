# 类型萃取与 Concept：在编译期掌控类型

上一集聊了零成本抽象的哲学，这一集落到具体的语言机制上。模板写多了必然遇到两类问题：一是"看不见"——不知道传进来的 T 到底能干什么；二是"改不动"——想从 `const T&` 里取出裸类型 T，只能靠晦涩的模板技巧。类型萃取（type_traits）和 Concept 就是 C++ 给出的答案：前者让你在编译期检测和变换类型，后者让你给模板参数立规矩。两者都在编译期完成，运行时零开销。

## 为什么需要在编译期"看见"类型

模板实例化需要类型的信息：分配内存要知道大小和对齐，容器要知道元素能不能安全地按位拷贝。更深一层的需求是**约束**——一个只接受算术类型的模板，如果传进来一个 `std::string`，最好在编译期就报错，而不是拖到运行时，更不要吐出几百行模板展开的噪音。

还有**分派**：根据类型特征生成不同的专用代码。典型例子是标准库的 `std::copy`——如果元素类型可以直接 memcpy，就走内存拷贝；否则逐元素调用拷贝构造。这是编译期决策，运行时没有任何判断。

> 核心问题是：如何在编译期检测一个类型的特征——它是不是整数、能不能按位拷贝、是不是某个类的派生类？

除了"检测"，还有"变换"：把 `T`、`T&`、`const T&` 统一修整成裸类型 T，从函数类型提取返回类型，基于 T 构造指针或数组。检测、查询、变换，这就是类型萃取的三件事。

## type_traits：标准库的工具箱

C++11 在 `<type_traits>` 头文件中提供了整套工具。常用的包括：

| 萃取 | 含义 | 示例 |
| ---- | ---- | ---- |
| `std::is_integral<T>` | T 是否整型 | `is_integral<int>` → true |
| `std::is_pointer<T>` | T 是否指针 | `is_pointer<int*>` → true |
| `std::is_same<T, U>` | T 与 U 是否相同 | `is_same<int, int>` → true |
| `std::remove_const<T>` | 去掉 const | `remove_const<const int>` → int |
| `std::remove_reference<T>` | 去掉引用 | `remove_reference<int&>` → int |
| `std::remove_cvref<T>` | 同时去掉 cv 限定与引用 | `remove_cvref<const int&>` → int |
| `std::add_pointer<T>` | 加上指针 | `add_pointer<int>` → int* |

这些工具都是模板：类模板形式的 `std::is_integral<T>::value` 是 C++11 的原始形态，C++14 起变量模板让写法简化成 `std::is_integral_v<T>`；`remove_cvref` 则是 C++20 才补上的。

最常用的场景是配合 `if constexpr`（C++17）在模板里走不同的编译期分支：

```cpp
#include <type_traits>
#include <iostream>

template <typename T>
void process(T value) {
    if constexpr (std::is_integral_v<T>) {
        std::cout << "按照整数处理\n";
    } else if constexpr (std::is_floating_point_v<T>) {
        std::cout << "按照浮点数处理\n";
    } else {
        std::cout << "按照其他类型处理\n";
    }
}

int main() {
    process(10);    // 按照整数处理
    process(3.14);  // 按照浮点数处理
}
```

编译出的代码里根本没有这个 `if`——每个实例化只保留命中的分支。

这些萃取的实现原理并不神秘：模板偏特化加 SFINAE。以 `is_integral` 为例，主模板继承 `std::false_type`，再对每个整数类型做特化继承 `std::true_type`：

```cpp
template <typename T>
struct is_integral : std::false_type {};
template <> struct is_integral<int> : std::true_type {};
// ... 其余整数类型同理

static_assert(is_integral<int>::value);
```

早期标准库就是这么实现的。后来为了编译性能，主流实现换成了编译器内建指令（intrinsic，如 `__is_integral`），省掉模板实例化的开销。我们自己写萃取，走偏特化这条路就够了。

## SFINAE 之痛，Concept 登场

有了萃取，就可以用它约束模板。但在 Concept 出现之前，约束的写法是 SFINAE 风格的 `enable_if`：

```cpp
template <typename T>
std::enable_if_t<std::is_arithmetic_v<T>, void>
process(T value) { /* ... */ }
```

问题很明显。其一，返回类型本来是干干净净的 `void`，现在被塞进一段机械暗语；其二，约束不满足时，编译器报出的不是"类型不符合要求"，而是找不到匹配的重载、附带一长串模板展开——约束失败的原因完全被噪音淹没。

C++20 的 Concept 解决了这两个问题：

> Concept 是一种命名了的编译期谓词，用来声明模板参数必须满足的条件。

| | SFINAE + `enable_if` | Concept（C++20） |
| ---- | ---- | ---- |
| 约束写法 | 嵌入返回类型，晦涩 | 声明在模板参数或 `requires` 子句，直观 |
| 错误信息 | 模板展开噪音，找不到根因 | 直接指出哪个约束未满足 |
| 可读性 | 约束藏在实现里 | 约束即文档 |
| 分派能力 | 靠重载解析的间接技巧 | 蕴含关系直接决定更优匹配 |

标准库在 `<concepts>` 头文件中提供了大量现成 Concept（`std::integral`、`std::floating_point`、`std::same_as` 等），使用方式有三种：

```cpp
// 语法 1：直接约束模板参数（最简洁，通常够用）
template <std::integral T>
T double_value(T x) { return x * 2; }

// 语法 2：requires 子句
template <typename T>
    requires std::integral<T>
T double_value(T x) { return x * 2; }

// 语法 3：尾部 requires
template <typename T>
T triple(T x) requires std::integral<T> { return x * 3; }
```

标准库覆盖不到的需求可以自定义。简单场景直接组合 type traits：

```cpp
template <typename T>
concept Numeric = std::is_integral_v<T> || std::is_floating_point_v<T>;
```

复杂场景用 `requires` 表达式，内部列出对类型的操作要求，全部满足才算通过：

```cpp
template <typename T>
concept Regular = requires(T a, T b) {
    T{a};    // 可拷贝构造
    a = b;   // 可拷贝赋值
    a == b;  // 可相等比较
    a != b;  // 可不等比较
};
```

## 实战：按能力选择算法，与 Subsumption

Concept 最出彩的地方是重载分派。有些容器只支持向前遍历，有些支持随机访问，可以用两个约束不同的重载让编译器自动选最优实现：

```cpp
#include <concepts>
#include <iostream>
#include <list>
#include <vector>

template <std::forward_iterator Iter>
void sort(Iter first, Iter last) {
    std::cout << "forward_iterator sort (insertion/merge)\n";
}

template <std::random_access_iterator Iter>
void sort(Iter first, Iter last) {
    std::cout << "random_access sort (quick/heap)\n";
}

int main() {
    std::list<int> l = {3, 1, 2};
    std::vector<int> v = {3, 1, 2};

    sort(l.begin(), l.end());  // forward_iterator 版本
    sort(v.begin(), v.end());  // random_access_iterator 版本
}
```

`std::random_access_iterator` 的定义中蕴含了 `std::forward_iterator`，这叫 **subsumption（蕴含关系）**：当多个重载都匹配时，编译器选约束更严格的那个。`std::list` 的迭代器只满足前者，`std::vector` 的两个都满足，于是选中更严格的 random access 版本。这同样适用于手写的约束组合——`std::signed_integral` 蕴含于 `std::integral`，`process(42)` 会优先匹配 `signed_integral` 版本，`process(42u)` 则落到 `integral` 版本。

一套接口，多种实现，纯编译期决策——这就是上一集说的静态多态，只是这次的分派规则写成了显式的约束。

## 边界在哪里

Concept 值得用，但别把它当成 SFINAE 的万能替身：

- **覆盖不了所有 SFINAE 场景。** Concept 约束的是"类型满足什么条件"，但有些老代码依赖 SFINAE 做更迂回的事——比如检测某个成员函数是否存在并据此修改返回类型，或者在重载决议中利用替换失败的细节。这些能迁移的应该迁移，迁不了的 `enable_if` 依然合法有效。
- **约束检查发生在编译期，重约束有编译成本。** `requires` 表达式会真实地做语义检查，嵌套很深的 Concept 组合会让编译时间和模板展开一样膨胀，错误信息虽然好了，但可能好得"很长"。
- **约束过强是常见误用。** 把 Concept 写成 `requires(T a) { a.foo(1); a.foo(2); a.foo(3); }` 这种枚举式检查，等于把类型焊死在自己的假设上；合理的 Concept 应该描述语义需求（可比较、可拷贝、可交换），而不是罗列用法。
- **它不改变运行时。** Concept 只影响编译期的选择和诊断，不会让编译器替你优化算法本身——`std::list` 上的 sort 该是 O(n log n) 归并还是 O(n²) 插入，取决于你写了什么。

一句话收尾：

> 类型萃取在编译期获取和变换类型特征，Concept 在编译期约束模板参数。两者合起来，让 C++ 在编译期就完成类型的检测、变换与分派——不花运行期的一个字节、一个时钟周期。

这正是零开销抽象哲学的实践。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第五集
