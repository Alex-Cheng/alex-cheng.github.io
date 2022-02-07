## C++标准库的某些场景下的效率问题

在下面的场景中，C++标准库的unordered_map、map、multiset、unordered_multiset效率并不高。

### 分组重复次数计数

有一亿条记录，记录有两列：group_id，attribute，并且记录已经按照group_id排了序。要求计数每个group_id对应的行的attribute值的重复次数，生成一个新的结果列。例如：

| group_id | attribute | 结果 |
| ----|------|---- |
| G001 | A | 1 | 
| G001 | A | 2 |
| G001 | B | 1 |
| G002 | C | 1 |
| G002 | B | 1 |
| G002 | A | 1 |
| G002 | B | 2 |

### 性能测试代码

用如下代码来测试std::map, std::unordered_map, std::multiset, std::unordered_multiset的性能。

### 性能测试结果

用release build以非debug模式运行若干次，得到以下结果：

| 实现方式 | 处理一亿条数据效率（运行花费时间） |
| --------|----------------------|
| std::unordered_multiset | 15.0s |
| std::multiset | 21.7s |
| std::unordered_map | 3.9s |
| std::map | 7.3s |

通过上面的测试结果可知：

*   multiset方式比map方式慢，需要研究具体实现；
*   红黑树方式(map和multiset所使用的)比Hash方式（unordered_map与unordered_multiset所使用的）要慢。从算法分析上也是如此，但hash table的构建比较耗时。

#### Debug版本和Release版本性能差别极大

| 实现方式 | Release版本一亿条数据处理效率 | Debug版本一亿条数处理效率 |
| ---------------|--------------------------------------------|---------------------------------------|
| std::unordered_multiset | 15.0s | 310s |
| std::multiset | 21.7s | 357s |
| std::unordered_map | 3.9s | 141s |
| std::map | 7.3s | 189s |

从测试数据可以看出，debug版本与release版本的性能是20倍左右的差距。性能天壤之别。

## 特定场景的Hash map实现

###优化思路
文中特定场景需要关联容器（hash map或者multiset）来记录每个基数的重复次数，具有以下几个特点：
1. 所需的容器的空间不需要太大，因为同一个group_id对应的行的数量小于 1000，即使全不相同需要的容器空间也不会超过1000；
2. 需要频繁地清空容器或者销毁并重新创建容器，因为扫描到新的group_id时原先的容器内容就没有用了；
3. 容器的每个元素所占空间不会很大，因为key值不会很大，value的值是UInt32或者UInt64。

根据VS Profiler的性能分析结果，STL关联容器中的创建和销毁元素的花费时间最多。

借鉴CH的Hash map，实现特定场景下效率优化的Hash map，优化的要点在于以下几点：
1. 提升Hash map的clear操作效率；
2. 提高内存访问的局部性，提升cache命中率；
3. 避免分配和释放内存；
4. 避免容器扩容时的内存拷贝。

### 提升clear() 操作

通过引入version概念实现O(1)的清空容器操作。一般的Hash map会在clear()方法中会一个个销毁容器内的元素然后再回收内存，参考 [双向链表std::list的clear()](https://prothentic.feishu.cn/docs/doccnAVHsM2RjClGPxrsNvWrlce#SMxsER)

优化的Hash map只要`version+=1`即起到清除容器的效果，因为优化的Hash map的每个元素都有一个version字段，如果version字段值不等于当前version，则认为该元素不存在或已销毁。

### 提高cache命中率
因为总是使用同一块内存，对内存访问的局部性提升了，这块内存进入到了cache中后，每次对hash map的访问都能够命中到cache。在多核时代中，cache的命中率的提高比单纯CPU的优化效果更好。

### 避免分配和释放内存

在函数中定义一个局部数组，该数组就在栈内存中。栈内存的分配很简单，编译器预先知道函数中有多少个局部变量，能够计算出总的栈内存空间`size`，执行`SP -= size`就等于分配了这块内存，`SP+<偏移量>`就是局部变量的地址。

栈内存根本不需要释放，因为函数退出时通过`SP += size`就等同于释放内存。

### 避免扩容时的内存拷贝

根据特殊场景情况，能够估计出一个最大容量，一次性在栈内存中分配这么大的内存。

### 实现代码

```
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
        OccurCountNode<std::string> occurs[MAP_SIZE+TAIL];
        auto hasher = std::hash<std::string>();
        auto emplace = [&hasher, &occurs, &version, MASK, MAP_SIZE, TAIL](const std::string & key) -> OccurCountNode<std::string>*
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

```

### 性能测试数据

| 实现方式 | Release版本一亿条数据处理效率 |
| ---------------|--------------------------------------------|
| std::unordered_multiset | 15.4s |
| std::multiset | 23.0s |
| std::unordered_map | 4.0s |
| std::map | 8.5s |
| **特定场景优化Hash map** | **1.9s** |

### 通用的容器为什么不这么做

通用的容器类是要考虑各种情况，因此会有一些在特定场景下“不必要”的东西，这些是影响了特定场景下的性能的。

例如：std::unordered_map就是使用了双向链表作为内部存储，双向链表的好处是不需要请求分配一整块内存，在扩容时不需要把旧内存内容拷贝到新内存上，但是代价是某些情况下（当前场景就是属于这里的“某些情况”）访问数据时有性能的损失。

通用容器类也不可能在栈内存中，因为栈内存空间是有限的。但是在我们的特定场景下可以保证容器空间需求有一个上界，适合放在栈内存中。

## STL容器与特定场景优化后的Hash Table性能测试代码

以上所涉及的所有代码如下，包括对STL四个关联容器和我们自己的优化后的hash map的按照特定场景的性能测试。

```
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

## CH的Hash Map

```
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

如代码所示，HashTable模板接受5个模板参数：

1.  Key - 就是键值类型
2.  Cell - 映射值的类型
3.  Hash - 哈希函数
4.  Grower - 增长策略
5.  Allocator - 内存分配器

### Clearable Hash Map

Clearable hash map是HashTable模板的一个实例化的简单的派生类，重点是用了`ClearableHashMapCell<Key, Mapped, Hash>`作为Cell类型。`ClearableHashMapCell`中定义了一个version字段，是其实现“可快速clear”的关键。

`ClearableHashMapCell` 在 `HashMapCell` 的基础上增加了一个version字段。在每次Clearable hash map执行了clear操作之后其version都会增1，所以version字段不等于当前version的Cell都被认为是“被清除的”Cell。

```
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

### 基于栈内存的Clearable Hash Map

基于栈内存的Clearable hash map是通过特殊的内存分配器`AllocatorWithStackMemory`实现的，定义如下：

```
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

`HashTableAllocatorWithStackMemory`的主体实现就是`AllocatorWithStackMemory`。

```
/**
  * We are going to use the entire memory we allocated when resizing a hash
  * table, so it makes sense to pre-fault the pages so that page faults don't
  * interrupt the resize loop. Set the allocator parameter accordingly.
  */
using HashTableAllocator = Allocator<true /* clear_memory */, true /* mmap_populate */>;

template <size_t initial_bytes = 64>
using HashTableAllocatorWithStackMemory = AllocatorWithStackMemory<HashTableAllocator, initial_bytes>;

```

AllocatorWithStackMemory 的做法就是定义一个栈内存上的数组，如果需要分配的内存大小正好小于等于这个数组的长度，就返回这个数组的地址，这个数组就是”分配“的内存。如果需要分配的内存大小不幸大于数组长度，则按照通常的做法（Allocator模板实现的，堆内存中分配内存）来分配内存。

### Hasher

CH中一般使用city hash。

### HashTableGrower

HashTableGrower代表hash table的内存使用策略，基于一整块连续内存，用hash值通过跟mask掩码进行”与“操作得到地址，并在哈希碰撞的时候将地址值增1以避免碰撞。

## 参考代码

### 双向链表std::list的clear()

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
