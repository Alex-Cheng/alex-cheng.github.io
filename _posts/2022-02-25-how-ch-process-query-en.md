# Clickhouse executes the process of processing query statements (including DDL and DML)

## Overall process

1. Start a thread to handle the TCP connection from the client;
2. Receive the request data and pass it to the function `executeQueryImpl()` for processing;
3. `executeQueryImpl()` processes the string of the SQL statement for the query;
4. Generate a `QueryPipeline` instance, which can contain data or just information on how to read the data;
5. Execute the QueryPipeline instance via a *PipelineExecutor such as PullingAsyncPipelineExecutor to obtain the data result.

```
PullingAsyncPipelineExecutor::pull() -> PipelineExecutor::execute()
```

## The executeQueryImpl() function process

executeQueryImpl() is the focus of the entire processing flow, and it includes the following:

1. Parsing the SQL statement to generate the AST;
2. Preprocessing the AST
    1. Parameter substitution of the AST to the actual values
    2. Substitution of the With clause
    3. Various visitors
    4. Standardizing the AST
    5. Processing insert statements with and without select
3. Obtaining the corresponding interpreter object through the factory method (all interpreters are found in InterpreterFactory.cpp)
4. Execute the interpreter's execute() method, which is a function defined by the base class `IInterpreter` for all interpreters, and return an instance of `BlockIO`, which contains, among other things, an instance of `QueryPipeline`.

`BlockIO` is an IO abstraction that can be used for both output (select-like queries) and input (insert-like queries), as you can see in the following definition of `IInterpreter`.

```Cpp
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

`BlockIO` contains the query pipeline, process list and callbacks, where the query pipeline is the data flow pipeline.

1. The interpreter for the Select query class, such as `InterpreterSelectQuery`, will first construct a query plan, and then construct a query pipeline from the query plan.
2. `PullingAsyncPipelineExecutor::pull()` or `PullingPipelineExecutor` pulls data from the `QueryPipeline` pipeline.



## Parse the query statement

The `parseQuery()` function takes a string of SQL statements and a parser, calls `parseQueryAndMovePosition()`, and finally calls `tryParseQuery()` to complete the parsing and return the AST tree as the result.



The parameter `allow_multi_statements` is used to control whether to parse multiple SQL statements, which is very important for my current task.

```Cpp
ASTPtr parseQueryAndMovePosition(
    IParser & parser,
    const char * & pos,
    const char * end,
    const std::string & query_description,
    bool allow_multi_statements,
    size_t max_query_size,
    size_t max_parser_depth)
{...
 ......
 ...
}
```

The process is roughly divided into two steps:

1. Convert the SQL string to a token set
2. The parser traverses the token set using the TokenIterator to update the AST result

The final AST tree is the result of the parsing.

Each parser represents a syntax pattern, and one parser can call multiple other parsers. Here are all the parsers.

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
├── ParserBool......
 .......
```

The AST syntax tree consists of a set of instances of the derived implementation class of `IAST`

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
├── ASTColumnsMatcher...
 ...
```


## Building the query pipeline

`IInterpreter::execute() `returns a `BlockIO `instance whose main component is a `QueryPipeline` instance. It can be said that the interpreter builds the query pipeline, but each interpreter builds the query pipeline differently. For Select-type queries (the most common queries), a Query Plan is first generated, optimized, and then the final Query Pipeline is generated.

`IInterpreter::execute()` is the core of the interpreter, which returns a `BlockIO` instance as a result based on three conditions.

```Cpp
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



### Building the query plan for a SELECT query

The interpreter for the SELECT query class, such as the `InterpreterSelectQuery` execute() method, first generates a `QueryPlan` instance, which, under an optimization strategy, generates a `QueryPipeline` instance. This is why the `explain plan` command can only be used for SELECT queries. Note that `InterpreterSelectQuery::executeImpl()` here is not an implementation of `InterpreterSelectQuery::execute()`, but actually an implementation of `InterpreterSelectQuery::buildQueryPlan()`.

The following comments reflect the main logic of the code:

```Cpp
void InterpreterSelectQuery::executeImpl(QueryPlan & query_plan, std::optional<Pipe> prepared_pipe)
{
    /** Streams of data. When the query is executed in parallel, we have several data streams.
    * If there is no GROUP BY, then perform all operations before ORDER BY and LIMIT in parallel, then
    * if there is an ORDER BY, then glue the streams using ResizeProcessor, and then MergeSorting transforms,
    * if not, then glue it using ResizeProcessor,
    * then apply LIMIT.
    * If there is GROUP BY, then we will perform all operations up to GROUP BY, inclusive, in parallel;
    * a parallel GROUP BY will glue streams into one,
    * then perform the remaining operations with one resulting stream.
    */
} 
```



### Query Plan Step

Query Plan Step is a component of Query Plan, represented by the base class `IQueryPlanStep` and its derived implementation classes.

A `QueryPlan` instance is mainly composed of a number of instances of IQueryPlanStep implementation classes organized in a tree (not a binary tree). Each instance of an IQueryPlanStep implementation class generates and weaves a set of Processors into the QueryPipeline, which is implemented by the `updatePipeline()` method.

The following comments explain the outline.

```Cpp
/// Add processors from current step to QueryPipeline.
/// Calling this method, we assume and don't check that:
/// * pipelines.size() == getInputStreams.size()
/// * header from each pipeline is the same as header from corresponding input_streams
/// Result pipeline must contain any number of streams with compatible output header is hasOutputStream(),
/// or pipeline should be completed otherwise.
virtual QueryPipelineBuilderPtr updatePipeline(QueryPipelineBuilders pipelines, const BuildQueryPipelineSettings & settings) = 0;
```



### Select query pipeline generation experiment

Use the following data table for the experiment:

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

**Simplest SELECT**

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

**SELECT with filter and LIMIT**

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


**SELECT with filter conditions, GROUP BY and LIMIT**

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

### Dry Run when constructing the Query Pipeline

The executeActionForHeader() function is used to retrieve the table header, but no data is generated. It will call the dryrun mode and no data will be generated.



## Execute Query Pipeline

The classes that execute the Query Pipeline are `PullingPipelineExecutor`, `PullingAsyncPipelineExecutor`, `PushPipelineExecutor`, and `PushAsyncPipelineExecutor`. The non-Async ones are single-threaded versions, while the ones with Async are multi-threaded parallel versions. Although the name of `PullingAsyncPipelineExecutor` contains the word Async, it actually returns after all worker threads have completed, so it is not asynchronous in my eyes.

The basic unit of the Query Pipeline is the Processor, and the class that actually implements the Processor is the PipelineExecutor, which is called by all the executors above. The class QueryPipeline is the implementation of the Query Pipeline, and the information used for execution is shown in the following code:

```Cpp
class QueryPipeline
{
...
...
private:
    PipelineResourcesHolder resources;
    Processors processors; // All the processors to be executed
    
    InputPort * input = nullptr; // input port
    
    OutputPort * output = nullptr; // output port
    OutputPort * totals = nullptr;
    OutputPort * extremes = nullptr;
    
    QueryStatus * process_list_element = nullptr; // strange name, indicates the query status
    
    IOutputFormat * output_format = nullptr; // final output
    
    size_t num_threads = 0; // number of threads
}
```

The implementation class of `IProcessor` is a task that can be executed directly.

The final output after completion is set in `QueryPipeline:: complete() `sets the final output after completion, and `IOutputFormat` is also a derived class of `IProcessor`.

```Cpp
void QueryPipeline:: complete(std::shared_ptr<IOutputFormat> format)
{
}
```



### Chunk

```Cpp
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

```Cpp
/** Container for set of columns for bunch of rows in memory.
  * This is unit of data processing.
  * Also contains metadata - data types of columns and their names
  *  (either original names from a table, or generated names during temporary calculations).
  * Allows to insert, remove columns in arbitrary position, to change order of columns.
  */
```



### Processors

The actual query pipeline execution components are the large and rich processors, which are the basic building blocks for the underlying execution.

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

The most important ones are these classes:

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



## Directly call SQL queries

You can directly call SQL queries in the interpreter. The sample code is as follows:

```Cpp
BlockIO InterpreterShowProcesslistQuery::execute()
{
    return executeQuery("SELECT * FROM system. processes”, getContext(), true);
}
```
