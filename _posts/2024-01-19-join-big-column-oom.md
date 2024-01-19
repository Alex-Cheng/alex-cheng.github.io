# ClickHouse中“大列”造成的JOIN的内存超限问题

“大列”是指单行数据量非常大的列，通常是100KiB以上。这样的列会导致JOIN（通常LEFT JOIN 和 INNER JOIN）出现内存超限的异常。

## 常用的JOIN算法

这里讨论的是常用的JOIN算法：partial merge join 与 hash join。Direct join算法不在本文讨论范围。

内存超限的错误一般长这样：

```
2024.01.16 17:04:30.084819 [ 3654586 ] {52653888-f266-443a-beba-348c66a88e60} <Error> TCPHandler: Code: 241. DB::Exception: Memory limit (for query) exceeded: would use 33.61 GiB (attempt to allocate chunk of 34359738368 bytes), maximum: 27.94 GiB.: While executing JoiningTransform. (MEMORY_LIMIT_EXCEEDED), Stack trace (when copying this message, always include the lines below):
```

## 测试数据

为了分析“大列”的JOIN运算出现内存超限问题，这里准备了特定的测试数据。

测试数据为两张表：

table1 - 相当于N表，10W行，两列：id，fk（外键）

table2 - 相当于1表，1W行，两列：id，value（value为超长字符串列，每个cell大小500K左右）

创建测试数据的查询如下：

```sql
drop database if exists `big_columns_join`;
create database `big_columns_join`;
use big_columns_join;

create table `big_columns_join`.`big_columns_table` (
    `id` UInt64,
    `fk` UInt64
) ENGINE = MergeTree() order by id
as (select 
        `number`,
        rand(4) % 10000
    from numbers(100000)
    settings max_block_size = 100
);

create table `big_columns_join`.`dim_table1` (
    `id` UInt64,
    `value` String
) ENGINE = MergeTree() order by id
as (select
        `number`,
        repeat(toString(rand(1)), 100000)
    from numbers(10000));
```

## 测试查询

测试查询是简单的LEFT JOIN。

```sql
select
    *
from
    `big_columns_join`.`big_columns_table`
    left join `big_columns_join`.`dim_table1` on `big_columns_join`.`big_columns_table`.`fk` = `big_columns_join`.`dim_table1`.`id`
format Null;
```

## Hash join算法

运行测试查询之前，设定max_joined_block_size_rows阈值。

```sql
set join_algorithm = 'hash';
set max_joined_block_size_rows=10000;  -- 阈值设小，需要内存会变少。
-- 运行测试查询
```

测试结果是：

**JOIN算法为hash join时，无论如何调整max_joined_block_size_rows的阈值大小，均会内存超限。**

报错信息如下：

```
0. Poco::Exception::Exception(String const&, int) @ 0x000000001504f759 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
1. DB::Exception::Exception(DB::Exception::MessageMasked&&, int, bool) @ 0x000000000b243077 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
2. DB::Exception::Exception<char const*, char const*, String, long&, String, char const*, std::basic_string_view<char, std::char_traits<char>>>(int, FormatStringHelperImpl<std::type_identity<char const*>::type, std::type_identity<char const*>::type, std::type_identity<String>::type, std::type_identity<long&>::type, std::type_identity<String>::type, std::type_identity<char const*>::type, std::type_identity<std::basic_string_view<char, std::char_traits<char>>>::type>, char const*&&, char const*&&, String&&, long&, String&&, char const*&&, std::basic_string_view<char, std::char_traits<char>>&&) @ 0x000000000b255d97 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
3. MemoryTracker::allocImpl(long, bool, MemoryTracker*, double) @ 0x000000000b2551b9 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
4. MemoryTracker::allocImpl(long, bool, MemoryTracker*, double) @ 0x000000000b254d6a in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
5. CurrentMemoryTracker::alloc(long) @ 0x000000000b21b30f in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
6. Allocator<false, false>::realloc(void*, unsigned long, unsigned long, unsigned long) @ 0x000000000b218368 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
7. void DB::PODArrayBase<1ul, 4096ul, Allocator<false, false>, 63ul, 64ul>::resize<>(unsigned long) @ 0x0000000006343dc6 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
8. DB::ColumnString::insertFrom(DB::IColumn const&, unsigned long) @ 0x0000000011c0ae2c in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
9. void DB::(anonymous namespace)::AddedColumns::appendFromBlock<false>(DB::Block const&, unsigned long) @ 0x00000000113d24ca in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
10. DB::PODArray<char8_t, 4096ul, Allocator<false, false>, 63ul, 64ul> DB::(anonymous namespace)::joinRightColumns<(DB::JoinKind)1, (DB::JoinStrictness)3, DB::ColumnsHashing::HashMethodOneNumber<PairNoInit<unsigned long, DB::RowRefList>, DB::RowRefList const, unsigned long, false, true, false>, HashMapTable<unsigned long, HashMapCell<unsigned long, DB::RowRefList, DefaultHash<unsigned long>, HashTableNoState, PairNoInit<unsigned long, DB::RowRefList>>, DefaultHash<unsigned long>, HashTableGrowerWithPrecalculation<8ul>, Allocator<true, true>>, true, false>(std::vector<DB::ColumnsHashing::HashMethodOneNumber<PairNoInit<unsigned long, DB::RowRefList>, DB::RowRefList const, unsigned long, false, true, false>, std::allocator<DB::ColumnsHashing::HashMethodOneNumber<PairNoInit<unsigned long, DB::RowRefList>, DB::RowRefList const, unsigned long, false, true, false>>>&&, std::vector<HashMapTable<unsigned long, HashMapCell<unsigned long, DB::RowRefList, DefaultHash<unsigned long>, HashTableNoState, PairNoInit<unsigned long, DB::RowRefList>>, DefaultHash<unsigned long>, HashTableGrowerWithPrecalculation<8ul>, Allocator<true, true>> const*, std::allocator<HashMapTable<unsigned long, HashMapCell<unsigned long, DB::RowRefList, DefaultHash<unsigned long>, HashTableNoState, PairNoInit<unsigned long, DB::RowRefList>>, DefaultHash<unsigned long>, HashTableGrowerWithPrecalculation<8ul>, Allocator<true, true>> const*>> const&, DB::(anonymous namespace)::AddedColumns&, DB::JoinStuff::JoinUsedFlags&) @ 0x00000000113d602a in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
11. void DB::HashJoin::joinBlockImpl<(DB::JoinKind)1, (DB::JoinStrictness)3, DB::HashJoin::MapsTemplate<DB::RowRefList>>(DB::Block&, DB::Block const&, std::vector<DB::HashJoin::MapsTemplate<DB::RowRefList> const*, std::allocator<DB::HashJoin::MapsTemplate<DB::RowRefList> const*>> const&, bool) const @ 0x0000000011493867 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
12. DB::HashJoin::joinBlock(DB::Block&, std::shared_ptr<DB::ExtraBlock>&) @ 0x00000000113a40e9 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
13. DB::JoiningTransform::readExecute(DB::Chunk&) @ 0x0000000012a32b90 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
14. DB::JoiningTransform::transform(DB::Chunk&) @ 0x0000000012a31905 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
15. DB::JoiningTransform::work() @ 0x0000000012a313aa in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
16. DB::ExecutionThreadContext::executeTask() @ 0x0000000012810d13 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
17. DB::PipelineExecutor::executeStepImpl(unsigned long, std::atomic<bool>*) @ 0x0000000012808ad0 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
18. void std::__function::__policy_invoker<void ()>::__call_impl<std::__function::__default_alloc_func<DB::PipelineExecutor::spawnThreads()::$_0, void ()>>(std::__function::__policy_storage const*) @ 0x000000001280965b in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
19. ThreadPoolImpl<ThreadFromGlobalPoolImpl<false>>::worker(std::__list_iterator<ThreadFromGlobalPoolImpl<false>, void*>) @ 0x000000000b317483 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
20. ThreadFromGlobalPoolImpl<false>::ThreadFromGlobalPoolImpl<void ThreadPoolImpl<ThreadFromGlobalPoolImpl<false>>::scheduleImpl<void>(std::function<void ()>, Priority, std::optional<unsigned long>, bool)::'lambda0'()>(void&&)::'lambda'()::operator()() @ 0x000000000b31a5bf in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
21. ThreadPoolImpl<std::thread>::worker(std::__list_iterator<std::thread, void*>) @ 0x000000000b314b07 in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
22. void* std::__thread_proxy[abi:v15000]<std::tuple<std::unique_ptr<std::__thread_struct, std::default_delete<std::__thread_struct>>, void ThreadPoolImpl<std::thread>::scheduleImpl<void>(std::function<void ()>, Priority, std::optional<unsigned long>, bool)::'lambda0'()>>(void*) @ 0x000000000b318a2e in /home/ubuntu/depot/ch-pro/build-release/programs/clickhouse
23. ? @ 0x00007f6db212b609 in ?
24. ? @ 0x00007f6db2050133 in ?
```

模板方法joinRightColumns根据join key查找对应的右边表的行，找到行对应的row_number，然后通过调用appendFromBlock(block, row_numer)完成一行的JOIN结果。

appendFromBlock每次调用IColumn::insertFrom插入一行。这里有个问题：ColumnString的内容增长是一行一行地增长，在这个过程中涉及到多个reallocation内存重分配，并造成大量的内存之间的数据复制。

## parital merge join算法

运行测试查询之前，设定max_joined_block_size_rows阈值。

```sql
set join_algorithm = 'parital_merge';
set max_joined_block_size_rows=10000;  -- 阈值设小，需要内存会变少。
-- 第一次运行测试查询

set max_joined_block_size_rows=1000000;  -- 阈值设大，需要内存可能会更多。
-- 第二次运行测试查询
```

测试结果是：

**JOIN算法为parital merge join时，调小max_joined_block_size_rows的阈值，内存就不会超限。**

当max_joined_block_size_rows比较大时（上例中第二次运行测试查询），会发生内存超限问题。

出错信息：

```
2024.01.16 17:04:30.084819 [ 3654586 ] {52653888-f266-443a-beba-348c66a88e60} <Error> TCPHandler: Code: 241. DB::Exception: Memory limit (for query) exceeded: would use 33.61 GiB (attempt to allocate chunk of 34359738368 bytes), maximum: 27.94 GiB.: While executing JoiningTransform. (MEMORY_LIMIT_EXCEEDED), Stack trace (when copying this message, always include the lines below):

0. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/exception:134: std::exception::capture() @ 0x000000000b609a42 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
1. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/exception:112: std::exception::exception[abi:v15000]() @ 0x000000000b609a0d in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
2. /home/ubuntu/depot/ch-pro/base/poco/Foundation/src/Exception.cpp:27: Poco::Exception::Exception(String const&, int) @ 0x000000002562ed40 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
3. /home/ubuntu/depot/ch-pro/src/Common/Exception.cpp:96: DB::Exception::Exception(DB::Exception::MessageMasked&&, int, bool) @ 0x00000000144166ee in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
4. /home/ubuntu/depot/ch-pro/src/Common/Exception.h:73: DB::Exception::Exception(String&&, int, bool) @ 0x000000000b5fba8a in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
5. /home/ubuntu/depot/ch-pro/src/Common/Exception.h:101: DB::Exception::Exception<char const*, char const*, String, long&, String, char const*, std::basic_string_view<char, std::char_traits<char>>>(int, FormatStringHelperImpl<std::type_identity<char const*>::type, std::type_identity<char const*>::type, std::type_identity<String>::type, std::type_identity<long&>::type, std::type_identity<String>::type, std::type_identity<char const*>::type, std::type_identity<std::basic_string_view<char, std::char_traits<char>>>::type>, char const*&&, char const*&&, String&&, long&, String&&, char const*&&, std::basic_string_view<char, std::char_traits<char>>&&) @ 0x0000000014435b3d in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
6. /home/ubuntu/depot/ch-pro/src/Common/MemoryTracker.cpp:339: MemoryTracker::allocImpl(long, bool, MemoryTracker*, double) @ 0x00000000144340b0 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
7. /home/ubuntu/depot/ch-pro/src/Common/MemoryTracker.cpp:397: MemoryTracker::allocImpl(long, bool, MemoryTracker*, double) @ 0x0000000014434402 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
8. /home/ubuntu/depot/ch-pro/src/Common/CurrentMemoryTracker.cpp:58: CurrentMemoryTracker::allocImpl(long, bool) @ 0x00000000143bb7db in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
9. /home/ubuntu/depot/ch-pro/src/Common/CurrentMemoryTracker.cpp:90: CurrentMemoryTracker::alloc(long) @ 0x00000000143bb9e1 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
10. /home/ubuntu/depot/ch-pro/src/Common/Allocator.h:161: Allocator<false, false>::realloc(void*, unsigned long, unsigned long, unsigned long) @ 0x00000000143b5eba in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
11. /home/ubuntu/depot/ch-pro/src/Common/PODArray.h:165: void DB::PODArrayBase<1ul, 4096ul, Allocator<false, false>, 63ul, 64ul>::realloc<>(unsigned long) @ 0x000000000b667142 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
12. /home/ubuntu/depot/ch-pro/src/Common/PODArray.h:0: void DB::PODArrayBase<1ul, 4096ul, Allocator<false, false>, 63ul, 64ul>::resize<>(unsigned long) @ 0x000000000b666ee6 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
13. /home/ubuntu/depot/ch-pro/src/Columns/ColumnString.h:147: DB::ColumnString::insertFrom(DB::IColumn const&, unsigned long) @ 0x000000001f0eaaff in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
14. /home/ubuntu/depot/ch-pro/src/Columns/IColumn.h:179: DB::IColumn::insertManyFrom(DB::IColumn const&, unsigned long, unsigned long) @ 0x000000000b60192b in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
15. /home/ubuntu/depot/ch-pro/src/Interpreters/MergeJoin.cpp:404: DB::(anonymous namespace)::copyRightRange(DB::Block const&, DB::Block const&, std::vector<COW<DB::IColumn>::mutable_ptr<DB::IColumn>, std::allocator<COW<DB::IColumn>::mutable_ptr<DB::IColumn>>>&, unsigned long, unsigned long) @ 0x000000001e999757 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
16. /home/ubuntu/depot/ch-pro/src/Interpreters/MergeJoin.cpp:432: bool DB::(anonymous namespace)::joinEquals<true>(DB::Block const&, DB::Block const&, DB::Block const&, std::vector<COW<DB::IColumn>::mutable_ptr<DB::IColumn>, std::allocator<COW<DB::IColumn>::mutable_ptr<DB::IColumn>>>&, std::vector<COW<DB::IColumn>::mutable_ptr<DB::IColumn>, std::allocator<COW<DB::IColumn>::mutable_ptr<DB::IColumn>>>&, DB::MergeJoinEqualRange&, unsigned long) @ 0x000000001e997d86 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
17. /home/ubuntu/depot/ch-pro/src/Interpreters/MergeJoin.cpp:892: bool DB::MergeJoin::leftJoin<true>(DB::MergeJoinCursor&, DB::Block const&, DB::MergeJoin::RightBlockInfo&, std::vector<COW<DB::IColumn>::mutable_ptr<DB::IColumn>, std::allocator<COW<DB::IColumn>::mutable_ptr<DB::IColumn>>>&, std::vector<COW<DB::IColumn>::mutable_ptr<DB::IColumn>, std::allocator<COW<DB::IColumn>::mutable_ptr<DB::IColumn>>>&, unsigned long&) @ 0x000000001e9b2a7d in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
18. /home/ubuntu/depot/ch-pro/src/Interpreters/MergeJoin.cpp:793: void DB::MergeJoin::joinSortedBlock<false, true>(DB::Block&, std::shared_ptr<DB::ExtraBlock>&) @ 0x000000001e99b738 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
19. /home/ubuntu/depot/ch-pro/src/Interpreters/MergeJoin.cpp:733: DB::MergeJoin::joinBlock(DB::Block&, std::shared_ptr<DB::ExtraBlock>&) @ 0x000000001e997512 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
20. /home/ubuntu/depot/ch-pro/src/Processors/Transforms/JoiningTransform.cpp:206: DB::JoiningTransform::readExecute(DB::Chunk&) @ 0x00000000208ca1e3 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
21. /home/ubuntu/depot/ch-pro/src/Processors/Transforms/JoiningTransform.cpp:191: DB::JoiningTransform::transform(DB::Chunk&) @ 0x00000000208c9f4e in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
22. /home/ubuntu/depot/ch-pro/src/Processors/Transforms/JoiningTransform.cpp:125: DB::JoiningTransform::work() @ 0x00000000208c985d in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
23. /home/ubuntu/depot/ch-pro/src/Processors/Executors/ExecutionThreadContext.cpp:47: DB::executeJob(DB::ExecutingGraph::Node*, DB::ReadProgressCallback*) @ 0x00000000203e5263 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
24. /home/ubuntu/depot/ch-pro/src/Processors/Executors/ExecutionThreadContext.cpp:95: DB::ExecutionThreadContext::executeTask() @ 0x00000000203e4fa0 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
25. /home/ubuntu/depot/ch-pro/src/Processors/Executors/PipelineExecutor.cpp:251: DB::PipelineExecutor::executeStepImpl(unsigned long, std::atomic<bool>*) @ 0x00000000203ca041 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
26. /home/ubuntu/depot/ch-pro/src/Processors/Executors/PipelineExecutor.cpp:217: DB::PipelineExecutor::executeSingleThread(unsigned long) @ 0x00000000203ca357 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
27. /home/ubuntu/depot/ch-pro/src/Processors/Executors/PipelineExecutor.cpp:341: DB::PipelineExecutor::spawnThreads()::$_0::operator()() const @ 0x00000000203cb098 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
28. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/__functional/invoke.h:394: decltype(std::declval<DB::PipelineExecutor::spawnThreads()::$_0&>()()) std::__invoke[abi:v15000]<DB::PipelineExecutor::spawnThreads()::$_0&>(DB::PipelineExecutor::spawnThreads()::$_0&) @ 0x00000000203caff5 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
29. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/__functional/invoke.h:480: void std::__invoke_void_return_wrapper<void, true>::__call<DB::PipelineExecutor::spawnThreads()::$_0&>(DB::PipelineExecutor::spawnThreads()::$_0&) @ 0x00000000203cafd5 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
30. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/__functional/function.h:235: std::__function::__default_alloc_func<DB::PipelineExecutor::spawnThreads()::$_0, void ()>::operator()[abi:v15000]() @ 0x00000000203cafb5 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse
31. /home/ubuntu/depot/ch-pro/contrib/llvm-project/libcxx/include/__functional/function.h:716: void std::__function::__policy_invoker<void ()>::__call_impl<std::__function::__default_alloc_func<DB::PipelineExecutor::spawnThreads()::$_0, void ()>>(std::__function::__policy_storage const*) @ 0x00000000203caf80 in /home/ubuntu/depot/ch-pro/build-debug/programs/clickhouse

```

MergeJoin::leftJoin负责partial merge join的LEFT JOIN运算的实现，最终会调用::copyRightRange方法，复制右边表的内容。在此期间IColumn::insertFrom会被调用，这会涉及到调用realloc重分配内存。在这个点上可能会发生内存超限的异常。

## LEFT ANY JOIN

LEFT ANY JOIN走不同代码分支，该代码分支**忽略**了setting配置max_joined_block_size_rows，因此即使调小了max_joined_block_size_rows，LEFT ANY JOIN依然会产生内存超限异常。

## “auto”的内存问题

根据文档，设置join_algorithm='auto' 以启用自动切换JOIN算法的模式，ClickHouse先尝试用hash join算法，然后在内存超过阈值的情况下切换到partial merge join算法。阈值有两个：max_bytes_in_join和max_rows_in_join，指定hash join算法创建的hash table的最大的占用内存字节数和行数。两个阈值只要有一个超过就算是超过阈值。

但是在实践中发现，原先的尝试的hash join所消耗的内存仍然没有释放，导致在切换到partial merge join后在原本不应该超限的情况下仍然产生内存超限的异常。参考以下示例：

```sql
SELECT
    t1.id AS id,
    t2.value AS value
FROM big_columns_join.big_columns_table AS t1
LEFT JOIN big_columns_join.dim_table1 AS t2 ON t1.fk = t2.id
SETTINGS join_algorithm = 'auto', max_bytes_in_join = '15G'
FORMAT `Null`;
```

运行日志如下：

```bash
2024.01.19 11:31:40.580304 [ 3654586 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> JoiningTransform: Before join block: 'id UInt64 UInt64(size = 0), fk UInt64 UInt64(size = 0)'
2024.01.19 11:31:40.580692 [ 3654586 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> JoiningTransform: After join block: 'id UInt64 UInt64(size = 0), fk UInt64 UInt64(size = 0), value String String(size = 0)'
2024.01.19 11:31:40.680382 [ 3654935 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 1.01 GiB.
2024.01.19 11:31:40.753297 [ 3654852 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 2.01 GiB.
2024.01.19 11:31:40.833103 [ 3654862 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 3.01 GiB.
2024.01.19 11:31:40.905190 [ 3654854 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 4.01 GiB.
2024.01.19 11:31:41.047932 [ 3654900 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 6.01 GiB.
2024.01.19 11:31:41.117219 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 7.00 GiB.
2024.01.19 11:31:41.198586 [ 3654851 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 8.01 GiB.
2024.01.19 11:31:41.272147 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 9.00 GiB.
2024.01.19 11:31:41.342679 [ 3654935 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 10.00 GiB.
2024.01.19 11:31:41.416512 [ 3654851 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 11.01 GiB.
2024.01.19 11:31:41.486753 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 12.01 GiB.
2024.01.19 11:31:41.560137 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 13.00 GiB.
2024.01.19 11:31:41.630755 [ 3654862 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 14.01 GiB.
2024.01.19 11:31:41.633781 [ 3654935 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Trace> HashJoin: (0x7f8299383918) Join data is being released, 15001390080 bytes and 8940 rows in hash table
2024.01.19 11:31:41.666781 [ 3654935 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MergeJoin: Joining keys: left [fk], right [t2.id]
2024.01.19 11:31:41.666943 [ 3654935 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Trace> HashJoin: (0x7f8299383918) Join data has been already released
2024.01.19 11:31:41.764950 [ 3654852 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 15.00 GiB.
2024.01.19 11:31:42.024590 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 16.14 GiB.
2024.01.19 11:31:42.221853 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 17.64 GiB.
2024.01.19 11:31:42.481914 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 19.64 GiB.
2024.01.19 11:31:43.001865 [ 3654941 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Debug> MemoryTracker: Current memory usage (for query): 23.64 GiB.
2024.01.19 11:31:44.610495 [ 3654586 ] {506df1da-8f03-480a-b263-a83a5b8277f0} <Error> executeQuery: Code: 241. DB::Exception: Memory limit (for query) exceeded: would use 31.64 GiB (attempt to allocate chunk of 17179869184 bytes), maximum: 27.94 GiB.: While executing MergeSortingTransform: While executing FillingRightJoinSide. (MEMORY_LIMIT_EXCEEDED) (version 23.8.3.1.alex-build-debug) (from [::ffff:127.0.0.1]:33076) (in query: select t1.id as id, t2.value as `value` from `big_columns_join`.`big_columns_table` as t1 left join `big_columns_join`.`dim_table1` as t2 on t1.fk = t2.id settings join_algorithm='auto',max_bytes_in_join=15000000000 format Null;), Stack trace (when copying this message, always include the lines below):
```

从日志可以看到，首先采用了hash join，然后内存使用量一路飙升到15GiB的时候切换到了partial merge join（日志第17行），原先hash join所使用的15GiB内存将被释放（日志第16行）。最后hash join的内存被释放（日志第18行），但是实际内存使用量并没有减少，仍然从15GiB开始继续增长。留给partial merge join的可用内存不多，因此很快产生内存超限MEMORY_LIMIT_EXCEEDED异常。

目前找到的解决办法只能是调小阈值，但是这样导致原本可以使用hash join的情况下却被迫切换到相对慢速的partial merge join。影响整体性能。
