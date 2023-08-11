

# 一种高效且节约内存的聚合数据结构的实现

在特定的场景中，特殊定制数据结构能够得到更加好的性能且更节约内存。



## 聚合函数GroupArray的问题

GroupArray聚合函数是将分组内容组成一个个数组，例如下面的例子：

```sql
SELECT groupArray(concat('ABC-', toString(number))) from numbers(20) group by number % 5;
------------------------------------------------------
Output:
------------------------------------------------------
['ABC-0','ABC-5','ABC-10','ABC-15']
['ABC-1','ABC-6','ABC-11','ABC-16']
['ABC-2','ABC-7','ABC-12','ABC-17']
['ABC-3','ABC-8','ABC-13','ABC-18']
['ABC-4','ABC-9','ABC-14','ABC-19']
```

原始的实现中使用顺序表存放每个字符串，每个字符串由size和data两部分组成，如以下简化代码所示：

```c++

// 内存排布：
// [8 字节]size, [不定字节数]data...
// 例如字符串"ABC"的表示如下：
// 0x0000000000000003, 'A', 'B', 'C'
struct StringNode
{
    size_t size;
    // 实例尾部存放实际数据。
};
using AggregateData = PODArray<StringNode*>
```

在聚合过程中，不断创建StringNode实例并将其指针放入表示聚合数据的`AggregateData`实例中。这个实现方法会存在几个问题：

1. 在聚合过程中，由`AggregateData`表示的聚合数据不断增长，会引发多次因PODArray的内存空间不够而引发的重新申请内存的动作，还会附加复制数据到新内存空间操作的消耗。
2. PODArray的初始大小也很难确定：初始大小如果过大，浪费空间；初始大小如果过小，重新申请新的内存空间后，原先的初始的内存就浪费了，且新的内存空间可能又过大了。举个例子，如果`AggregateData`初始大小是32字节，实际聚合数据有48字节，需要重新分配内存空间，重新分配的内存是64字节，这样浪费的内存是：原来的32字节+新空间装完48字节的数据之后空余的16字节，总共浪费了48个字节。
3. `StringNode`的size字段并不需要8个字节，因为我们知道在我们的实际使用场景中，字符串最大不会超过65535，用2个字节表示长度就够了，浪费了6个字节。



## 用链表替代顺序表的解决方案

用链表替代顺序表，似乎第一感觉是不可行的，因为两个根深蒂固（可能来自于教科书）的观点：

1. 链表的内存分散，局部性不好；
2. 链表每新增一个节点都需要分配内存，内存分配动作过多影响效率；
3. 链表访问较慢，需要通过next指针找下一个。

在使用Arena的内存分配器和当前GroupArray的聚合数据结构的前提条件，以上两个观点都不是绝对正确的。

先说第一个问题，在一般内存分配器中，可能每次分配的内存都是不连续的，这是链表的内存分散的原因。但是Arena内存分配器在不切换内存块的前提下分配的内存是连续的。每个聚合线程有独立的Arena内存分配器。因此这种情况下链表的内存是基本连续的，保证了相对的局部性。

第二个问题也是跟Arena内存分配器相关。Arena内存分配器是一次调用系统接口（jemalloc或者mmap或者其他）分配一大块内存，然后每次调用Arena内存分配器分配内存时只要返回当前指向内存块中空余内存的指针的值，然后更新这个指针的值使其指向剩下的空余内存的开头即可。这是一个非常轻量的函数调用而且极有可能被内联了。

第三个问题，聚合数据是`StringNode`的指针的数组，虽然PODArray是顺序表但是每次访问也是要通过指针才能访问到`StringNode`实例的，这样跟链表中通过next指针访问的代价是一样的。但我们此时能够直接访问真实数据了，不需要再次通过链表节点的指针去访问真实数据，这样指针取值操作的次数是不变的。



综上所述，链表替代顺序表在这个特定场景下是更好的方案。



## 节约6个字节

原先的`size_t size`需要8个字节，但实际两个字节就够了。虽然只是6个字节，但是在数据的行数很大的情况下总共节约下来的内存是很客观的。例如对于十亿条数据，就会节约8GiB左右（8 x 10亿）的内存。

实现方式如下：

```c++
struct StringNode
{
	UInt16 size;
    char data[6];
}

// string_size是字符串的实际大小。sizeof(StringNode::data)等于6。
arena.alignedAlloc(std::max(sizeof(Node), sizeof(Node) - sizeof(StringNode::data) + string_size), alignof(Node));
```

通过把size改成UInt16并加入一个6个字节的data字段，省出6个字节出来。



## 根据需要定义count字段

教科书上的链表不需要count字段，因为可以通过遍历next指针获得。但是实际上我们可能需要快速获取一个链表的节点个数，但也有可能不需要。

通过模板参数，来控制是否需要count字段。在不需要获取节点数量（例如本例中的GroupArray聚合函数）的场景下，就可以省下count字段的8个字节。积少成多。



```c++
struct EmptyState{};

template <bool is_empty, typename T>
using TypeOrEmpty = std::conditional_t<is_empty, EmptyState, T>;

template <...,
		bool require_count,
		...
        >
struct ...
{
    ... ...
    [[no_unique_address]] TypeOrEmpty<!require_count, UInt64> node_count {};
    ... ...
};


```

当模板参数`require_count`等于false的时候, `node_count`不占空间。



## 具体实现

### 代码结构

实现由以下几个模板类组成：

1. struct ArenaLinkedNodeList
   表示整一个链表数据结构。
2. concept UnfixedSized
   判定数据类型是否为变长的，规定凡是有char * data和size_t size的就是变长数据类型。
3. struct ArenaMemoryNodeBase
   表示链表中的一个节点的数据结构基类。派生类使用CRTP模式继承此基类。
4. struct ArenaMemoryUnfixedSizedNode
   表示变长数据的链表节点，通常是字符串、数组。
5. struct ArenaMemoryFixedSizedNode
   表示固定长度数据的链表节点，通常是数值、日期。



### 具体代码

以下是具体代码。

```c++
struct EmptyState { };  // 表示空类型。

template <bool use_type, typename T>
using MaybeEmptyState = std::conditional_t<use_type, T, EmptyState>; // 可能是空类型，也可能是T，由use_type控制。

template <typename T>
concept UnfixedSized = requires(T v)
{
    {v.size} -> std::convertible_to<size_t>;
    {v.data} -> std::convertible_to<const char *>;
};

template <typename T>
concept FixedSized = !UnfixedSized<T>;

template <typename Derived, typename ValueType>
struct ArenaMemoryNodeBase
{
    Derived * next;
    
    Derived * asDerived()
    {
        return static_cast<Derived*>(this);
    }

    const Derived * asDerived() const
    {
        return static_cast<const Derived*>(this);
    }

    template <bool is_plain_column>
    ALWAYS_INLINE static Derived * allocate(const IColumn & column, size_t row_num, Arena & arena)
    {
        return Derived::allocate(Derived::template getValueFromColumn<is_plain_column>(column, row_num, arena), arena);
    }

    ALWAYS_INLINE Derived * clone(Arena & arena) const
    {
        size_t copy_size = Derived::realMemorySizeOfNode(static_cast<const Derived &>(*this));
        Derived * new_node = reinterpret_cast<Derived*>(arena.alignedAlloc(copy_size, alignof(Derived)));
        memcpy(new_node, this, copy_size);
        new_node->next = nullptr;
        return new_node;
    }

    ALWAYS_INLINE ValueType value() const
    {
        return Derived::getValueFromNode(static_cast<const Derived&>(*this));
    }

    ALWAYS_INLINE void serialize(WriteBuffer & buf) const
    {
        writeBinary(value(), buf);
    }
};


template <UnfixedSized ValueType>
struct ArenaMemoryUnfixedSizedNode : ArenaMemoryNodeBase<ArenaMemoryUnfixedSizedNode<ValueType>, ValueType>
{
    using Derived = ArenaMemoryUnfixedSizedNode<ValueType>;
    static constexpr UInt16 unfixed_sized_len_limit = -1;

    UInt16 size;
    char data[6];

    template <bool is_plain_column>
    ALWAYS_INLINE static ValueType getValueFromColumn(const IColumn & column, size_t row_num, Arena & arena)
    {
        if (is_plain_column)
        {
            const char * begin{};
            auto serialized = column.serializeValueIntoArena(row_num, arena, begin);
            return allocate(arena, {serialized.data, serialized.size});
        }
        else
        {
            return allocate(arena, column.getDataAt(row_num));
        }
    }

    ALWAYS_INLINE static ValueType getValueFromNode(const Derived & node)
    {
        return {node.data, node.size};
    }

    ALWAYS_INLINE static Derived * allocate(ValueType value, Arena & arena)
    {
        if (value.size > unfixed_sized_len_limit)
        {
            throw Exception();
        }
        Derived * node = reinterpret_cast<Derived*>(arena.alignedAlloc(Derived::realUnfixedSizedDataMemorySizeForPayload(value.size), alignof(Derived)));
        node->next = nullptr;
        node->size = value.size;
        memcpy(node->data, value.data, value.size);
        return node;
    }

    ALWAYS_INLINE static size_t realMemorySizeOfNode(const Derived & node)
    {
        return realUnfixedSizedDataMemorySizeForPayload(node.size);
    }

    ALWAYS_INLINE static size_t realUnfixedSizedDataMemorySizeForPayload(size_t payload_size)
    {
        return std::max(sizeof(Derived), sizeof(Derived) + payload_size - sizeof(Derived::data));
    }

    ALWAYS_INLINE static Derived * deserialize(ReadBuffer & buf, Arena & arena)
    {
        // Treat all unfixed sized data as String and StringRef.
        String data;
        readBinary(data, buf);
        return allocate(arena, StringRef(data));
    }

};

template <FixedSized ValueType>
struct ArenaMemoryFixedSizedNode : ArenaMemoryNodeBase<ArenaMemoryFixedSizedNode<ValueType>, ValueType>
{
    using Derived = ArenaMemoryFixedSizedNode<ValueType>;

    ValueType data;

    template <bool is_plain_column>
    ALWAYS_INLINE static ValueType getValueFromColumn(const IColumn & column, size_t row_num, Arena & arena)
    {
        static_assert(!is_plain_column);
        return allocate(arena, assert_cast<const ColumnVector<ValueType>&>(column).getData()[row_num]);
    }

    ALWAYS_INLINE static ValueType getValueFromNode(const Derived & node)
    {
        return node.data;
    }

    ALWAYS_INLINE static Derived * allocate(ValueType value, Arena & arena)
    {
        Derived * node = reinterpret_cast<Derived*>(arena.alignedAlloc(sizeof(Derived), alignof(Derived)));
        node->next = nullptr;
        node->data = value;
        return node;
    }

    ALWAYS_INLINE size_t realMemorySizeOfNode() const
    {
        return sizeof(Derived);
    }

    ALWAYS_INLINE static Derived * deserialize(ReadBuffer & buf, Arena & arena)
    {
        Derived * new_node = reinterpret_cast<Derived*>(arena.alignedAlloc(sizeof(Derived), alignof(Derived)));
        new_node->next = nullptr;
        readBinary(new_node->data, buf);
        return new_node;
    }
};

template <typename ValueType, bool has_count_field = false>
struct ArenaLinkedList
{
    template <typename T>
    struct NodeTraits
    {
        using NodeType = ArenaMemoryFixedSizedNode<T>;
    };

    template <UnfixedSized T>
    struct NodeTraits<T>
    {
        using NodeType = ArenaMemoryUnfixedSizedNode<T>;
    };

    using Node = typename NodeTraits<ValueType>::NodeType;

    Node * head{};
    Node * tail{};

    [[no_unique_address]] std::conditional_t<has_count_field, size_t, EmptyState> count{};

    struct Iterator
    {
        using iterator_category = std::forward_iterator_tag;
        using difference_type = std::ptrdiff_t;
        using value_type = ValueType;
        using pointer = value_type *;
        using reference = value_type &;

        value_type operator * ()
        {
            return p->value();
        }

        Iterator & operator ++ ()
        {
            p = p->next;
            return *this;
        }

        Iterator operator ++ (int)
        {
            auto retvalue = *this;
            ++(*this);
            return retvalue;
        }

        friend bool operator == (const Iterator & left, const Iterator & right) = default;
        friend bool operator != (const Iterator & left, const Iterator & right) = default;

        Node * p{};
    };

    Iterator begin() const { return {head}; }
    Iterator end() const { return {nullptr}; }

    template <bool is_plain_column>
    ALWAYS_INLINE void add(const IColumn & column, size_t row_num, Arena & arena)
    {
        Node * new_node = Node::template allocate<is_plain_column>(arena, column, row_num);
        add(new_node);
    }

    ALWAYS_INLINE void add(ValueType value, Arena & arena)
    {
        Node * new_node = Node::allocate(value, arena);
        add(new_node);
    }

    ALWAYS_INLINE void add(Node * new_node)
    {
        new_node->next = nullptr;
        if (head == nullptr) [[unlikely]]
        {
            head = new_node;
        }

        if (tail != nullptr) [[likely]]
        {
            tail->next = new_node;
        }
        tail = new_node;

        if constexpr (has_count_field)
        {
            ++ count;
        }
    }

    ALWAYS_INLINE size_t size() const
    {
        if constexpr (has_count_field)
        {
            return count;
        }
        else
        {
            return std::distance(begin(), end());
        }
    }

    ALWAYS_INLINE bool empty() const
    {
        return begin() == end();
    }

    void merge(const ArenaLinkedList & rhs, Arena & arena)
    {
        auto rhs_iter = rhs.head;
        while (rhs_iter)
        {
            auto new_node = rhs_iter->clone(arena);
            add(new_node);
            rhs_iter = rhs_iter->next;
        }
    }

    void mergeLink(const ArenaLinkedList & rhs, Arena &)
    {
        if (!head) [[unlikely]]
        {
            head = rhs.head;
        }

        if (tail) [[likely]]
        {
            tail->next = rhs.head;
        }
        if (rhs.tail) [[likely]]
        {
            tail = rhs.tail;
        }

        if constexpr (has_count_field)
        {
            count += rhs.count;
        }
    }
};

```



### 测试

测试代码是基于gtest写的。

```c++
#include <ArenaLinkedNodeList.h>

#include <gtest/gtest.h>

TEST(ArenaLinkedList, StringList)
{
    Arena arena;
    ArenaLinkedList<StringRef> list;
    String s1{"Activity1"}, s2{"Activity2"}, s3{"ActivityActivity3"};
    list.add(StringRef(s1), arena);
    list.add(StringRef(s2), arena);
    list.add(StringRef(s3), arena);

    ASSERT_EQ(list.size(), 3);

    auto iter = list.begin();
    ASSERT_EQ(*iter, s1);
    ++iter;
    ASSERT_EQ(*iter, s2);
    ++iter;
    ASSERT_EQ(*iter, s3);
}

TEST(ArenaLinkedList, NumberList)
{
    Arena arena;
    ArenaLinkedList<Int64, true> list;
    std::array<Int64, 10> expected {1, 4, 2, 1024, 10231024, 102310241025, 888, 99999999, -102310241025, -99999999};
    for (auto x : expected)
        list.add(x, arena);

    ASSERT_EQ(list.size(), 10);

    auto iter = list.begin();
    for (size_t i = 0; i < expected.size(); ++i, ++iter)
        ASSERT_EQ(*iter, expected[i]);
}

TEST(ArenaLinkedList, MergeList)
{
    Arena arena;
    ArenaLinkedList<StringRef> list1, list2;
    String s1{"Activity1"}, s2{"Activity2"}, s3{"ActivityActivity3"}, s4{"ABCDEFGHIJKLMN"};
    Strings expected{s1, s2, s3, s4};
    list1.add(StringRef(s1), arena);
    list1.add(StringRef(s2), arena);
    list1.add(StringRef(s3), arena);
    list2.add(StringRef(s4), arena);

    list1.merge(list2, arena);

    auto iter = list1.begin();
    ASSERT_EQ(list1.size(), expected.size());
    for (auto x : expected)
    {
        ASSERT_EQ(*iter, x);
        ++iter;
    }
}

TEST(ArenaLinkedList, MergeEmptyList)
{
    Arena arena;
    ArenaLinkedList<StringRef> list1, list2;
    String s1{"Activity1"}, s2{"Activity2"}, s3{"ActivityActivity3"};
    Strings expected{s1, s2, s3};
    list1.add(StringRef(s1), arena);
    list1.add(StringRef(s2), arena);
    list1.add(StringRef(s3), arena);

    // list2 is an empty list.
    list1.merge(list2, arena);

    auto iter = list1.begin();
    ASSERT_EQ(list1.size(), expected.size());
    for (auto x : expected)
    {
        ASSERT_EQ(*iter, x);
        ++iter;
    }
}

TEST(ArenaLinkedList, MergeLinkEmptyList)
{
    Arena arena;
    ArenaLinkedList<StringRef> list1, list2;
    String s1{"Activity1"}, s2{"Activity2"}, s3{"ActivityActivity3"};
    Strings expected{s1, s2, s3};
    list1.add(StringRef(s1), arena);
    list1.add(StringRef(s2), arena);
    list1.add(StringRef(s3), arena);

    // list2 is an empty list.
    list1.mergeLink(list2, arena);

    auto iter = list1.begin();
    ASSERT_EQ(list1.size(), expected.size());
    for (auto x : expected)
    {
        ASSERT_EQ(*iter, x);
        ++iter;
    }
}

TEST(ArenaLinkedList, MergeLinkEmptyListAndAddNew)
{
    Arena arena;
    ArenaLinkedList<StringRef> list1, list2;
    String s1{"Activity1"}, s2{"Activity2"}, s3{"ActivityActivity3"}, s4{"ABCDEFGHIJKLMN"}, s5{"abcdefg"};
    Strings expected{s1, s2, s3, s4, s5};
    list1.add(StringRef(s1), arena);
    list1.add(StringRef(s2), arena);
    list1.add(StringRef(s3), arena);

    // list2 is an empty list.
    list1.mergeLink(list2, arena);
    list1.add(StringRef(s4), arena);
    list1.add(s5, arena);

    auto iter = list1.begin();
    ASSERT_EQ(list1.size(), expected.size());
    for (auto x : expected)
    {
        ASSERT_EQ(*iter, x);
        ++iter;
    }
}

```



测试全部通过。
