# Performance Optimization of C++ Hash Map in Specific Scenarios (Beyond STL's 1x)

In the following scenarios, the efficiency of C++ standard library's `unordered_map`, `map`, `multiset`, and `unordered_multiset` is not high.

## Counting the Number of Repeated Occurrences in Groups

There are one hundred million records with two columns: `group_id` and `attribute`, and the records are already sorted by `group_id`. The requirement is to count the number of repeated occurrences of the `attribute` values for each `group_id` and generate a new result column. For example:

| group_id | attribute | result |
| ----|------|---- |
| G001 | A | 1 | 
| G001 | A | 2 |
| G001 | B | 1 |
| G002 | C | 1 |
| G002 | B | 1 |
| G002 | A | 1 |
| G002 | B | 2 |

## Performance Testing Code

The following code is used to test the performance of `std::map`, `std::unordered_map`, `std::multiset`, and `std::unordered_multiset`.

## Performance Test Results

Running several times in release build and non-debug mode, the following results are obtained:

| Implementation | Efficiency in Processing 100 Million Data (Time Taken) |
| --------|----------------------|
| `std::unordered_multiset` | 15.0s |
| `std::multiset` | 21.7s |
| `std::unordered_map` | 3.9s |
| `std::map` | 7.3s |

From the above test results, it is known that:

The `multiset` method is slower than the `map` method, and the specific implementation needs to be studied;

The Red-Black tree method (used by `map` and `multiset`) is slower than the Hash method (used by `unordered_map` and `unordered_multiset`). This is also the case from the algorithm analysis, but the construction of the hash table is time-consuming.

## Debug Version and Release Version Performance Difference

| Implementation | Release Version Efficiency for Processing 100 Million Data | Debug Version Efficiency for Processing 100 Million Data |
| ---------------|--------------------------------------------|---------------------------------------|
| `std::unordered_multiset` | 15.0s | 310s |
| `std::multiset` | 21.7s | 357s |
| `std::unordered_map` | 3.9s | 141s |
| `std::map` | 7.3s | 189s |

From the test data, it can be seen that there is about a 20 times difference in performance between the debug version and the release version. The difference in performance is huge.

## Specific Scenario Hash Map Implementation

### Optimization Ideas

In the specific scenario described, an associative container (hash map or multiset) is needed to record the number of repetitions for each base number, with the following characteristics:
1. The required container space does not need to be too large, because the number of rows corresponding to the same `group_id` is less than 1000, and even if they are all different, the container space required will not exceed 1000;
2. The container needs to be cleared frequently or destroyed and recreated, because when a new `group_id` is scanned, the original container content is no longer useful;
3. The space occupied by each element of the container will not be very large, because the key value will not be very large, and the value of `value` is `UInt32` or `UInt64`.

According to the performance analysis results of VS Profiler, the most time-consuming operation in STL associative containers is the creation and destruction of elements.

By drawing on CH's Hash map, an optimized Hash map for specific scenarios is implemented, with the key points of optimization being:
1. Improve the efficiency of the Hash map's `clear` operation;
2. Improve the locality of memory access and increase the cache hit rate;
3. Avoid memory allocation and deallocation;
4. Avoid memory copy during container expansion.

### Improving the `clear()` Operation

By introducing the concept of version to achieve an O(1) empty container operation. Generally, Hash maps will destroy the elements in the container one by one and then reclaim the memory in the `clear()` method, referring to the `std::list` of doubly linked list.

The optimized Hash map only needs to increment the version to clear the container, because each element of the optimized Hash map has a version field. If the version field value is not equal to the current version, it is considered that the element does not exist or has been destroyed.

### Increasing Cache Hit Rate

Because the same piece of memory is always used, the locality of memory access is improved, and this piece of memory enters the cache. Each access to the hash map can hit the cache. In the multi-core era, the improvement of cache hit rate is better than the optimization of CPU alone.

### Avoiding Memory Allocation and Deallocation

Define a local array in the function, which is in the stack memory. The allocation of stack memory is very simple. The compiler knows in advance how many local variables there are in the function, and can calculate the total stack memory space size. Executing `SP -= size` is equivalent to allocating this piece of memory, and `SP+<offset>` is the address of the local variable.

Stack memory does not need to be released at all, because when the function exits, `SP += size` is equivalent to releasing memory.

### Avoiding Memory Copy During Expansion

According to the special scenario, an estimated maximum capacity can be determined at one time, and such a large memory can be allocated in the stack memory.

## Implementation Code

```cpp
template <typename KeyTy>
struct OccurCountNode
{
        KeyTy key;
        uint32_t count = 0;
        uint32_t version = 0;
};

void my_hash_map(const std::vector& group_ids, const std::vector& attrs, std::vector& result)
{
        const unsigned char DEGREE = 9;
        const size_t MAP_SIZE = 1UL << DEGREE;
        const size_t MASK = MAP_SIZE - 1;
        const size_t TAIL = 10;
        int version = 1;
        OccurCountNode occurs[MAP_SIZE+TAIL];
        auto hasher = std::hash<KeyTy>();
        auto emplace = [&](KeyTy key) -> OccurCountNode*
        {
                size_t idx = hasher(key) & MASK;
                while (idx < MAP_SIZE + TAIL)
                {
                        auto& item = occurs[idx];
                        if (item.version != version)
                        {
                                item.version = version;
                                item.key = key;
                                item.count = 1;
                                return &item;
                        }
                        if (item.version == version && item.key == key)
                        {
                                item.count++;
                                return &item;
                        }
                        idx++;
                }
                return nullptr;
        };

```

## Performance Test Data

| Implementation | Release Version Efficiency for Processing 100 Million Data |
| ---------------|--------------------------------------------|
| `std::unordered_multiset` | 15.4s |
| `std::multiset` | 23.0s |
| `std::unordered_map` | 4.0s |
| `std::map` | 8.5s |
| Optimized Hash map for Specific Scenarios | 1.9s |

## Why General Containers Don't Do This

General container classes need to consider various situations, so there will be some "unnecessary" things in specific scenarios, which affect the performance in specific scenarios.

For example: `std::unordered_map` uses a doubly linked list as the internal storage. The advantage of the doubly linked list is that it does not need to request a whole block of memory. When expanding, it does not need to copy the old memory content to the new memory, but the cost is the loss of performance when accessing data in some cases (the current scenario belongs to the "some cases" here).

General container classes cannot be in stack memory either, because the stack memory space is limited. However, in our specific scenario, we can ensure that there is an upper limit to the container space demand, which is suitable for being placed in stack memory.

## STL Container and Optimized Hash Table Performance Test Code

All the codes involved above, including the performance test of the four STL associative containers and our own optimized hash map according to the specific scenario.

```cpp
#include <chrono>
#include <iostream>
#include <map>
#include <set>
#include <unordered_map>
#include <unordered_set>
#include <vector>

using namespace std::chrono;

template <typename TMap>
void stl_map(const std::vector<std::string>& group_ids, const std::vector<std::string>& attrs, std::vector<int>& result)
{
        TMap occurs;
        std::string group_id;
        for (size_t i = 0; i < group_ids.size(); ++i)
        {
                if (group_id != group_ids[i])
                {
                        occurs.clear();
                        group_id = group_ids[i];
                }

                auto value = attrs[i];
                if (occurs.find(value) == occurs.end())
                {
                        occurs[value] = 1;
                }
                else
                {
                        ++occurs[value];
                }
                // assign occurs[value] to result
                result[i] = occurs[value];
        }
}

template <typename TMultiSet>
void stl_multiset(const std::vector<std::string>& group_ids, const std::vector<std::string>& attrs, std::vector<int>& result)
{
        TMultiSet occurs;
        std::string group_id;
        int tmp;
        for (size_t i = 0; i < group_ids.size(); ++i)
        {
                if (group_id != group_ids[i])
                {
                        occurs.clear();
                        group_id = group_ids[i];
                }

                auto value = attrs[i];
                std::multiset<int> s;
                occurs.insert(value);
                // assign occurs[value] to result
                result[i] = occurs.count(value);
        }
}

template <typename KeyTy>
struct OccurCountNode
{
        KeyTy key;
        uint32_t count = 0;
        uint32_t version = 0;
};

void my_hash_map(const std::vector<std::string>& group_ids, const std::vector<std::string>& attrs, std::vector<int>& result)
{
        const unsigned char DEGREE = 9;
        const size_t MAP_SIZE = 1UL << DEGREE;
        const size_t MASK = MAP_SIZE - 1;
        const size_t TAIL = 10;
        int version = 1;
        OccurCountNode<std::string> occurs[MAP_SIZE + TAIL];
        auto hasher = std::hash<std::string>();
        auto emplace = [&hasher, &occurs, &version, MASK, MAP_SIZE, TAIL](const std::string& key) -> OccurCountNode<std::string>*
        {
                size_t idx = hasher(key) & MASK;
                while (idx < MAP_SIZE + TAIL)
                {
                        auto& item = occurs[idx];
                        if (item.version != version)
                        {
                                item.version = version;
                                item.key = key;
                                item.count = 1;
                                return &item;
                        }
                        if (item.version == version && item.key == key)
                        {
                                item.count++;
                                return &item;
                        }
                        idx++;
                }
                return nullptr;
        };

        std::string group_id;
        for (size_t i = 0; i < group_ids.size(); ++i)
        {
                if (group_id != group_ids[i])
                {
                        version++;
                        group_id = group_ids[i];
                }

                auto value = attrs[i];
                OccurCountNode<std::string>* find_result = emplace(value);
                // assign occurs[value] to result
                result[i] = find_result->count;
        }
}

using OccursCountFunc = void (*)(const std::vector<std::string>& group_ids, const std::vector<std::string>& attrs, std::vector<int>& result);

long long test_perf(const std::vector<std::string>& group_ids, const std::vector<std::string>& attrs, std::vector<int>& result, OccursCountFunc func)
{
        auto start = system_clock::now();

        func(group_ids, attrs, result);

        for (size_t i = 0; i < 10; ++i)
        {
                std::cout << result[i] << ", ";
        }

        auto end = system_clock::now();
        return duration_cast<milliseconds>(end - start).count();
}

int main()
{
        const size_t DATA_SIZE = 100000000;
        std::vector<std::string> group_ids(DATA_SIZE);
        std::vector<std::string> attrs(DATA_SIZE);
        std::vector<int> result1(DATA_SIZE);
        std::vector<int> result2(DATA_SIZE);
        std::vector<int> result3(DATA_SIZE);
        std::vector<int> result4(DATA_SIZE);
        std::vector<int> result5(DATA_SIZE);

        // Prepare test data.
        char buf[50];
        std::string values[] = { "A", "B", "C", "D", "E" };
        for (size_t i = 0; i < DATA_SIZE; ++i)
        {
                snprintf(buf, 50, "G%010zu", (i / 20) + 1);
                group_ids[i] = std::string(buf);
                attrs[i] = values[rand() % 5];
        }

        // Performance test.
        std::cout << "Performance test starts\n";

        std::cout << "stl_hash_multiset - ";
        std::cout << "Cost: " << test_perf(group_ids, attrs, result1, stl_multiset<std::unordered_multiset<std::string>>) << std::endl;

        std::cout << "stl_multiset - ";
        std::cout << "Cost: " << test_perf(group_ids, attrs, result2, stl_multiset<std::multiset<std::string>>) << std::endl;

        std::cout << "stl_hash_map - ";
        std::cout << "Cost: " << test_perf(group_ids, attrs, result3, stl_map<std::unordered_map<std::string, int>>) << std::endl;

        std::cout << "stl_map - ";
        std::cout << "Cost: " << test_perf(group_ids, attrs, result4, stl_map<std::map<std::string, int>>) << std::endl;

        std::cout << "my_hash_map" << std::endl;
        std::cout << "Cost: " << test_perf(group_ids, attrs, result5, my_hash_map) << std::endl;

        std::cout << "Performance test ended\n";

        // Validate results.
        for (size_t i = 0; i < DATA_SIZE; ++i)
        {
                if (result1[i] != result2[i] || result2[i] != result3[i] || result3[i] != result4[i] || result4[i] != result5[i])
                {
                        std::cout << "Error: " << result1[i] << ", " << result2[i] << ", " << result3[i] << ", " << result4[i] << result5[i] << std::endl;
                }
        }
}

```

## CH's Hash Map

```cpp
// The HashTable
template
<
    typename Key,
    typename Cell,
    typename Hash,
    typename Grower,
    typename Allocator
>
class HashTable :
    private boost::noncopyable,
    protected Hash,
    protected Allocator,
    protected Cell::State,
    protected ZeroValueStorage<Cell::need_zero_value_storage, Cell>     /// empty base optimization
{ ... }

```

As shown in the code, the HashTable template accepts five template parameters:

1. **Key** - This is the key type.
2. **Cell** - This is the type of the mapped value.
3. **Hash** - This is the hash function.
4. **Grower** - This is the growth strategy.
5. **Allocator** - This is the memory allocator.

### Clearable Hash Map

The Clearable hash map is a simple derived class instantiated from the HashTable template, focusing on using `ClearableHashMapCell<Key, Mapped, Hash>` as the Cell type. The `ClearableHashMapCell` defines a version field, which is key to its "quick clear" capability.

The `ClearableHashMapCell` adds a version field based on `HashMapCell`. After each clear operation on the Clearable hash map, its version is incremented by 1, so Cells whose version field is not equal to the current version are considered "cleared" Cells.

```cpp
template
<
    typename Key,
    typename Mapped,
    typename Hash = DefaultHash<Key>,
    typename Grower = HashTableGrower<>,
    typename Allocator = HashTableAllocator
>
class ClearableHashMap : public HashTable<Key, ClearableHashMapCell<Key, Mapped, Hash>, Hash, Grower, Allocator>
{
public:
    Mapped & operator[](const Key & x)
    {
        typename ClearableHashMap::LookupResult it;
        bool inserted;
        this->emplace(x, it, inserted);

        if (inserted)
            new (&it->getMapped()) Mapped();

        return it->getMapped();
    }

    void clear()
    {
        ++this->version;
        this->m_size = 0;
    }
};
```

### Stack Memory Based Clearable Hash Map

The stack memory-based Clearable hash map is implemented through a special memory allocator `AllocatorWithStackMemory`, defined as follows:

```cpp
template <typename Key, typename Mapped, typename Hash,
    size_t initial_size_degree>
using ClearableHashMapWithStackMemory = ClearableHashMap<
    Key,
    Mapped,
    Hash,
    HashTableGrower<initial_size_degree>,
    HashTableAllocatorWithStackMemory<
        (1ULL << initial_size_degree)
        * sizeof(ClearableHashMapCell<Key, Mapped, Hash>)>>;
```

The main implementation of `HashTableAllocatorWithStackMemory` is `AllocatorWithStackMemory`.

```cpp
/**
  * We are going to use the entire memory we allocated when resizing a hash
  * table, so it makes sense to pre-fault the pages so that page faults don't
  * interrupt the resize loop. Set the allocator parameter accordingly.
  */
using HashTableAllocator = Allocator<true /* clear_memory */, true /* mmap_populate */>;

template <size_t initial_bytes = 64>
using HashTableAllocatorWithStackMemory = AllocatorWithStackMemory<HashTableAllocator, initial_bytes>;
```

The approach of `AllocatorWithStackMemory` is to define an array on the stack memory. If the size of the memory to be allocated is exactly less than or equal to the length of this array, the address of this array is returned, which is the "allocated" memory. If the size of the memory to be allocated is unfortunately greater than the array length, memory is allocated as usual (allocated in heap memory implemented by Allocator template).

### Hasher

In CH, the `city hash` is generally used.

### HashTableGrower

`HashTableGrower` represents the memory usage strategy of the hash table, based on a block of contiguous memory, using the hash value to perform an "and" operation with the mask to get the address, and incrementing the address value by 1 to avoid collision when there is a hash collision.

## Reference Code

### `clear()` Method of Doubly Linked List `std::list`
```
    void clear() noexcept { // erase all
        auto& _My_data = _Mypair._Myval2;
        _My_data._Orphan_non_end();
        _Node::_Free_non_head(_Getal(), _My_data._Myhead);
        _My_data._Myhead->_Next = _My_data._Myhead;
        _My_data._Myhead->_Prev = _My_data._Myhead;
        _My_data._Mysize        = 0;
    }

    template <class _Alnode>
    static void _Free_non_head(
        _Alnode& _Al, _Nodeptr _Head) noexcept { // free a list starting at _First and terminated at nullptr
        _Head->_Prev->_Next = nullptr;

        auto _Pnode = _Head->_Next;
        for (_Nodeptr _Pnext; _Pnode; _Pnode = _Pnext) {
            _Pnext = _Pnode->_Next;
            _Freenode(_Al, _Pnode);
        }
    }   

    template <class _Alnode>
    static void _Freenode(_Alnode& _Al, _Nodeptr _Ptr) noexcept { // destroy all members in _Ptr and deallocate with _Al
        allocator_traits<_Alnode>::destroy(_Al, _STD addressof(_Ptr->_Myval));
        _Freenode0(_Al, _Ptr);
    }

    template <class _Alnode>
    static void _Freenode0(_Alnode& _Al, _Nodeptr _Ptr) noexcept {
        // destroy pointer members in _Ptr and deallocate with _Al
        static_assert(is_same_v<typename _Alnode::value_type, _List_node>, "Bad _Freenode0 call");
        _Destroy_in_place(_Ptr->_Next);
        _Destroy_in_place(_Ptr->_Prev);
        allocator_traits<_Alnode>::deallocate(_Al, _Ptr, 1);
    }

```
