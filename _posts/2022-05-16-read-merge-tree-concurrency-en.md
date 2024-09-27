# Implementation logic for parallel reading of MergeTree tables



## Preface

The MergeTree table engine is the most commonly used table engine in Clickhouse. Queries must first read data from the table, and there is no doubt that multi-threaded parallel reading, especially parallel reading from multiple disks, is the most efficient. This article introduces and analyzes the code implementation of parallel reading data on the MergeTree table engine.



## Processor class for reading MergeTree tables

The entry point for reading MergeTree tables is `MergeTreeDataSelectExecutor`, from which all SELECT statements for MergeTree tables are executed. This executor generates the query step `ReadFromMergeTree`, which is part of the query plan. They are a higher-level abstraction of the query execution network, from which the specific query execution network is generated.

The query step `ReadFromMergeTree` chooses whether to generate a multi-stream query pipeline or a single-stream query pipeline based on whether the current query is expected to generate multiple data streams or a single data stream and the nature of the query. Generating a multi-stream query is done by calling the function `readFromPool()`, while generating a single-stream query is done by calling the function `readInOrder()`.

Here are two examples of execution pipelines:



**Multi-stream pipeline**

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

`MergeTreeThread` is implemented by class `MergeTreeThreadSelectProcessor`.



**Single data stream**

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

`MergeTreeInOrder` is implemented by the class `MergeTreeInOrderSelectProcessor`.



The explain results show that `MergeTreeThread` runs in four threads at the same time, while `MergeTreeInOrder` runs in a single thread. Since `MergeTreeThread` runs in multiple threads, it requires a task allocation mechanism, which is implemented by `MergeTreeReadPool`.



## MergeTreeReadPool

The `MergeTreeReadPool` organizes and distributes the total number of read tasks passed in during construction for performance optimization purposes. It is shared among multiple threads as a task pool.

```cpp
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



The important member variables and member functions are as follows:

| Type | Name | Meaning |
| -------- | ----------------- | ------------------------------------------------------------ |
| Member variable | parts_ranges | Specifies all the parts involved in the read operation and the range of marks within each part (the MergeTree table engine uses marks to index column data files). |
| Member variable | threads_tasks | The read tasks assigned to each thread. |
| Member variable | data | Points to the MergeTree storage, an `IStorage` object. |
| Member function | fillPerPartInfo | Collects and organizes information about the parts, obtaining information such as the total number of marks, whether it is remote data, and the number of marks in each part. |
| Member function | fillPerThreadInfo | Distributes the reading tasks according to the information collected by `fillPerPartInfo`, trying to keep the workload of each thread as even as possible. <br />At the same time, it tries to let a thread read an entire part, and tries to let different threads access different disks at the same time, with the aim of parallel reading as much as possible,<br />making full use of the capabilities of each thread. |
| Member function | getTask: Each instance of MergeTreeThread that reads data obtains tasks from the pool represented by MergeTreeReadPool. |

Dependency order: `fillPerPartInfo()` collects and saves part information, `fillPerThreadInfo()` allocates reading tasks based on this information, and `MergeTreeThread` obtains tasks and executes them via the `getTask()` function.



## Other processors that read the MergeTree

The class inheritance structure of processors that read the MergeTree is as follows:

```
MergeTreeBaseSelectProcessor
    |- (Processor: MergeTreeThread) MergeTreeThreadSelectProcessor
    |- (抽象类) MergeTreeSelectProcessor
        |- (Processor: MergeTreeReverse) MergeTreeReverseSelectProcessor
        |- (Processor: MergeTreeInOrder) MergeTreeInOrderSelectProcessor
```

`MergeTreeBaseSelectProcessor` is the base class for all processors. `MergeTreeReverseSelectProcessor` is similar to `MergeTreeInOrderSelectProcessor`, except that the order of reading is reversed.



## Optimization options that affect the execution pipeline



optimize_read_in_order - When the ORDER BY keyword specified when building the MergeTree table is queried, use `MergeTreeInOrder`.

optimize_aggregation_in_order - When the ORDER BY keyword specified when building the MergeTree table is queried, use `MergeTreeInOrder`.



## Other processors that read MergeTree

`MergeTreeSequentialSource` is a lightweight class for reading a single part. It is currently only used by the `MergeTask` class, which does the background merge operation.

```cpp
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
