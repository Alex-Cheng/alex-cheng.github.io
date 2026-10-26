# C++20 Ranges：用管道思维打开编程新模式

先看一个任务：给定一批整数，过滤出偶数、求平方、取前 3 个、倒序输出。用传统 STL 写法，这是四段循环加四个临时容器；用 C++20 Ranges，这是一条管道。本文讲清 Ranges 是什么、它背后的管道模式从哪来、能带来什么，以及代价在哪里。

## 一条管道代替四段循环

传统写法的痛点是典型的。为了完成"过滤 → 变换 → 截取 → 倒序"，我们要手写中间容器、手动管边界、逐段搬运数据：

```cpp
std::vector<int> data{1, 3, 2, 8, 7, 4, 6, 5};

std::vector<int> temp_even;
temp_even.reserve(data.size());
// Step 1: 过滤偶数
for (auto it = data.begin(); it != data.end(); ++it) {
    if (*it % 2 == 0) temp_even.push_back(*it);
}

std::vector<int> temp_squared;
temp_squared.reserve(temp_even.size());
// Step 2: 求平方
for (auto it = temp_even.begin(); it != temp_even.end(); ++it) {
    temp_squared.push_back((*it) * (*it));
}

// Step 3: 取前 3 个（手动检查边界）
std::vector<int> temp_first_three;
for (std::size_t i = 0; i < std::min(temp_squared.size(), std::size_t{3}); ++i)
    temp_first_three.push_back(temp_squared[i]);

// Step 4: 倒序
std::vector<int> result;
for (int i = static_cast<int>(temp_first_three.size()) - 1; i >= 0; --i)
    result.push_back(temp_first_three[i]);

for (int x : result) std::cout << x << " ";  // 输出: 16 64 4
```

同样的逻辑，C++20 用 Ranges 一气呵成：

```cpp
std::vector<int> data{1, 3, 2, 8, 7, 4, 6, 5};
auto result = data
    | std::views::filter([](int x) { return x % 2 == 0; })  // 过滤偶数
    | std::views::transform([](int x) { return x * x; })    // 求平方
    | std::views::take(3)                                   // 取前 3 个
    | std::views::reverse;                                  // 倒序
for (int x : result)
    std::cout << x << " ";  // 输出: 16 64 4
```

两种写法的差异不只是行数：

| | 传统 STL 写法 | Ranges 管道 |
| ---- | ---- | ---- |
| 中间容器 | 每个步骤一个 | 无 |
| 遍历次数 | 每个阶段各一次 | 整条管道一次 |
| 内存分配与拷贝 | 频繁 | 零额外 |
| 代码形态 | 指令式，循环和条件散落 | 声明式，一行管道 |
| 阅读焦点 | 怎么实现 | 想做什么 |

## Ranges 的核心组件

C++20 Ranges 把函数式编程中的管道模式引入标准库，核心组件有四块。

**range 概念。** `std::ranges::range` 约束一个类型提供 `begin` 迭代器和 `end` 哨兵。所有标准容器天然满足。这是一种"鸭子类型"式的约束：不看你继承自什么，只看你的行为——走起来像鸭子、叫起来像鸭子，就是鸭子。

**view 概念。** `view` 约束一个 range 的拷贝、移动、赋值都是 O(1)。这解释了为什么 `std::vector` 不是 view（拷贝是 O(n)），而 `std::string_view` 是（只复制指针和长度）。大多数标准 view 还有两个特征：惰性求值——遍历时才计算，之前只是声明；不拥有数据——只是对源的观察，源销毁则 view 失效。

> View 就是数据上的一副"眼镜"：你不移动数据，只是换镜片去看同一个数据集，看到的形状不同，数据本身不变。

**适配器与工厂。** 范围适配器（range adaptor）是函数对象，通过 `|` 与 range 组合后产生视图：

```cpp
std::vector<int> v{1, 2, 3, 4, 5, 6};
auto result = v | std::views::filter([](int x) { return x % 2 == 0; })
                | std::views::transform([](int x) { return x * x; });
```

适配器链上所有操作都是惰性的——遍历 `result` 时，数据才依次流经 `filter` → `transform`。这像电源适配器：把 220V 变成 5V（做变换），不改变发电站的电（不动源数据），不接电器就没有电流（惰性）。工厂则不需要输入，自己"无中生有"，如 `std::views::iota(1)` 生成 1, 2, 3, ... 的等差序列。常用的一些：

| 类型 | 名称 | 功能 |
| ---- | ---- | ---- |
| 适配器 | `views::filter` | 过滤元素 |
| 适配器 | `views::transform` | 映射变换 |
| 适配器 | `views::take` / `views::drop` | 取前 / 跳过前 N 个 |
| 适配器 | `views::reverse` | 反转 |
| 适配器 | `views::split` / `views::join` | 拆分 / 合并 |
| 工厂 | `views::iota` | 生成等差序列 |
| 工厂 | `views::single` | 单元素视图 |

**Range 版算法与投影。** 所有 STL 算法都有 ranges 版本，直接接受 range，不用再传 `begin()`/`end()` 对；并且统一附带一个投影（projection）参数，把"取什么字段"和"怎么比较"解耦：

```cpp
// 传统写法：手写 lambda 比较 age
std::sort(people.begin(), people.end(),
    [](const Person& a, const Person& b) { return a.age < b.age; });

// Ranges + Projection：第二个参数是默认比较器，第三个是投影
std::ranges::sort(people, {}, &Person::age);
```

## 管道模式：跨语言的共同选择

Ranges 背后的设计思想是管道模式：把数据处理流程拆成一组独立的、可组合的阶段，数据依次流过，每个阶段只做单一变换。它不是 C++ 独创，而是函数式编程中函数组合（function composition）与不可变数据流思想在数据处理领域的落地——`| filter | transform` 本质上就是 `f(g(x))` 的泛化。

几乎所有主流语言都能找到它的影子：

| 语言 | 实现形式 | 示例 |
| ---- | ---- | ---- |
| C++20 | Ranges | `v \| std::views::filter(f) \| std::views::transform(g)` |
| Java | Stream API | `stream.filter(f).map(g).collect(toList())` |
| C# | LINQ | `list.Where(f).Select(g).ToList()` |
| Rust | Iterator combinators | `iter.filter(f).map(g).collect()` |
| Python | 生成器表达式 | `(x*x for x in data if x%2==0)` |
| Elixir | `|>` 管道操作符 | `data \|> f() \|> g()` |
| Unix Shell | 命令行管道 | `cat file \| grep "err" \| wc -l` |

一个完整的管道由四要素构成：数据源（source）、连接各阶段的 `|`、做单一变换的阶段（stage）、消费结果的汇（sink）。C++ Ranges 对这四要素都有对应物。

## 惰性求值与零拷贝：性能从哪来

Ranges 的性能优势不来自算法更快，而来自两个架构级特征。

一是视图组合不产生中间容器。管道每一步只是产出一个轻量 view 对象，不分配、不拷贝。这与惰性求值是两回事：前者管"怎么存"（view 本身不存数据），后者管"何时算"（遍历时才执行）。两者的对比：

| | 即时求值（传统容器方式） | 惰性求值（views） |
| ---- | ---- | ---- |
| 计算时机 | 每步立即执行，结果立刻物化 | 遍历时才逐元素计算 |
| 中间结果 | 每步产出完整容器 | 只描述"怎么算"，不存数据 |
| 未被消费时 | 开销已经付出 | 零开销 |

二是单次遍历。传统方式每个阶段独立扫一遍数据；Ranges 管道中所有阶段按元素粒度交织执行，每个元素一次走完整条管道：取出 → 判断过滤 → 变换 → 计数 → 送出或跳过。

在实测中（一千万个 double 上执行 `filter → transform → take`）：

| 指标 | 传统写法 | Ranges 管道 |
| ---- | ---- | ---- |
| 耗时 | 603 ms | 55 ms |
| 中间容器 | 3 个 | 0 个 |
| 遍历次数 | 3 次 | 1 次 |
| 加速比 | — | 11.0× |

数据量越大，零拷贝的优势越明显。编译期内联展开保证这些抽象不在运行时留下痕迹——典型的 C++ 零成本抽象。C++23 的 `std::ranges::to` 则打通最后一公里，把视图物化回容器只需一行：

```cpp
auto v = data | std::views::filter(pred)
              | std::views::transform(f)
              | std::ranges::to<std::vector<int>>();
```

## 代价在哪里

Ranges 不是免费午餐，几个坑必须清楚。

**悬垂引用。** view 不拥有数据，源 range 销毁后 view 立即悬垂，再遍历就是未定义行为：

```cpp
auto dangerous() {
    std::vector<int> v{1, 2, 3, 4, 5};
    return v | std::views::filter([](int x) { return x % 2 == 0; });
    // 危险！v 随函数返回被析构，返回的 view 悬垂
}
```

需要把结果传出作用域时，先用 `std::ranges::to<T>()` 物化到容器。

**const 语义陷阱。** 某些视图（如 `filter_view`）的 `begin()` 需要修改内部缓存以满足均摊 O(1)，对视图加 `const` 后可能直接编译失败。需要只读语义时，对源数据加 `const`，而不是对视图。

**一次性输入。** 基于 input iterator 的视图（如 `std::views::istream<int>(std::cin)`）只能遍历一次，消费完就空了。需要多次遍历，同样先物化到容器。

**编译与调试体验。** 管道每一段都是模板实例化，深层管道会拉长编译时间；报错信息动辄几百行，出问题时调试器里的调用栈也不如手写循环直观。

所以准确的评价是：Ranges 把"怎么处理数据"的复杂度交给了类型系统和编译器，换来声明式的表达力，但内存所有权、求值时机、编译成本这些事情，仍然要靠你自己想清楚。

## 一句话总结

C++20 Ranges 带来的不只是一套新 API，而是一种思维方式的转变：从"怎么做"到"做什么"，从容器思维到 view 思维，从立即计算到惰性求值。

> Ranges 让你用数据流代替控制流，用意图代替步骤。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第六集
