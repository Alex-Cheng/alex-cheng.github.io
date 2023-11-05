# An efficient and memory-saving data structure for some kinds of aggregation functions

In certain scenarios, special customized data structures for aggregation can achieve better performance and save memory.


## Problems with aggregate function `GroupArray``

The `GroupArray` aggregation function transform a group of contents into a group of arrays, such as the following example:

```sql
SELECT groupArray(concat('ABC-', toString(number))) from numbers(20) group by number % 5;
-------------------------------------------------- ----
Output:
-------------------------------------------------- ----
['ABC-0','ABC-5','ABC-10','ABC-15']
['ABC-1','ABC-6','ABC-11','ABC-16']
['ABC-2','ABC-7','ABC-12','ABC-17']
['ABC-3','ABC-8','ABC-13','ABC-18']
['ABC-4','ABC-9','ABC-14','ABC-19']
```

The original implementation of the aggregation function uses a sequence list `PODArray` to store strings. Each string consists of two parts: size and data, as shown in the following simplified code:

```c++

//Memory arrangement:
// [8 bytes]size, [variable number of bytes]data...
// For example, the string "ABC" is represented as follows:
// 0x0000000000000003, 'A', 'B', 'C'
struct StringNode
{
     size_t size;
     //The actual data is stored at the end of the instance.
};
using AggregateData = PODArray<StringNode*>
```

During the aggregation process, StringNode instances are continuously created and their pointers are placed into the `AggregateData` instance that represents the aggregated data. There are several problems with this implementation approach:

1. During the aggregation process, the aggregate data represented by `AggregateData` continues to grow, which will cause multiple memory "reallocate" actions due to exceeding of memory capacity of PODArray, and there will be additional cost of copying data to new memory chunk.
2. The initial size of PODArray is also difficult to determine: if the initial size is too large, it will waste space; if the initial size is too small, after "reallocate" for new larger memory space, the original initial memory will be wasted, and the size of memory to reallocate may be overestimate. For example, if the initial size of `AggregateData` is 32 bytes, and the actual aggregate data is 48 bytes, the memory chunk needs to be reallocated. The reallocated memory is 64 bytes, so the wasted memory is: 32 bytes on old memory chunk + 16 bytes on new memory chunk, becaue after the 48 bytes of data are copied into the new space, there are 16 bytes left. Therefore, a total of 48 bytes wasted.
3. The size field of `StringNode` does not need 8 bytes, because we know that in our actual usage scenario, the maximum string will not exceed 65535, and 2 bytes are enough to express the length, which is a waste of 6 byte.



## A solution that uses linked list instead of sequence list

Replacing the sequence list with a linked list seems to be unfeasible at first glance, because of two deep-rooted viewpoints:

1. The memory of the linked list is scattered and the locality is not good;
2. Every time a new node is added to the linked list, memory needs to be allocated. Too many memory allocation actions affect efficiency;
3. Linked list access is slow and you need to find the next one through the `next` pointer.

Under the prerequisite of using `Arena`'s memory allocator and the current GroupArray's aggregate data structure, neither of the above points is absolutely correct.

Firstly, let’s talk about the first problem. In a general memory allocator, the memory allocated each time may be discontinuous. This is the reason why the memory of the linked list is scattered. However, the memory allocated by the Arena memory allocator is continuous within one memory chunk. Linked list nodes are continuous unless switching memory chunk which is unlikely happen. Each aggregate thread has its own Arena memory allocator. Therefore, in this case, the memory of the linked list is basically continuous, ensuring relative locality.

The second question is also related to the "Arena" memory allocator. The "Arena" memory allocator allocates a large chunk of memory by calling the system interface (jemalloc or mmap or other) once. Then each time the Arena memory allocator is called to allocate memory, the only thing it needs to do is returning the address of free memory in the memory chunk, and then update the address of free memory, i.e. update the `void *` pointer to the beginning of the remaining free memory. This is a very lightweight function call and is most likely inlined.

The third question is not a problem, because the aggregate data is an array of pointers to `StringNode` and although PODArray is a sequence list, each access to the `StringNode` instance must be through a pointer, which is the same as accessing through the `next` pointer in a linked list. For the new solution, we can directly access the real data, thus it does not need to access the real data through the pointer of the linked list node. Therefore, the number of dereference operations of pointers(i.e. operator *) remains unchanged.



In summary, linked lists instead of sequence lists are a better solution in this specific scenario.



## Save 6 bytes

The original `size_t size` requires 8 bytes, but actually two bytes are enough. Although it is only 6 bytes, the total memory saved is very considerable when the number of rows of data is large. For example, for one billion pieces of data, about 8GiB (8 x 1 billion) of memory will be saved.

This is achieved as follows:

```c++
struct StringNode
{
    UInt16 size;
    char data[6];
}

// string_size is the actual size of the string. sizeof(StringNode::data) is equal to 6.
arena.alignedAlloc(std::max(sizeof(Node), sizeof(Node) - sizeof(StringNode::data) + string_size), alignof(Node));
```

By changing the size to UInt16 and adding a 6-byte data field, 6 bytes are saved.



## Define the `count` field as needed

Originally a linked list does not require the count field because it can be obtained by traversing the next pointer. But in fact, we may need to quickly obtain the number of nodes in a linked list, however it may not be necessary in some other cases.

Use template parameters to control whether the count field is required. In scenarios where there is no need to obtain the number of nodes (such as the GroupArray aggregate function in this example), 8 bytes of the count field can be saved. A little adds up to a lot.



```c++
struct EmptyState{};

template <bool is_empty, typename T>
using TypeOrEmpty = std::conditional_t<is_empty, EmptyState, T>;

template <...,
bool require_count,
...
         >
struct...
{
     ... ...
     [[no_unique_address]] TypeOrEmpty<!require_count, UInt64> node_count {};
     ... ...
};


```

When the template parameter `require_count` is equal to false, `node_count` does not occupy space.



## Implementation

### Code structure

The implementation consists of the following template classes:

1. struct ArenaLinkedNodeList
    Represents the entire linked list data structure.
2. concept UnfixedSized
    Determine whether the data type is variable length. It is stipulated that any data type with char * data and size_t size is a variable length data type.
3. struct ArenaMemoryNodeBase
    Base class of data structure that represents a node in a linked list. Derived classes inherit this base class using CRTP pattern.
4. struct ArenaMemoryUnfixedSizedNode
    Linked list nodes representing variable-length data, usually strings or arrays.
5. struct ArenaMemoryFixedSizedNode
    Linked list nodes representing fixed-length data, usually numerical values and dates.



### Source code

The following is the implementation source code.

```c++
struct EmptyState { }; // Represents an empty type.

template <bool use_type, typename T>
using MaybeEmptyState = std::conditional_t<use_type, T, EmptyState>; // It may be an empty type or T, controlled by use_type.

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
             throwException();
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

         Iterator&operator++()
         {
             p = p->next;
             return *this;
         }

         Iteratoroperator++(int)
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

     ALWAYS_INLINE void add(Node* new_node)
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



### test

The test code is written based on gtest.

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



All tests passed.
