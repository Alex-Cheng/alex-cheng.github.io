# STL Library's ranges

In the `<ranges>` of the C++ STL standard library (introduced in C++20), a comprehensive set of concepts, classes, templates, functions, and other related components about **ranges** are defined, aiming to enhance the ability to abstract and process element sequences. It mainly includes the following aspects:

1. **Range**: Defines a set of standard requirements that specify what objects can be considered a range.
2. **Views**: Provides a series of lightweight, immutable, and lazily evaluated class templates and related tool functions.
4. **Range-friendly algorithms**: Upgrades and extends traditional STL library algorithms to directly operate on range objects, leveraging the characteristics of views to improve the flexibility and efficiency of the algorithms.
5. **Auxiliary tools**: Some tool functions to make operations on ranges more convenient.

## Ranges

A range is an object that can be iterated (traversed), and it can be a standard container (such as `vector` and `list`), a native array, a string, or any data structure that can provide an iterator interface. In Ranges, a range encompasses not only a sequence of elements but also defines the rules for accessing those elements. It refers to a series of elements and is conceptually similar to a pair of `begin` and `end` iterators.

### Range Concepts

Ranges are defined by concepts. Concepts are a core feature of the C++ language and were officially introduced in the C++20 standard. Unlike class definitions, concept definitions describe a set of behavioral characteristics without regard to specific types. This means that as long as an object exhibits the expected behavior (such as specific member variables or methods, or allowing a certain piece of code to compile), it can be treated as an object that conforms to a certain convention in the code without worrying about the exact type of the object.

The introduction of range concepts decouples the code that processes sequence data from the specific container implementation that carries the sequence data, allowing for greater flexibility and modularity in code design. This is also the programming paradigm of "duck typing."

> The programming paradigm represented by concepts is also known as duck typing, which takes its name from the saying: "If it walks like a duck and quacks like a duck, then it is a duck." Duck typing is widely used in dynamic typing languages such as Ruby and Python. In the static typing language C++, the introduction of the Concept mechanism also cleverly borrows this methodology of handling object features flexibly.

The STL's `<ranges>` defines the `std::ranges::range` concept, and any object that conforms to the `range` concept can be treated as a range object. From a code definition perspective, any object from which `begin` and `end` iterators can be obtained can be regarded as a range. As shown in the following code:

**Code Definition of std::ranges::range**

```c++
template< class T >
concept range = requires( T& t ) {
  ranges::begin(t); // equality-preserving for forward iterators
  ranges::end  (t);
};
```

Ranges are a broad category. In addition to defining the basic range concept with `std::ranges::range`, the `<ranges>` namespace also defines specific range concepts, forming a tree-like relationship structure similar to class inheritance. Depending on the supported iterators, some range concept definitions can form a tree structure like this.

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

Taking `sized_range` as an example, this concept defines anything that "conforms to the `range` concept and can be used as a parameter to execute `size(x)`" as belonging to this concept.

```c++
    _EXPORT_STD template <class _Rng>
    concept sized_range = range<_Rng> && requires(_Rng& __r) { _RANGES size(__r); };
```

### Borrowed Ranges

Borrowed ranges are an important concept that refers to a sequence of data that is not consumed due to iteration, such as views that reference the original data or containers of reference types. After the borrowed range's lifetime ends, its iterators remain valid.

The concept `borrowed_range` determines whether a type is a borrowed range, and is defined as follows:

```c++
template<class _Range>
concept borrowed_range = range<_Range> &&
(is_lvalue_reference_v<_Range> || enable_borrowed_range<remove_cvref_t<_Range>>);

// Specified as true by a template specialization.
template <class>
inline constexpr bool enable_borrowed_range = false;
```

If you want to create a class that conforms to the `borrowed_range` concept, first, the type must meet the requirements of the `range` concept, and second, you need to specialize `enable_borrowed_range` to meet the requirements of `enable_borrowed_range`.

## Views

Views are a type of lightweight range that does not store elements but instead performs operations such as transformation and filtering on other ranges. Views are lazily evaluated, meaning that operations are not performed until the actual results are needed, which helps improve efficiency. Views can perform various operations such as transformation, filtering, and aggregation on range objects, and have the following characteristics:

1. Do not own data
   Decoupled from the ownership of data, meaning that views process data but do not own it, eliminating the need to manage resources and ensuring that the underlying data is not modified.

2. Do not copy data
   Usually, there is no need to allocate a new data structure in memory, but rather to operate by referencing or transforming the existing data, resulting in less additional overhead during computations.

3. Lazy Evaluation
   Lazy evaluation means "compute on demand," meaning that when you create a view, no immediate calculations are performed on the underlying data, and only when it is actually used will the calculation be triggered. This lazy computing feature can save memory and computing resources, especially in scenarios dealing with large datasets.

4. Functional Programming and Chained Style
   Views themselves conform to the requirements of the range concept, so a view can be used as input for another view, and based on the functional, immutable, and side-effect-free nature of views, this supports the functional programming paradigm. Combined with the pipe operator "|", it enables a beautiful chained programming style.

### Common Views

The content related to views is defined in the `std::ranges::views` namespace and includes, but is not limited to, the following:

1. `filter`: Creates a view that contains only elements that meet a specific condition.
2. `transform`: Applies a given transformation function to each element and generates a new view.
3. `take`: Creates a view that contains a specified number of elements.
4. `drop`: Creates a view that removes a specified number of elements from the beginning or end.
5. `split`: Splits the range into a sequence of subranges of a specified size.
6. `reverse`: Reverses the order of elements in the range.
7. `join`: Joins the subranges in the range into a single range.
8. `elements`: Selects elements from the tuples in the range at the specified indices and represents them as a range.

`std::views` is a shorthand for `std::ranges::views`, which is implemented through a namespace alias, aiming to simplify code writing.

```c++
namespace views = ranges::views;
```

### Pipe Operator

The best use of views is with the pipe operator. The pipe operator is a redefinition of the bitwise OR operator `|`, and its usage is similar to the Unix pipe command, allowing views to be connected like pipes to implement a streaming data processing pipeline similar to the Java Stream API.

Here is a simple example:

```C++
#include <iostream>
#include <ranges>
#include <vector>

int main() {
    // Create an integer vector
    std::vector<int> numbers = { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12 };

    // Use std::views::filter to filter out all even numbers, double their values, and take the first three.
    auto result_view = numbers
        | std::views::filter([](int i) { return i % 2 == 0; })
        | std::views::transform([](int i) { return i * 2; })
        | std::views::take(3);
    for (int number : result_view) {
        std::cout << number << ';
    }
    return 0;
}
```

Note that `std::views::take(3)` means only taking the first three results, as views are lazily evaluated, the program does not process all the elements of `numbers`. And throughout the processing, there are no intermediate variables and no containers are constructed to hold the intermediate results. Here, the clear value of views can be seen:

- Save memory and computing resources
- Compact and readable code style
- Minimal side effects
- Reduced chance of bugs

### Range Adapters

Views are also known as "range adapters," just like power adapters (such as AC to DC, 220V to 110V), they are "adapters" that transform the data on top of the range, by providing a dynamic and composable data processing pipeline, allowing C++ programmers to handle data in a declarative and functional way without worrying about the underlying implementation details, thereby greatly enhancing the expressiveness and efficiency of the code.

## Range-friendly Algorithms

After the introduction of ranges, many algorithms in the STL (the functions in the original `algorithm` module) have been rewritten and placed in the `std::ranges` namespace (to coexist with the original algorithm functions in the `std` namespace for compatibility), these new algorithms accept a range as a parameter instead of the original two parameters `begin` and `end`, such as `std::ranges::sort(range)`.

Here are some commonly used range-friendly algorithms:

- Conditional judgment
  - `ranges::all_of`
  - `ranges::any_of`
  - `ranges::none_of`
- Traversal processing
  - `ranges::for_each` & `ranges::for_each_n`
- Conversion
  - `ranges::transform`
  - `ranges::reverse`
- Generation
  - `ranges::fill`
  - `ranges::generate`
  - `ranges::iota`
- Search and comparison
  - `ranges::count` & `ranges::count_if`
  - `ranges::find` & `ranges::find_if`
  - `ranges::starts_with` & `ranges::ends_with`
  - `ranges::contains`
  - `ranges::search`
- Copy and move
  - `ranges::copy` & `ranges::copy_if`
  - `ranges::move`
- Sorting and semi-sorting
  - `ranges::is_sorted`
  - `ranges::sort` & `ranges::stable_sort`
  - `ranges::partial_sort` & `ranges::nth_element`
- Partitioning
  - `ranges::is_partition` & `ranges::partition`
- Binary search
  - `ranges::lower_bound` & `ranges::upper_bound`
  - `ranges::binary_search`
- Set operations - Provide operations related to set data structures
  - `ranges::merge`
  - `ranges::include`
  - `ranges::set_difference` & `ranges::set_intersection` & `ranges::set_union` Set difference, intersection, and union operations
- Heap operations - Provide operations related to heap data structures
  - `ranges::is_heap` & `ranges::make_heap`
  - `ranges::push_heap` & `ranges::pop_heap` & `ranges::sort_heap` Enqueue, dequeue, and heap sort operations

## Experience and Insights

C++ introduces the concept of concepts, providing a higher-level abstraction. `<ranges>` is based on concepts, extending the abstraction to a wide range of scenarios. Algorithms based on ranges have better通用性. Programmers can interact with ranges using their specially designed containers (possibly optimized for specific application scenarios) and reuse the content provided by ranges, reducing their own workload.

`std::ranges::views` and the pipe operator provide a modern and more intuitive way to handle sequence operations, making the code more concise and readable.

In conclusion, using `<ranges>` can make the code more modern,concise, and efficient, improving development efficiency and reducing the possibility of errors.
