# STL库的ranges

在C++ STL标准库的`<ranges>`（C++20中引入）中，定义了一套全面的关于**范围**的概念、类、模板、函数以及其他相关组件，旨在提高对元素序列的抽象化处理能力。主要包括以下几个方面：

1. **范围（Range）**：定义了一系列标准要求，规定了怎样的对象可被视为一个范围。
2. **视图（Views）**：提供了一系列轻量级、不可变且延迟计算的类模板及相关工具函数。
4. **范围友好算法（Range-Algorithms）**：对传统STL库的算法进行了升级和扩展，使其可以直接作用于范围对象，并能充分利用视图的特性，提高了算法的灵活性和效率。
5. **辅助工具**：一些工具函数，使得对范围的操作更为便捷。



## 范围（ranges）

范围（Range）是一个可以被迭代（遍历）的对象，它可以是标准容器（如vector、list）、原生数组、字符串或者任何能够提供迭代器接口的数据结构。在Ranges中，一个范围不仅仅包括元素序列，还定义了如何访问这些元素的规则。它指向一系列元素，从概念上看类似于一对begin与end迭代器。



### 范围概念

范围由概念（concept）定义。概念（concept）是C++语言的一个核心特性，它正式引入于C++20标准。与类定义不同，概念定义描述了一组行为特征，而不用关心具体的类型。这意味着只要一个对象具有期望的行为（如特定的成员变量或方法，或者让作为参数能让某段代码编译通过），就可以在代码中当作符合某种约定的对象来处理，而无需关心对象的确切类型。

引入范围概念，让处理序列数据的代码与承载序列数据的具体容器实现无关，两者**解耦**。这也是“鸭子类型”的编程范式。

> concept代表的编程范式也被称为鸭子类型（Duck Typing），这个概念源自一句俗语：“如果它走路像鸭子、叫声像鸭子，那么它就是鸭子。” 动态类型语言中广泛使用鸭子类型编程范式，例如Ruby、Python。而在静态类型语言C++中，通过引入Concept机制，也巧妙借鉴了这一灵活处理对象特性的方法论。



STL的`<ranges>`定义了`std::ranges::range`概念（concept），凡是符合`range`概念的对象都可以被当作范围对象。从代码定义上看，凡是能从中得到begin和end两个迭代器的对象都可以看作范围。如下代码所示：

**std::ranges::range代码定义**

```c++
template< class T >
concept range = requires( T& t ) {
  ranges::begin(t); // equality-preserving for forward iterators
  ranges::end  (t);
};
```



范围是个大范畴，除了`std::ranges::range`定义了基本的范围概念外，`<ranges>`命名空间里还定义了特殊的范围概念，形成一个类似于类继承的树形关系结构。根据支持迭代器的不同，一部分范围概念定义可以组成这样的树形结构。

```bash
range
|- view
|- common_range
|- sized_range
|- output_range
|- input_range
    |- forward_range
        |- bidirectional_range
            |- random_access_range
                |- contiguous_range
    
```

以`sized_range`为例，这个概念定义 “**符合range概念并可以作为参数执行size(x)**” 的东西均属于此概念。

```c++
    _EXPORT_STD template <class _Rng>
    concept sized_range = range<_Rng> && requires(_Rng& __r) { _RANGES size(__r); };
```



### 借用范围 borrowed range

借用范围是一种比较重要的概念，是指不会因为迭代而被消耗的数据序列，例如引用原始数据的视图或者引用类型的容器。借用范围生命周期结束后，其迭代器仍然有效。

概念`borrowed_range`判断一个类型是否为借用范围（borrowed range），定义如下：

```c++
template<class _Range>
concept borrowed_range = range<_Range> &&
(is_lvalue_reference_v<_Range> || enable_borrowed_range<remove_cvref_t<_Range>>);

// 由模板特化指定为true。
template <class>
inline constexpr bool enable_borrowed_range = false;

```

如果要创建一个符合`borrowed_range`概念的类，首先这个类型要满足`range`概念的要求，其次需要特化`enable_borrowed_range`以满足`enable_borrowed_range`的要求。





## 视图（views）

视图（views）是一种轻量级的范围，它不会存储元素，而是对其他范围进行变换、过滤等操作的结果。视图是惰性求值的，这意味着操作直到真正需要结果时才会执行，这有助于提升效率。视图能够对范围对象进行各种转换、筛选和聚合等运算，有以下特点：

1. 不拥有数据
   与数据的拥有权解耦，即视图处理数据但不拥有数据，因此不必管资源的申请和释放，同时也不会修改底层数据。

2. 不复制数据

   通常不需要在内存中分配新的数据结构，而是通过引用或转换现有的数据进行操作，这意味着运算中通常产生较少的的额外开销。

3. 惰性计算（Lazy Evaluation）
   惰性计算就是“按需计算”，即它们只在需要时才会执行。这意味着，当你创建一个视图时，不会立即对底层数据进行任何计算，只有在实际使用时才会触发计算。这种延迟计算的特性可以节省内存和计算资源，尤其是在处理大型数据集的场景中。

4. 函数式编程与链式风格
   视图本身符合范围概念的要求，因此一个视图可以作为另一个视图的输入，且基于视图的函数性、不可变性和无副作用性，这样就支持了函数式编程范式。辅以管道运算符“|”，可以实现漂亮的链式编程风格。



### 常用视图

关于视图相关的内容定义在`std::ranges::views`名字空间中，包含但不限于以下内容：

1. `filter`：创建一个仅包含符合特定条件的元素的视图。
2. `transform`：对每个元素应用给定的转换函数，并生成一个新的视图。
3. `take`：创建一个包含指定数量元素的视图。
4. `drop`：创建一个去除指定数量元素后的视图。
5. `split`：将范围分割成指定大小的子范围序列。
6. `reverse`：反转范围中的元素顺序。
7. `join`：将范围的范围中的子范围连接成单个范围。
8. `elements`：从范围中的元组中选择指定索引的元素，并将其表示为一个范围。



`std::views`是对`std::ranges::views`的简写，它是通过一个命名空间别名实现的，旨在简化代码的书写。

```c++
namespace views = ranges::views;
```



### 管道运算符

视图的使用最好配合管道运算符。管道运算符就是位或运算符`|`的重定义，用法就像Unix的管道命令，可以将视图像管道一样连接起来，实现类似于Java Stream API的流式数据处理管道。

下面是一个简单的例子：

```C++
#include <iostream>
#include <ranges>
#include <vector>

int main() {
    // 创建一个整数向量
    std::vector<int> numbers = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 };

    // 使用std::views::filter过滤出所有偶数，将其值增加一倍，再取前三个值。
    auto result_view = numbers
        | std::views::filter([](int i) { return i % 2 == 0; })
        | std::views::transform([](int i) { return i * 2; })
        | std::views::take(3);
    for (int number : result_view) {
        std::cout << number << ' ';
    }
    return 0;
}
```

注意`std::views::take(3)`意味着只取前三个结果，因为视图是惰性计算的，因此程序并不会处理numbers的所有元素。并且整个处理过程看不到中间变量，也没有构建用于存放中间结果的容器。此处可以看到视图的非常明显的价值：

- 节约内存和计算资源
- 代码风格清晰紧凑，可读性强
- 几乎没有副作用
- 产生bug的几率少



### 范围适配器

视图也被称为“范围适配器”（Range adapters），就像电源适配器（例如交流转直流，220V转110V）一样，它们是作用在范围之上的对其数据做转换的“适配器”，通过提供动态的、可组合的数据处理管道，使得C++程序员能够以声明式、函数式的方式处理数据，而无需关注底层实现细节，从而极大地增强了代码的表达力和效率。



## 范围友好算法

引入ranges之后，STL中的很多算法（原先algorithm模块中的函数）被改写并放到了`std::ranges`命名空间中（为了兼容性跟原先的std命名空间中的算法函数并存），这些新的算法接受一个range作为参数，而不是原来的begin和end两个参数，例如std::ranges::sort(range)。

以下是常用的一些范围友好算法：

- 条件判断
  - ranges::all_of
  - ranges::any_of
  - ranges::none_of
- 遍历处理
  - ranges::for_each & ranges::for_each_n
- 转换
  - ranges::transform
  - ranges::reverse
- 生成
  - ranges::fill
  - ranges::generate
  - ranges::iota
- 查找比较
  - ranges::count & ranges::count_if
  - ranges::find & ranges::find_if
  - ranges::starts_with & ranges::ends_with
  - ranges::contains
  - ranges::search
- 复制搬运
  - ranges::copy & ranges::copy_if
  - ranges::move
- 排序和半排序
  - ranges::is_sorted
  - ranges::sort & ranges::stable_sort
  - ranges::partial_sort & ranges::nth_element
- 分区 
  - ranges::is_partition & ranges::partition
- 二分查找
  - ranges::lower_bound & ranges::upper_bound
  - ranges::binary_search
- 集合运算 - 提供集合数据结构相关的操作
  - ranges::merge
  - ranges::include
  - ranges::set_difference & ranges::set_intersection & ranges::set_union 集合的求差集、交集、并集运算
- 堆运算 - 提供堆数据结构相关的操作
  - ranges::is_heap & ranges::make_heap
  - ranges::push_heap & ranges::pop_heap & ranges::sort_heap 入队、出堆与堆排序



## 心得体会

C++引入了概念concept，提供了更高层级的抽象，`<ranges>`是基于概念的，把抽象推广至广泛的场景。基于range的算法有更好的通用型。程序员使用自己专门设计的容器（可能是为了自己特定应用场景而做了特别的优化）与ranges互动，复用ranges提供的内容，减少自己的工作量。

`std::ranges::views`和管道运算符提供了一种现代化的、更加直观的方式来处理序列操作，使代码更简洁易读。



总之，使用`<ranges>`可以让代码更加现代化、简洁和高效，提高开发效率并减少错误的可能性。
