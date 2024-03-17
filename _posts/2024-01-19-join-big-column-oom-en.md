# OOM problem of JOIN caused by "large column" in ClickHouse

A "large column" refers to a column with a very large amount of data in each row, usually more than 100KiB. Such a column causes an OOM(out of memory) exception for the JOIN (usually LEFT JOIN and INNER JOIN).

## JOIN algorithms

There are two kinds of JOIN algorithms discussed here: `partial merge join` and `hash join`. The `direct join` algorithm is beyond the scope of this article.

OOM exceptions generally look like this:

```
2024.01.16 17:04:30.084819 [ 3654586 ] {52653888-f266-443a-beba-348c66a88e60} <Error> TCPHandler: Code: 241. DB::Exception: Memory limit (for query) exceeded: would use 33.61 GiB (attempt to allocate chunk of 34359738368 bytes), maximum: 27.94 GiB.: While executing JoiningTransform. (MEMORY_LIMIT_EXCEEDED), Stack trace (when copying this message, always include the lines below):
```

## Test data

For analyzing the OOM problem for JOIN operations of "large column", we prepare the special tables for test data before hand.

The test data is two tables with N-1 relationship:

table1 - N tables, 10W rows, two columns: id, fk (foreign key)

table2 - 1 table, 1W rows, two columns: id, value (value is an overly long string column, each cell is about 500KiB in size)

The query to create test data is as follows:

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

## Test query

The test query is a simple LEFT JOIN.

```sql
select
    *
from
    `big_columns_join`.`big_columns_table`
    left join `big_columns_join`.`dim_table1` on `big_columns_join`.`big_columns_table`.`fk` = `big_columns_join`.`dim_table1`.`id`
format Null;
```

## Hash join algorithm

Before running the test query, set the `max_joined_block_size_rows` threshold.

```sql
set join_algorithm = 'hash';
set max_joined_block_size_rows=10000;  -- lower threshold，need less memory。
-- run test query
```

The test results are:

**When the JOIN algorithm is "hash join"**, no matter what the threshold size of `max_joined_block_size_rows` is, the OOM exception always happen.

The error message is as follows:

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

The template function `joinRightColumns` looks up the row of the corresponding right table based on the JOIN key, finds the `row_number` corresponding to the row, and then completes the JOIN result of the row by calling `appendFromBlock (block, row_number)`.

`appendFromBlock` calls `IColumn:: insertFrom` to insert one line at a time. Here's a problem: `ColumnString`'s content growth is line-by-line, which involves multiple memory reallocations and incurs a large amount of memory copy.

## Parital merge join

Before running the test query, set the `max_joined_block_size_rows` threshold.

```sql
set join_algorithm = 'parital_merge';
set max_joined_block_size_rows=10000;  -- lower threshold, need less memory.
-- run test query first time.

set max_joined_block_size_rows=1000000;  -- higher threshold, need more memory.
-- run test query second time.
```

The test results are:

**When the JOIN algorithm is "parental merge join"**, decreasing the threshold of `max_joined_block_size_rows` could avoid OOM exception.

When `max_joined_block_size_rows` is relatively large (the second test query run in the above example), the OOM exception occurs.

Error message:

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

`MergeJoin::leftJoin` is responsible for implementing the LEFT JOIN operation of partial merge join, which eventually calls `::copyRightRange`, copying the contents of the table on the right. During this time, `IColumn::insertFrom` is called, which involves calling `realloc` to reallocate memory. At this point, an OOM exception may occur.

## LEFT ANY JOIN

LEFT ANY JOIN takes a different branch of code that **overlooked** the setting `max_joined_block_size_rows`, so even if `max_joined_block_size_rows` is reduced, LEFT ANY JOIN still generates a memory overrun exception.

## Memory exeeds when choose join algorithm “auto”

According to the documentation, settting join_algorithm to 'auto ' enables automatic switching of the JOIN algorithm, it tries the "hash join" algorithm first, and then switch to the "partial merge join" algorithm if the memory exceeds the threshold. There are two thresholds, `max_bytes_in_join` and `max_rows_in_join`, which specify the maximum number of bytes of memory occupied by the hash table created by the "hash join" algorithm and the maximum nubmer of rows of the hash table. As long as one of the two thresholds exceeds, it is considered as exceeding the threshold.

However, in practice it is found that the memory consumed by the original hash join has not been released, which leads to the OOM exception after switching to partial merge join, even if it should not happen(memory consumption of partial merge join actually does not exceed the total memory). Refer to the following example:

```sql
SELECT
    t1.id AS id,
    t2.value AS value
FROM big_columns_join.big_columns_table AS t1
LEFT JOIN big_columns_join.dim_table1 AS t2 ON t1.fk = t2.id
SETTINGS join_algorithm = 'auto', max_bytes_in_join = '15G'
FORMAT `Null`;
```

The ClickHouse sever log is as follows：

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

As you can see from the log, the "hash join" algorithm was first adopted, and then the "partial merge join" algorithm was switched when the memory usage reached to 15GiB (log line 17), and the 15GiB memory used by the original "hash join" algorithm will be released (log line 16). Finally, the memory of the hash join was said be freed (line 18 of the log), but the actual memory usage did not decrease, and continued to grow from 15GiB. There is not much free memory left for the "partial merge join" algorithm, so a memory overrun MEMORY_LIMIT_EXCEEDED exception is quickly thrown.

At present, the solution can only be to reduce the threshold, but this leads to the forced switch to the relatively slow partial merge join when the hash join can be used. It affects overall performance.
