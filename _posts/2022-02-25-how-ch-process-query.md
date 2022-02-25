# Clickhouse执行处理查询语句（包括DDL，DML）的过程

## 总体过程

1. 启动线程处理客户端接入的TCP连接；
2. 接收请求数据，交给函数`executeQueryImpl()`处理；
3. `executeQueryImpl()`处理查询的SQL语句字符串；
4. 生成`QueryPipeline`实例，`QueryPipeline`实例可以包含数据也可以仅包含如何读取数据的信息；
5. 通过`*PipelineExecutor`例如`PullingAsyncPipelineExecutor`执行`QueryPipeline`实例，获得数据结果。

```
PullingAsyncPipelineExecutor::pull() -> PipelineExecutor::execute()
```

## executeQueryImpl()函数过程

executeQueryImpl()是整个处理流程的重点，她包含如下几项：

1. 解析SQL语句，生成语法树AST；
2. 预处理AST
   1. AST参数替换成实际值
   2. With 子句替换
   3. 各种visitor
   4. 标准化AST
   5. 处理带select的insert语句和不带select的insert语句
3. 通过工厂方法获得对应的解释器对象  （InterpreterFactory.cpp 里面找到所有的解释器）
4. 执行解释器的execute()方法，该方法是所有解释器的基类`IInterpreter`定义的函数，返回`BlockIO`实例，其中包含的最重要的是`QueryPipeline`的实例。

`BlockIO`是一个IO的抽象，可输出（select类查询），也可输入（insert类查询），参考以下`IInterpreter`的定义。

```C++
class IInterpreter
{
public:
     /** For queries that return a result (SELECT and similar), sets in BlockIO a stream from which you can read this result.
      * For queries that receive data (INSERT), sets a thread in BlockIO where you can write data.
      * For queries that do not require data and return nothing, BlockIO will be empty.
      */
    virtual BlockIO execute() = 0;
    ......
    ......
}
```

`BlockIO`包含query pipeline，process list和callbacks，其中query pipeline是数据的流动管道。

1. Select查询类的解释器例如`InterpreterSelectQuery`会先构建一个query plan，再从query plan上构建query pipeline。
2. `PullingAsyncPipelineExecutor::pull()` 或者 `PullingPipelineExecutor` 拉取`QueryPipeline`管道的数据。



## 解析查询语句

`parseQuery()` 函数接收SQL语句字符串和parser，调用`parseQueryAndMovePosition()`，最终调用`tryParseQuery()`完成解析返回AST树作为结果。



参数`allow_multi_statements`用于控制是否解析多个SQL语句，这个对于我目前的任务非常重要。

```C++	
ASTPtr parseQueryAndMovePosition(
    IParser & parser,
    const char * & pos,
    const char * end,
    const std::string & query_description,
    bool allow_multi_statements,
    size_t max_query_size,
    size_t max_parser_depth)
{
    ... ...
    ... ...
}
```

过程大致分为两步：

1. 将SQL字符串转成token集合
2. parser通过`TokenIterator`遍历token集合，更新AST结果

最终的AST树即是解析之后的结果。

每个parser代表一种语法模式，一个parser可以调用另外多个parser。以下是所有的parser。

```ruby
  ^IParser$
  └── IParser
      └── IParserBase
          ├── IParserColumnDeclaration
          ├── IParserNameTypePair
          ├── ParserAdditiveExpression
          ├── ParserAlias
          ├── ParserAlterCommand
          ├── ParserAlterCommand
          ├── ParserAlterCommandList
          ├── ParserAlterQuery
          ├── ParserAlterQuery
          ├── ParserAlwaysFalse
          ├── ParserAlwaysTrue
          ├── ParserArray
          ├── ParserArrayElementExpression
          ├── ParserArrayJoin
          ├── ParserArrayOfLiterals
          ├── ParserAssignment
          ├── ParserAsterisk
          ├── ParserAttachAccessEntity
          ├── ParserBackupQuery
          ├── ParserBetweenExpression
          ├── ParserBool
		  ...... .......
```

AST语法树由`IAST`的派生实现类的一组实例组成

```ruby	
  ^IAST$
  └── IAST
      ├── ASTAlterCommand
      ├── ASTAlterCommand
      ├── ASTAlterQuery
      ├── ASTArrayJoin
      ├── ASTAssignment
      ├── ASTAsterisk
      ├── ASTBackupQuery
      ├── ASTColumnDeclaration
      ├── ASTColumns
      ├── ASTColumnsElement
      ├── ASTColumnsMatcher
	  ... ...
```



## 构建Query Pipeline

`IInterpreter::execute() `返回的结果 `BlockIO `实例中主要组成部分就是`QueryPipeline`实例。可以说是由解释器来构建Query Pipeline的，但是每种解释器的构建Query Pipeline的方式不同。Select类查询（最普遍的查询）是先生成Query Plan，做优化后，再生成最终的Query Pipeline。

`IInterpreter::execute()`是解释器的核心，它会根据三种情况返回`BlockIO`实例作为结果。

```C%2B%2B
/** Interpreters interface for different queries.
  */
class IInterpreter
{
public:
    /** For queries that return a result (SELECT and similar), sets in BlockIO a stream from which you can read this result.
      * For queries that receive data (INSERT), sets a thread in BlockIO where you can write data.
      * For queries that do not require data and return nothing, BlockIO will be empty.
      */
      virtual BlockIO execute() = 0;
 }
```



### 构建select 类查询的Query Plan

而Select查询类的解释器比如 `InterpreterSelectQuery`的execute() 方法会首先生成`QueryPlan`实例，在优化的策略下由`QueryPlan`实例去生成`QueryPipeline`实例。这也是为什么`explain plan` 命令只能用于select类型的查询中。注意这里的 `InterpreterSelectQuery::executeImpl()` 并不是 `InterpreterSelectQuery::execute()` 的实现，其实是 `InterpreterSelectQuery::buildQueryPlan()` 的实现。

以下注释反映出代码主要逻辑：

```C%2B%2B
void InterpreterSelectQuery::executeImpl(QueryPlan & query_plan, std::optional<Pipe> prepared_pipe)
{
    /** Streams of data. When the query is executed in parallel, we have several data streams.
     *  If there is no GROUP BY, then perform all operations before ORDER BY and LIMIT in parallel, then
     *  if there is an ORDER BY, then glue the streams using ResizeProcessor, and then MergeSorting transforms,
     *  if not, then glue it using ResizeProcessor,
     *  then apply LIMIT.
     *  If there is GROUP BY, then we will perform all operations up to GROUP BY, inclusive, in parallel;
     *  a parallel GROUP BY will glue streams into one,
     *  then perform the remaining operations with one resulting stream.
     */
 } 
```



### Query Plan Step

Query Plan Step是Query Plan的组成部分，由基类`IQueryPlanStep`和其派生实现类表示。

`QueryPlan`实例主要由若干以树（非二叉树）的形式组织起来的IQueryPlanStep的实现类的实例构成。每个IQueryPlanStep的实现类的实例会为QueryPipeline产生并织入一组Processor，这步由 `updatePipeline()` 方法实现。

以下注释解释了其中的概要。

```C%2B%2B
    /// Add processors from current step to QueryPipeline.
    /// Calling this method, we assume and don't check that:
    ///   * pipelines.size() == getInputStreams.size()
    ///   * header from each pipeline is the same as header from corresponding input_streams
    /// Result pipeline must contain any number of streams with compatible output header is hasOutputStream(),
    ///   or pipeline should be completed otherwise.
    virtual QueryPipelineBuilderPtr updatePipeline(QueryPipelineBuilders pipelines, const BuildQueryPipelineSettings & settings) = 0;
```



### Select查询Pipeline生成实验

用以下数据表做实验：

```SQL
┌─statement───────────────────────────┐
│ CREATE TABLE default.cx1
(
    `eventId` Int64,
    `案例号` String,
    `金额` UInt8
)
ENGINE = MergeTree
ORDER BY (`案例号`, eventId)
SETTINGS index_granularity = 8192 │
└────────────────────────────────────┘
```

**最简单的SELECT**

```SQL
explain pipeline select * from cx1
┌─explain───────────────────────┐
│ (Expression)                  │ # query step 名字
│ ExpressionTransform × 4       │ # 4个 ExpressionTransform processor
│   (SettingQuotaAndLimits)     │ # query step 名字
│     (ReadFromMergeTree)       │
│     MergeTreeThread × 4 0 → 1 │ # MergeTreeThread的输入流0个，输出流1个
└───────────────────────────────┘
```

**带过滤条件和LIMIT的SELECT**

```SQL
explain pipeline header=1 select `案例号`, eventId from cx1 where eventId % 10 > 3 group by `案例号`, eventId limit 100
┌─explain─────────────────────────────────────────────────────────────┐
│ (Expression)                                                        │
│ ExpressionTransform                                                 │
│ Header: 案例号 String: 案例号 String String(size = 0)                │
│         eventId Int64: eventId Int64 Int64(size = 0)                │
│   (Limit)                                                           │
│   Limit                                                             │
│   Header: 案例号 String: 案例号 String String(size = 0)              │
│           eventId Int64: eventId Int64 Int64(size = 0)              │
│     (Aggregating)                                                   │
│     Resize 4 → 1   # 代表输入数据流是4个，合并后输出1个                │
│     Header: 案例号 String: 案例号 String String(size = 0)            │
│             eventId Int64: eventId Int64 Int64(size = 0)            │
│       AggregatingTransform × 4                                      │
│       Header: 案例号 String: 案例号 String String(size = 0)          │
│               eventId Int64: eventId Int64 Int64(size = 0)          │
│         StrictResize 4 → 4                                          │
│         Header × 4 : eventId Int64: eventId Int64 Int64(size = 0)   │
│                       案例号 String: 案例号 String String(size = 0)  │
│           (Expression)                                              │
│           ExpressionTransform × 4                                   │
│           Header: eventId Int64: eventId Int64 Int64(size = 0)      │
│                   案例号 String: 案例号 String String(size = 0)      │
│             (SettingQuotaAndLimits)                                 │
│               (ReadFromMergeTree)                                   │
│               MergeTreeThread × 4 0 → 1                             │
│               Header: eventId Int64: eventId Int64 Int64(size = 0)  │
│                       案例号 String: 案例号 String String(size = 0)  │
└─────────────────────────────────────────────────────────────────────┘
```

**带过滤条件、GROUP BY和LIMIT的SELECT**

```SQL
explain pipeline header=1 select `案例号`, eventId, avg(`金额`) from cx1 where eventId % 10 > 3 group by `案例号`, eventId limit 100
┌─explain──────────────────────────────────────────────────────────────┐
│ (Expression)                                                         │
│ ExpressionTransform                                                  │
│ Header: 案例号 String: 案例号 String String(size = 0)                 │
│         eventId Int64: eventId Int64 Int64(size = 0)                 │
│         avg(金额) Float64: avg(金额) Float64 Float64(size = 0)        │
│   (Limit)                                                            │
│   Limit                                                              │
│   Header: 案例号 String: 案例号 String String(size = 0)               │
│           eventId Int64: eventId Int64 Int64(size = 0)               │
│           avg(金额) Float64: avg(金额) Float64 Float64(size = 0)      │
│     (Aggregating)                                                    │
│     Resize 4 → 1                                                     │
│     Header: 案例号 String: 案例号 String String(size = 0)             │
│             eventId Int64: eventId Int64 Int64(size = 0)             │
│             avg(金额) Float64: avg(金额) Float64 Float64(size = 0)    │
│       AggregatingTransform × 4                                       │
│       Header: 案例号 String: 案例号 String String(size = 0)           │
│               eventId Int64: eventId Int64 Int64(size = 0)           │
│               avg(金额) Float64: avg(金额) Float64 Float64(size = 0)  │
│         StrictResize 4 → 4                                           │
│         Header × 4 : eventId Int64: eventId Int64 Int64(size = 0)    │
│                       案例号 String: 案例号 String String(size = 0)   │
│                       金额 UInt8: 金额 UInt8 UInt8(size = 0)          │
│           (Expression)                                               │
│           ExpressionTransform × 4                                    │
│           Header: eventId Int64: eventId Int64 Int64(size = 0)       │
│                   案例号 String: 案例号 String String(size = 0)       │
│                   金额 UInt8: 金额 UInt8 UInt8(size = 0)              │
│             (SettingQuotaAndLimits)                                  │
│               (ReadFromMergeTree)                                    │
│               MergeTreeThread × 4 0 → 1                              │
│               Header: eventId Int64: eventId Int64 Int64(size = 0)   │
│                       案例号 String: 案例号 String String(size = 0)   │
│                       金额 UInt8: 金额 UInt8 UInt8(size = 0)          │
└──────────────────────────────────────────────────────────────────────┘
```

### 构建Query Pipeline时的Dry Run

在构建executeActionForHeader() 函数获取表头header，但是并不产生数据，它会调用dryrun模式，并不产生数据。



## 执行Query Pipeline

执行Query Pipeline的类是`PullingPipelineExecutor`, `PullingAsyncPipelineExecutor`, `PushPipelineExecutor`, `PushAsyncPipelineExecutor`。非Async的是单线程版本，带Async的是多线程并行版本。`PullingAsyncPipelineExecutor`虽然名字里有Async字眼，但实际上是等所有worker线程完成之后才返回，因此并不是我眼中的异步。

Query Pipeline的基本单位是Processor，实际执行Processor的类是`PipelineExecutor`，该类被以上所有executor所调用。类QueryPipeline是Query Pipeline的实现，其中用于执行的信息如下代码所示：

```C%2B%2B
class QueryPipeline
{
...
...
private:
    PipelineResourcesHolder resources;
    Processors processors;  // 所有要执行的processors

    InputPort * input = nullptr; // 输入端口

    OutputPort * output = nullptr; // 输出端口
    OutputPort * totals = nullptr;
    OutputPort * extremes = nullptr;

    QueryStatus * process_list_element = nullptr; // 名字很奇怪，是表示查询运行状态

    IOutputFormat * output_format = nullptr; // 最终输出

    size_t num_threads = 0;  // 线程数
}
```

`IProcessor`的实现类是可以直接执行的task。

`QueryPipeline::complete() `里设定完成后的最终输出，`IOutputFormat`也是`IProcessor`的派生类。

```C%2B%2B
void QueryPipeline::complete(std::shared_ptr<IOutputFormat> format)
{
}
```



### Chunk

```C%2B%2B
/**
 * Chunk is a list of columns with the same length.
 * Chunk stores the number of rows in a separate field and supports invariant of equal column length.
 *
 * Chunk has move-only semantic. It's more lightweight than block cause doesn't store names, types and index_by_name.
 *
 * Chunk can have empty set of columns but non-zero number of rows. It helps when only the number of rows is needed.
 * Chunk can have columns with zero number of rows. It may happen, for example, if all rows were filtered.
 * Chunk is empty only if it has zero rows and empty list of columns.
 *
 * Any ChunkInfo may be attached to chunk.
 * It may be useful if additional info per chunk is needed. For example, bucket number for aggregated data.
**/
```

### Block 

```C%2B%2B
/** Container for set of columns for bunch of rows in memory.
  * This is unit of data processing.
  * Also contains metadata - data types of columns and their names
  *  (either original names from a table, or generated names during temporary calculations).
  * Allows to insert, remove columns in arbitrary position, to change order of columns.
  */
```



### Processors

实际执行query pipeline的组件是庞大而丰富的processors，它们是底层执行的基础构件。

```Ruby
  ^IProcessor$
  └── IProcessor
      ├── AggregatingInOrderTransform
      ├── AggregatingTransform
      ├── ConcatProcessor
      ├── ConvertingAggregatedToChunksTransform
      ├── CopyTransform
      ├── CopyingDataToViewsTransform
      ├── DelayedPortsProcessor
      ├── DelayedSource
      ├── FillingRightJoinSideTransform
      ├── FinalizingViewsTransform
      ├── ForkProcessor
      ├── GroupingAggregatedTransform
      ├── IInflatingTransform
      ├── IntersectOrExceptTransform
      ├── JoiningTransform
      ├── LimitTransform
      ├── OffsetTransform
      ├── ResizeProcessor
      ├── SortingAggregatedTransform
      ├── StrictResizeProcessor
      ├── WindowTransform
      ├── IAccumulatingTransform
      │   ├── BufferingToFileTransform
      │   ├── CreatingSetsTransform
      │   ├── CubeTransform
      │   ├── MergingAggregatedTransform
      │   ├── QueueBuffer
      │   ├── RollupTransform
      │   ├── TTLCalcTransform
      │   └── TTLTransform
      ├── ISimpleTransform
      │   ├── AddingDefaultsTransform
      │   ├── AddingSelectorTransform
      │   ├── ArrayJoinTransform
      │   ├── CheckSortedTransform
      │   ├── DistinctSortedTransform
      │   ├── DistinctTransform
      │   ├── ExpressionTransform
      │   ├── ExtremesTransform
      │   ├── FillingTransform
      │   ├── FilterTransform
      │   ├── FinalizeAggregatedTransform
      │   ├── LimitByTransform
      │   ├── LimitsCheckingTransform
      │   ├── MaterializingTransform
      │   ├── MergingAggregatedBucketTransform
      │   ├── PartialSortingTransform
      │   ├── ReplacingWindowColumnTransform
      │   ├── ReverseTransform
      │   ├── SendingChunkHeaderTransform
      │   ├── TotalsHavingTransform
      │   ├── TransformWithAdditionalColumns
      │   └── WatermarkTransform
      ├── ISink
      │   ├── EmptySink
      │   ├── ExternalTableDataSink
      │   ├── NullSink
      │   └── ODBCSink
      ├── SortingTransform
      │   ├── FinishSortingTransform
      │   └── MergeSortingTransform
      ├── IMergingTransformBase
      │   └── IMergingTransform
      │       ├── AggregatingSortedTransform
      │       ├── CollapsingSortedTransform
      │       ├── ColumnGathererTransform
      │       ├── FinishAggregatingInOrderTransform
      │       ├── GraphiteRollupSortedTransform
      │       ├── MergingSortedTransform
      │       ├── ReplacingSortedTransform
      │       ├── SummingSortedTransform
      │       └── VersionedCollapsingTransform
      ├── ExceptionKeepingTransform
      │   ├── CheckConstraintsTransform
      │   ├── ConvertingTransform
      │   ├── CountingTransform
      │   ├── ExecutingInnerQueryFromViewTransform
      │   ├── SquashingChunksTransform
      │   └── SinkToStorage
      │       ├── BufferSink
      │       ├── DistributedSink
      │       ├── EmbeddedRocksDBSink
      │       ├── HDFSSink
      │       ├── KafkaSink
      │       ├── LiveViewSink
      │       ├── LogSink
      │       ├── MemorySink
      │       ├── MergeTreeSink
      │       ├── NullSinkToStorage
      │       ├── PostgreSQLSink
      │       ├── PushingToLiveViewSink
      │       ├── PushingToWindowViewSink
      │       ├── RabbitMQSink
      │       ├── RemoteSink
      │       ├── ReplicatedMergeTreeSink
      │       ├── SQLiteSink
      │       ├── SetOrJoinSink
      │       ├── StorageFileSink
      │       ├── StorageMySQLSink
      │       ├── StorageS3Sink
      │       ├── StorageURLSink
      │       ├── StripeLogSink
      │       └── PartitionedSink
      │           ├── PartitionedHDFSSink
      │           ├── PartitionedStorageFileSink
      │           ├── PartitionedStorageS3Sink
      │           └── PartitionedStorageURLSink
      ├── IOutputFormat
      │   ├── ArrowBlockOutputFormat
      │   ├── LazyOutputFormat
      │   ├── MySQLOutputFormat
      │   ├── NativeOutputFormat
      │   ├── NullOutputFormat
      │   ├── ODBCDriver2BlockOutputFormat
      │   ├── ORCBlockOutputFormat
      │   ├── ParallelFormattingOutputFormat
      │   ├── ParquetBlockOutputFormat
      │   ├── PostgreSQLOutputFormat
      │   ├── PullingOutputFormat
      │   ├── TemplateBlockOutputFormat
      │   ├── PrettyBlockOutputFormat
      │   │   ├── PrettyCompactBlockOutputFormat
      │   │   └── PrettySpaceBlockOutputFormat
      │   └── IRowOutputFormat
      │       ├── AvroRowOutputFormat
      │       ├── BinaryRowOutputFormat
      │       ├── CSVRowOutputFormat
      │       ├── CapnProtoRowOutputFormat
      │       ├── CustomSeparatedRowOutputFormat
      │       ├── JSONCompactEachRowRowOutputFormat
      │       ├── MarkdownRowOutputFormat
      │       ├── MsgPackRowOutputFormat
      │       ├── ProtobufRowOutputFormat
      │       ├── RawBLOBRowOutputFormat
      │       ├── ValuesRowOutputFormat
      │       ├── VerticalRowOutputFormat
      │       ├── XMLRowOutputFormat
      │       ├── JSONEachRowRowOutputFormat
      │       │   └── JSONEachRowWithProgressRowOutputFormat
      │       ├── JSONRowOutputFormat
      │       │   └── JSONCompactRowOutputFormat
      │       └── TabSeparatedRowOutputFormat
      │           └── TSKVRowOutputFormat
      └── ISource
          ├── ConvertingAggregatedToChunksSource
          ├── MergeSorterSource
          ├── NullSource
          ├── ODBCSource
          ├── PushingAsyncSource
          ├── PushingSource
          ├── RemoteExtremesSource
          ├── RemoteTotalsSource
          ├── SourceFromNativeStream
          ├── TemporaryFileLazySource
          ├── WaitForAsyncInsertSource
          ├── IInputFormat
          │   ├── ArrowBlockInputFormat
          │   ├── NativeInputFormat
          │   ├── ORCBlockInputFormat
          │   ├── ParallelParsingInputFormat
          │   ├── ParquetBlockInputFormat
          │   ├── ValuesBlockInputFormat
          │   └── IRowInputFormat
          │       ├── AvroConfluentRowInputFormat
          │       ├── AvroRowInputFormat
          │       ├── CapnProtoRowInputFormat
          │       ├── JSONAsStringRowInputFormat
          │       ├── JSONEachRowRowInputFormat
          │       ├── LineAsStringRowInputFormat
          │       ├── MsgPackRowInputFormat
          │       ├── ProtobufRowInputFormat
          │       ├── RawBLOBRowInputFormat
          │       ├── RegexpRowInputFormat
          │       ├── TSKVRowInputFormat
          │       └── RowInputFormatWithDiagnosticInfo
          │           ├── TemplateRowInputFormat
          │           └── RowInputFormatWithNamesAndTypes
          │               ├── BinaryRowInputFormat
          │               ├── CSVRowInputFormat
          │               ├── CustomSeparatedRowInputFormat
          │               ├── JSONCompactEachRowRowInputFormat
          │               └── TabSeparatedRowInputFormat
          └── ISourceWithProgress
              └── SourceWithProgress
                  ├── BlocksListSource
                  ├── BlocksSource
                  ├── BufferSource
                  ├── CassandraSource
                  ├── ColumnsSource
                  ├── DDLQueryStatusSource
                  ├── DataSkippingIndicesSource
                  ├── DictionarySource
                  ├── DirectoryMonitorSource
                  ├── EmbeddedRocksDBSource
                  ├── FileLogSource
                  ├── GenerateSource
                  ├── HDFSSource
                  ├── JoinSource
                  ├── KafkaSource
                  ├── LiveViewEventsSource
                  ├── LiveViewSource
                  ├── LogSource
                  ├── MemorySource
                  ├── MergeTreeSequentialSource
                  ├── MongoDBSource
                  ├── NumbersMultiThreadedSource
                  ├── NumbersSource
                  ├── RabbitMQSource
                  ├── RedisSource
                  ├── RemoteSource
                  ├── SQLiteSource
                  ├── ShellCommandSource
                  ├── SourceFromSingleChunk
                  ├── StorageFileSource
                  ├── StorageInputSource
                  ├── StorageS3Source
                  ├── StorageURLSource
                  ├── StripeLogSource
                  ├── SyncKillQuerySource
                  ├── TablesBlockSource
                  ├── WindowViewSource
                  ├── ZerosSource
                  ├── MySQLSource
                  │   └── MySQLWithFailoverSource
                  ├── PostgreSQLSource
                  │   └── PostgreSQLTransactionSource
                  └── MergeTreeBaseSelectProcessor
                      ├── MergeTreeThreadSelectProcessor
                      └── MergeTreeSelectProcessor
                          ├── MergeTreeInOrderSelectProcessor
                          └── MergeTreeReverseSelectProcessor
```

最重要的是这几个Class：

```Ruby
  ^IProcessor$
  └── IProcessor
      ├── IAccumulatingTransform
      ├── IMergingTransformBase
      ├── IOutputFormat
      ├── ISimpleTransform
      ├── ISink
      ├── ISource
      ├── JoiningTransform
      ├── LimitTransform
      ├── OffsetTransform
      ├── ResizeProcessor
      ├── SortingAggregatedTransform
      ├── SortingTransform
      └── WindowTransform
```



## 直接调用SQL查询

解释器里面可以直接调用SQL查询，示例代码如下：

```C%2B%2B
BlockIO InterpreterShowProcesslistQuery::execute()
{
    return executeQuery("SELECT * FROM system.processes", getContext(), true);
}
```
