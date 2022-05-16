# 并行读取MergeTree表的实现逻辑



## 前言

MergeTree表引擎是Clickhouse最主要用的表引擎。在查询中首先要从表中读取数据，而无疑多线程并行读取，尤其是并行地从多个磁盘中读取数据是最为高效的。本文就介绍和分析MergeTree表引擎上并行读取数据的代码实现。



## 读取MergeTree表的Processor类

读取MergeTree表的入口是`MergeTreeDataSelectExecutor`，所有关于MergeTree表的SELECT语句的执行都是从这里进去。这个执行器生成查询步骤`ReadFromMergeTree`，查询步骤是查询计划的一部分，它们是查询执行网络的更高一层的抽象，由它们生成具体的查询执行网络。

查询步骤`ReadFromMergeTree`根据是否当前查询要产生多个数据流还是单个数据流以及查询的性质来选择生成多数据流查询管线还是单数据流查询管线。生成多数据流通过调用函数`readFromPool()`完成；而生成单数据流通过调用函数`readInOrder()`完成。

下面是两个执行管线的例子：



**多数据流**

```sql
DESKTOP-UBNBIFE.localdomain :) explain pipeline select * from events;

┌─explain───────────────────────┐
│ (Expression)                  │
│ ExpressionTransform × 4       │
│   (SettingQuotaAndLimits)     │
│     (ReadFromMergeTree)       │
│     MergeTreeThread × 4 0 → 1 │
└───────────────────────────────┘
```

`MergeTreeThread`是由类`MergeTreeThreadSelectProcessor`实现。



**单数据流**

```sql
DESKTOP-UBNBIFE.localdomain :) explain pipeline select * from events settings max_threads=1;

┌─explain────────────────────┐
│ (Expression)               │
│ ExpressionTransform        │
│   (SettingQuotaAndLimits)  │
│     (ReadFromMergeTree)    │
│     MergeTreeInOrder 0 → 1 │
└────────────────────────────┘
```

`MergeTreeInOrder`是由类`MergeTreeInOrderSelectProcessor`实现。



由explain的结果可以看看出`MergeTreeThread`是同时四个线程跑，而`MergeTreeInOrder`是单线程跑。由于`MergeTreeThread`是多个线程跑，所以需要一个任务分配机制，这个任务分配机制就是由`MergeTreeReadPool`来完成。



## MergeTreeReadPool

`MergeTreeReadPool`根据构造时传入的总的读取数据的任务，按照性能优化的目的去组织和分配，本身是作为一个任务池在多个线程中共享。

```c++
/**   Provides read tasks for MergeTreeThreadSelectBlockInputStream`s in fine-grained batches, allowing for more
 *    uniform distribution of work amongst multiple threads. All parts and their ranges are divided into `threads`
 *    workloads with at most `sum_marks / threads` marks. Then, threads are performing reads from these workloads
 *    in "sequential" manner, requesting work in small batches. As soon as some thread has exhausted
 *    it's workload, it either is signaled that no more work is available (`do_not_steal_tasks == false`) or
 *    continues taking small batches from other threads' workloads (`do_not_steal_tasks == true`).
 */
class MergeTreeReadPool : private boost::noncopyable
{
public:
    /** Pull could dynamically lower (backoff) number of threads, if read operation are too slow.
      * Settings for that backoff.
      */
    struct BackoffSettings
    {
        // ...
    };

    BackoffSettings backoff_settings;

private:
    /** State to track numbers of slow reads.
      */
    struct BackoffState
    {
        // ...
    };

    BackoffState backoff_state;

public:
    MergeTreeReadTaskPtr getTask(const size_t min_marks_to_read, const size_t thread, const Names & ordered_names);

    /** Each worker could call this method and pass information about read performance.
      * If read performance is too low, pool could decide to lower number of threads: do not assign more tasks to several threads.
      * This allows to overcome excessive load to disk subsystem, when reads are not from page cache.
      */
    void profileFeedback(const ReadBufferFromFileBase::ProfileInfo info);

    Block getHeader() const;

private:
    std::vector<size_t> fillPerPartInfo(const RangesInDataParts & parts);

    void fillPerThreadInfo(
        const size_t threads, const size_t sum_marks, std::vector<size_t> per_part_sum_marks,
        const RangesInDataParts & parts, const size_t min_marks_for_concurrent_read);

    const MergeTreeData & data;
    StorageMetadataPtr metadata_snapshot;
    const Names column_names;
    bool do_not_steal_tasks;
    bool predict_block_size_bytes;
    std::vector<NameSet> per_part_column_name_set;
    std::vector<NamesAndTypesList> per_part_columns;
    std::vector<NamesAndTypesList> per_part_pre_columns;
    std::vector<char> per_part_should_reorder;
    std::vector<MergeTreeBlockSizePredictorPtr> per_part_size_predictor;
    PrewhereInfoPtr prewhere_info;

    struct Part
    {
        MergeTreeData::DataPartPtr data_part;
        size_t part_index_in_query;
    };

    std::vector<Part> parts_with_idx;

    struct ThreadTask
    {
        struct PartIndexAndRange
        {
            size_t part_idx;
            MarkRanges ranges;
        };

        std::vector<PartIndexAndRange> parts_and_ranges;
        std::vector<size_t> sum_marks_in_parts;
    };

    std::vector<ThreadTask> threads_tasks;

    std::set<size_t> remaining_thread_tasks;

    RangesInDataParts parts_ranges;

    mutable std::mutex mutex;

    Poco::Logger * log = &Poco::Logger::get("MergeTreeReadPool");

    std::vector<bool> is_part_on_remote_disk;

    bool suffled_in_partition;
};

```



这里重要的成员变量和成员函数如下：

| 类型     | 名称              | 含义                                                         |
| -------- | ----------------- | ------------------------------------------------------------ |
| 成员变量 | parts_ranges      | 指定读取操作涉及到的所有parts，以及每个part内部的mark的范围（MergeTree表引擎是用mark来索引列数据文件）。 |
| 成员变量 | threads_tasks     | 为每个线程分配好的读取任务。                                 |
| 成员变量 | data              | 指向MergeTree的存储，`IStorage`对象。                        |
| 成员函数 | fillPerPartInfo   | 收集并组织part的信息，得到总的mark数、是否是远程数据、每个part的mark数等信息。 |
| 成员函数 | fillPerThreadInfo | 根据`fillPerPartInfo`收集到的信息分配读取任务，尽量让每个线程的工作压力均匀。<br />同时尽量让一个线程读完一整个part，并尽量让不同线程同时访问不同的磁盘，目的是尽量地并行读取，<br />充分利用每一个线程的能力。 |
| 成员函数 | getTask           | 每个读取数据的`MergeTreeThread`的实例从`MergeTreeReadPool`表示的池子里获取任务。 |

依赖次序为： `fillPerPartInfo()` 收集并保存part信息，`fillPerThreadInfo()`根据这些信息分配读取任务，`MergeTreeThread`通过`getTask()`函数获取任务并执行。



## 其他读取MergeTree的Processor

读取MergeTree的Processor的类继承结构如下所示：

```
MergeTreeBaseSelectProcessor
    |- (Processor: MergeTreeThread) MergeTreeThreadSelectProcessor
    |- (抽象类) MergeTreeSelectProcessor
        |- (Processor: MergeTreeReverse) MergeTreeReverseSelectProcessor
        |- (Processor: MergeTreeInOrder) MergeTreeInOrderSelectProcessor
```

`MergeTreeBaseSelectProcessor`是所有的基类，`MergeTreeReverseSelectProcessor`跟`MergeTreeInOrderSelectProcessor`类似，区别是读取顺序是逆序。



## 影响执行管线的优化选项



optimize_read_in_order  -  在查询ORDER BY的关键字是建MergeTree表的时候指定的ORDER BY关键字时，用`MergeTreeInOrder`。

optimize_aggregation_in_order  -   在查询ORDER BY的关键字是建MergeTree表的时候指定的ORDER BY关键字时，用`MergeTreeInOrder`。



## 其他读MergeTree的Processor

`MergeTreeSequentialSource` 是一个轻量级的用于读取一个单独part的类，目前只有做后台merge操作的`MergeTask`类用到。

```c++
/// Lightweight (in terms of logic) stream for reading single part from MergeTree
class MergeTreeSequentialSource : public SourceWithProgress
{
public:
    MergeTreeSequentialSource(
        const MergeTreeData & storage_,
        const StorageMetadataPtr & metadata_snapshot_,
        MergeTreeData::DataPartPtr data_part_,
        Names columns_to_read_,
        bool read_with_direct_io_,
        bool take_column_types_from_storage,
        bool quiet = false);

    ~MergeTreeSequentialSource() override;

    String getName() const override { return "MergeTreeSequentialSource"; }

    size_t getCurrentMark() const { return current_mark; }

    size_t getCurrentRow() const { return current_row; }

protected:
    Chunk generate() override;

private:

    const MergeTreeData & storage;
    StorageMetadataPtr metadata_snapshot;

    /// Data part will not be removed if the pointer owns it
    MergeTreeData::DataPartPtr data_part;

    /// Columns we have to read (each Block from read will contain them)
    Names columns_to_read;

    /// Should read using direct IO
    bool read_with_direct_io;

    Poco::Logger * log = &Poco::Logger::get("MergeTreeSequentialSource");

    std::shared_ptr<MarkCache> mark_cache;
    using MergeTreeReaderPtr = std::unique_ptr<IMergeTreeReader>;
    MergeTreeReaderPtr reader;

    /// current mark at which we stop reading
    size_t current_mark = 0;

    /// current row at which we stop reading
    size_t current_row = 0;

private:
    /// Closes readers and unlock part locks
    void finish();
};

```
