# Common ClickHouse problem diagnosis queries

Clickhouse is a powerful OLAP database. In actual use, you will encounter various problems, and there are also many places that can be tuned. This article explains how to diagnose ClickHouse problems and perform a performance analysis.



## Related system tables



| No. | Table name | Meaning | Description |
| ---- | ------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------- |
| 1 | system.asynchronous_insert_log | Asynchronous data insertion log | Added in version 2023 |
| 2 | system.asynchronous_metrics | Current system performance metrics | Asynchronously updated |
| 3 | system.asynchronous_metric_log | System historical performance metrics | Asynchronously updated |
| 4 | system.crash_log | System crash log | |
| 5 | system.filesystem_cache_log | Log of file-based caches | |
| 6 | system.metric_log | System historical performance metrics | Not the same as system.asynchronous_metrics |
| 7 | system.part_log | The system's data part log records the creation, merging, download, removal, update, and movement of data parts. | Very useful. |
| 8 | system.processes | Queries currently running. | Very common. |
| 9 | system.query_log | The system's query log. | Very useful. |
| 10 | system.query_views_log | Query log for various views | Experimentally found that it does not record any logs, even if log_query_views is turned on. |
| 11 | system.query_thread_log | Thread-related log for system queries | Records thread_name, thread_id, master_thread_id information |
| 12 | system.opentelemetry_span_log | OpenTelemetry span log | See the description of OpenTelemetry below |
| 13 | system.processors_profile_log | Detailed performance information during query execution | |
| 14 | system.session_log | Client login/logout log | Can be used for security protection |
| 15 | system.settings | Settings information for system configuration | |
| 16 | system.text_log | The system's text log, which is the same as the content of the log file | |
| 17 | system.trace_log | System operation trace log, including callstack. | Very useful |
| 18 | system.transactions_info_log | Transaction work log, including start and end time, status | |
| 19 | system.zookeeper_log | Operation log for ZooKeeper | |

OpenTelemetry is an open standard for generating, collecting and processing trace, logging and metrics data from distributed systems. It provides a set of APIs and SDKs that can be integrated into applications and infrastructure to collect and deliver data and aggregate it into a centralized repository to support analysis, monitoring and troubleshooting.




## Performance metrics

Performance metrics are sourced from `system.asynchronous_metrics`, `system.asynchronous_metric_log`, and `system.metric_log`.



### Real-time performance metrics



#### Display all current performance metrics

```SQL
select
        *,
        formatReadableSize(value),
        value
from
        system.asynchronous_metrics
order by
        metric;
```

There are more than 300 metrics. Here is a description of some of them

| Metric | Meaning |
| --------------------------------------------- | ---------------------------------------------------- |
| CompiledExpressionCacheCount | Number of compiled expressions saved in the cache |
| jemalloc.* | jemalloc-related metrics, requires in-depth understanding of jemalloc memory allocation |
| MarkCacheBytes / MarkCacheFiles | .mrk file cache |
| MemoryCode | Memory footprint of ClickHouse code |
| MemoryDataAndStack | Memory size occupied by data and stack (including virtual memory) |
| MemoryResident | Size of occupied real memory |
| MemoryShared | Shared memory size |
| MemoryVirtual | Virtual memory size |
| NumberOfDatabases | Number of databases |
| NumberOfTables | Number of tables |
| ReplicasMaxAbsoluteDelay | The maximum absolute delay time (in seconds) for cluster replicas |
| ReplicasMaxRelativeDelay | The maximum relative delay time (in seconds) for cluster replicas |
| ReplicasMaxInsertsInQueue | The maximum number of parts to be fetched from other replicas by a single Replicated table slave |
| ReplicasSumInsertsInQueue | The total number of parts to be fetched from other replicas by all Replicated table slaves |
| ReplicasMaxMergesInQueue | The maximum number of merge tasks in the merge queue of a single Replicated table slave |
| ReplicasSumMergesInQueue | The total number of merge tasks in the merge queue of all replicated tables |
| ReplicasMaxQueueSize | The maximum number of tasks in the task queue of a single replicated table |
| ReplicasSumQueueSize | The maximum number of tasks in the task queue of all replicated tables |
| UncompressedCacheBytes/UncompressedCacheCells | The memory space occupied by the cache of uncompressed data |
| Uptime | The cumulative online time of ClickHouse (in seconds) |



#### Key metrics - Memory related

```SQL
select
        *,
        formatReadableSize(value)
from
        system.asynchronous_metrics
where
       metric ilike '%memory%' or metric ilike '%cach%'
order by
        metric;
```


#### Key metrics - CPU-related

```SQL
select
        *
from
        system.asynchronous_metrics
where
       metric ilike '%cpu%'
order by
        metric;
```

Each core of the CPU has a corresponding CPU metric. Currently, there are about 10 metrics for each CPU core, suffixed with `CPUx`.

| Metric (without the CPUx suffix) | Explanation |
| ---------------------------- | ------------------------------------------------------------ |
| OSGuestNiceTime | Metric that measures the “nice time” of processes in the virtual machine. Nice time indicates the priority of the process and ranges from -20 to +19. The default value is 0. A lower nice value indicates a higher priority for the process, i.e. it is more likely to be allocated a CPU time slice. |
| OSGuestTime | An indicator that measures the time of processes in a virtual machine. It indicates the total time that processes running in a virtual machine spend using the CPU. The unit is nanoseconds. It can be used to monitor the CPU utilization of processes in a virtual machine and the load on the host system. |
| OSIOWaitTime | An indicator of the time spent by a process waiting for I/O operations. It can be used to monitor the load on I/O devices by processes. Generally, if this indicator is high, it indicates that the bottleneck is in I/O, which is detrimental to systems that emphasize throughput. |
| OSIdleTime | An indicator of CPU idle time, in nanoseconds. |
| OSIrqTime | An indicator that measures the CPU time consumed by a process in the hardware interrupt (such as I/O device operation completion, clock interrupt, etc.) service routine. This indicator mainly indicates the impact of I/O interrupts on the system, in nanoseconds. A high value indicates that the processing of I/O interrupts is a bottleneck, but the optimization may not be at the software level. |
| OSNiceTime | A metric that measures the “nice time” of processes in the host. Nice time indicates the priority of the process, and ranges from -20 to +19. The default value is 0. A smaller nice value indicates a higher priority for the process, which means it is more likely to obtain a CPU time slice. |
| OSSoftIrqTime | A metric that measures the CPU time consumed by soft interrupt service routines, in nanoseconds. |
| OSStealTime | A metric that measures the CPU time stolen by the host computer from virtual machines in a virtualized environment. It indicates the time that processes running in virtual machines are forced to wait because the host computer has stolen CPU time. The unit is nanoseconds. A high value indicates that the host computer is overloaded and resources are highly contested. |
| OSSystemTime | CPU system time metric, which indicates the total time the process has used the CPU in kernel mode, in nanoseconds. |
| OSUserTime | CPU user time metric, which indicates the total time the process has used the CPU in user mode, in nanoseconds. |
| OSCPUVirtualTimeMicroseconds | Runtime on the virtual CPU, in microseconds. |

Reference: [Metrics List](https://pastila.nl/?00014be2/6cb3dc5f2fc8f3c8ae55bd8a2ea39c2d.md)



### Historical performance metrics

Replace the table `system.asynchronous_metrics` in real-time performance metrics with `system.asynchronous_metric_log`, which has the additional columns `event_date` and `event_time`.

For example, to view historical memory-related metrics, use the following query:
```SQL
select *
from system.asynchronous_metric_log
where
       metric ilike '%memory%'
order by
        event_time
desc;
```

The following describes some commonly used queries.



#### Trend of peak memory usage (nearest to farthest)

```SQL
with interval 5 minute as time_frame_size -- 时间间隔，当前是5分钟
, 100 as bar_width -- 条状图的宽度，当前是100
, (select max(value) from system.asynchronous_metric_log where metric = 'OSMemoryTotal') as max_mem
, now() - interval 24 hour as time_start
, now() as time_end
select toStartOfInterval(event_time, time_frame_size) as timeframe,
	max(value) as `used_memory`,
    formatReadableSize(`used_memory`) as `used_memory_readable`,
    formatReadableSize(max_mem) as `max_memory`,
    bar(used_memory / max_mem, 0, 1, bar_width)
from system.asynchronous_metric_log
where metric = 'MemoryResident' and event_time >= time_start and event_time <= time_end
group by timeframe
order by timeframe desc;
```


#### Trend of peak CPU utilization

```SQL
with interval 5 minute as time_frame_size -- 时间间隔，当前是5分钟
, 20 as bar_width -- 条状图的宽度，当前是30
, now() - interval 24 hour as time_start
, now() as time_end
select 
   toStartOfInterval(event_time, time_frame_size) as timeframe,
   maxIf(value, metric = 'OSUserTimeNormalized') as cpu_usr,
   maxIf(value, metric = 'OSSystemTimeNormalized') as cpu_sys,
   bar(cpu_usr, 0, 1, bar_width) as barCPU_usr,
   bar(cpu_sys, 0, 1, bar_width) as barCPU_sys
from system.asynchronous_metric_log
where metric in ['OSUserTimeNormalized', 'OSSystemTimeNormalized'] and event_time >= time_start and event_time <= time_end
group by timeframe
order by timeframe desc;
```



#### Trend of peak CPU and memory utilization

```SQL
with interval 5 minute as time_frame_size -- 时间间隔，当前是5分钟
, 25 as bar_width -- 条状图的宽度，当前是100
, (select max(value) from system.asynchronous_metric_log where metric = 'OSMemoryTotal') as max_mem
, now() - interval 24 hour as time_start
, now() as time_end
select toStartOfInterval(event_time, time_frame_size) as timeframe,
	maxIf(value, metric = 'MemoryResident') as `used_memory`,
    formatReadableSize(`used_memory`) as `used_memory_readable`,
    formatReadableSize(max_mem) as `max_memory`,
    maxIf(value, metric = 'OSUserTimeNormalized') as cpu_usr,
    maxIf(value, metric = 'OSSystemTimeNormalized') as cpu_sys,    
    cpu_usr + cpu_sys as cpu,
    bar(used_memory / max_mem, 0, 1, bar_width) as barMem,
    bar(cpu_usr + cpu_sys, 0, 1, bar_width) as barCPU_usr
from system.asynchronous_metric_log
where metric in ['OSUserTimeNormalized', 'OSSystemTimeNormalized', 'MemoryResident']
	and event_time >= time_start
	and event_time <= time_end
group by timeframe
order by timeframe desc;
```



#### Memory usage statistics for various types of queries

Use the following query to obtain the memory usage statistics for various types of queries for a certain period of time.

```SQL
WITH 
    now() - INTERVAL 24 HOUR AS min_time,  -- you can adjust that
    now() AS max_time,   -- you can adjust that
    INTERVAL 1 HOUR as time_frame_size
SELECT 
    timeframe,
    formatReadableSize(max(mem_overall)) as peak_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='Insert'))     as inserts_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='Select'))     as selects_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='MergeParts')) as merge_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='MutatePart')) as mutate_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='Alter'))      as alter_ram,
    formatReadableSize(maxIf(mem_by_type, event_type='Create'))     as create_ram,
    formatReadableSize(maxIf(mem_by_type, event_type not IN ('Insert', 'Select', 'MergeParts','MutatePart', 'Alter', 'Create') )) as other_types_ram,
    groupUniqArrayIf(event_type, event_type not IN ('Insert', 'Select', 'MergeParts','MutatePart', 'Alter', 'Create') ) as other_types
FROM (
    SELECT 
        toStartOfInterval(event_timestamp, time_frame_size) as timeframe,
        toDateTime( toUInt32(ts) ) as event_timestamp,
        t as event_type,
        SUM(mem) OVER (PARTITION BY t ORDER BY ts) as mem_by_type,
        SUM(mem) OVER (ORDER BY ts) as mem_overall
    FROM 
    (
        WITH arrayJoin([(toFloat64(event_time_microseconds) - (duration_ms / 1000), toInt64(peak_memory_usage)), (toFloat64(event_time_microseconds), -peak_memory_usage)]) AS data
        SELECT
        CAST(event_type,'LowCardinality(String)') as t,
        data.1 as ts,
        data.2 as mem
        FROM system.part_log
        WHERE event_time BETWEEN min_time AND max_time AND peak_memory_usage != 0

        UNION ALL 

        WITH arrayJoin([(toFloat64(query_start_time_microseconds), toInt64(memory_usage)), (toFloat64(event_time_microseconds), -memory_usage)]) AS data
        SELECT 
        query_kind,
        data.1 as ts,
        data.2 as mem
        FROM system.query_log
        WHERE event_time BETWEEN min_time AND max_time AND memory_usage != 0
))
group by timeframe
order by timeframe desc;
```



### MergeTree-related performance metrics

#### Merge performance metrics

```sql
SELECT
    table,
    round((elapsed * (1 / progress)) - elapsed, 2) AS estimate,
    elapsed,
    progress,
    is_mutation,
    formatReadableSize(total_size_bytes_compressed) AS size,
    formatReadableSize(memory_usage) AS mem
FROM system.merges
ORDER BY elapsed DESC
```



#### Performance metrics for mutations

```sql
SELECT
    database,
    table,
    substr(command, 1, 30) AS command,
    sum(parts_to_do) AS parts_to_do,
    anyIf(latest_fail_reason, latest_fail_reason != '')
FROM system.mutations
WHERE NOT is_done
GROUP BY
    database,
    table,
    command
```



## Troubleshooting

If the system is currently experiencing a problem, follow the troubleshooting steps below.



### Currently running queries

You can find out whether any queries are currently running for a long time by looking at the currently running queries.

```SQL
select query_id, * from system.processes;
```

Or, to narrow the focus,

```SQL
SELECT
    initial_query_id,
    elapsed,
    formatReadableSize(memory_usage),
    formatReadableSize(peak_memory_usage),
    query
FROM system.processes
ORDER BY peak_memory_usage DESC
LIMIT 10;
```



### Forcefully terminate queries

Queries that are executed for a long time without being terminated need to be terminated in time to release system resources for use by other queries, so as to avoid the entire system from being stuck.

```SQL
kill query where query_id = '<query ID>'; -- Replace <query ID> with the ID of the query you really want to terminate
```



### Query error analysis

First, find the keyword that causes the error based on the error message of the query, replace `keyword`, and use the following query to find the query that causes the error.

```SQL
with '%<包含关键字>%' as keyword  -- 把<包含关键字>替换为实际关键字
select event_time_microseconds, query_id, query, `exception`, exception_code, stack_trace  from system.query_log where exception ilike keyword order by event_time_microseconds desc;
```

You can roughly determine where the exception was thrown from the `stack_trace`.



### System crash analysis

#### View all crash logs

```SQL
select * from system.crash_log order by event_time desc;
```



#### Count the number of crashes by build version

```SQL
select min(event_time) as begin_time, max(event_time) as end_time, build_id, count() from system.crash_log group by build_id order by end_time desc;
```



## Tuning analysis

Tuning analysis is generally divided into two steps: 1. Find the query or queries with the problem; 2. Carefully examine the execution details of the query with the problem and the details of the relevant performance indicators.



### Analysis of the memory occupied by loaded tables

If you find that ClickHouse occupies a large amount of memory after starting without any operations, it is likely that the loaded tables occupy too much memory. In particular, tables of the `Join`, `Memory`, and `Set` engines will load all data into memory. We need to find such loaded tables that occupy memory.

```SQL
with (select formatReadableSize(sum(total_bytes)) from system.tables where engine in ('Memory','Set','Join')) as all_bytes
select
    database as `数据库名`,
    name as `表名`,
    formatReadableSize(total_bytes) as `占用内存`,
    all_bytes as `总共占用`
from system.tables
where engine in ('Memory','Set','Join')
order by total_bytes desc;
```


The MergeTree engine family also preloads some data in memory, which also needs to be found.

```SQL
SELECT
	count() as `parts数量`,
    sumIf(data_uncompressed_bytes, part_type = 'InMemory') as `内存中的数据片大小`,
    formatReadableSize(sum(primary_key_bytes_in_memory)) as `主键占用内存`,
    formatReadableSize(sum(primary_key_bytes_in_memory_allocated)) as `为主键分配的内存大小`
FROM system.parts;
```



#### Refresh in real time using a shell script

```bash
echo "         Merges      Processes       PrimaryK       TempTabs          Dicts"; \
for i in `seq 1 600`; do clickhouse-client --empty_result_for_aggregation_by_empty_set=0  -q "select \
(select leftPad(formatReadableSize(sum(memory_usage)),15, ' ') from system.merges)||
(select leftPad(formatReadableSize(sum(memory_usage)),15, ' ') from system.processes)||
(select leftPad(formatReadableSize(sum(primary_key_bytes_in_memory_allocated)),15, ' ') from system.parts)|| \
(select leftPad(formatReadableSize(sum(total_bytes)),15, ' ') from system.tables \
 WHERE engine IN ('Memory','Set','Join'))||
(select leftPad(formatReadableSize(sum(bytes_allocated)),15, ' ') FROM system.dictionaries)
"; sleep 3;  done 
```



### Locating queries that need to be optimized

Find the queries that need to be optimized most among the many queries that occur within a period of time.

#### All queries within a period of time and sort by execution time

to get all queries in a certain period of time and sort them by execution duration from largest to smallest. This allows you to quickly find the most time-consuming queries.

```SQL
with now() - interval 24 hour as time_start  -- 开始时间
  , now() as time_end   -- 结束时间
select
		event_time_microseconds,
        initial_query_id,
        query,
        query_start_time,
        query_duration_ms,
        memory_usage,
        formatReadableSize (memory_usage),
        `databases`,
        `tables`,
        stack_trace,
        *
from
        system.query_log
where
        event_time_microseconds >= time_start and event_time_microseconds <= time_end
        and
        type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
order by
        query_duration_ms desc;
```



#### All queries in a time period sorted by memory consumption

Get all queries in a time period sorted by memory consumption from high to low. This allows you to quickly find the queries that consume the most memory.

```SQL
with now() - interval 24 hour as time_start  -- 开始时间
  , now() as time_end   -- 结束时间
select
		event_time_microseconds,
        initial_query_id,
        query,
        query_start_time,
        query_duration_ms,
        memory_usage,
        formatReadableSize (memory_usage),
        `databases`,
        `tables`,
        stack_trace,
        *
from
        system.query_log
where
        event_time_microseconds >= time_start and event_time_microseconds <= time_end
        and
        type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
order by
        memory_usage desc;
```



#### The SQL statement that used the most CPU time during a certain period of time

```SQL
with now() - interval 24 hour as time_start -- 开始时间
  , now() as time_end -- 结束时间
select any(query), sum(`ProfileEvents.Values`[indexOf(`ProfileEvents.Names`, 'UserTimeMicroseconds')]) as `总消耗CPU(ms)` 
from system.query_log 
where type = 'QueryFinish'
	and event_time_microseconds >= time_start and event_time_microseconds <= time_end
group by normalizedQueryHash(query)
order by `总消耗CPU(ms)` desc
limit 100
```



#### The SQL statement that used the most memory during a certain period of time

```sql
with now() - interval 24 hour as time_start -- 开始时间
  , now() as time_end -- 结束时间
select any(query), 
	count() as `出现次数`,
	avg(memory_usage) as avg_memory_usage,
	formatReadableSize(avg(memory_usage)) as `平均内存使用`
from system.query_log 
where type = 'QueryFinish'
	and event_time_microseconds >= time_start and event_time_microseconds <= time_end
group by normalizedQueryHash(query)
order by avg_memory_usage desc
limit 100;
```



#### Unfinished queries

```SQL
with now() - interval 24 hour as time_start  -- 开始时间
  , now() as time_end   -- 结束时间
select
  query_id as `查询ID`,
  min(event_time) as `查询时间`,
  any(query),
  groupArray(type) as `事件类型`
from system.query_log
where event_time_microseconds >= time_start and event_time_microseconds <= time_end
group by query_id
HAVING countIf(type = 'QueryFinish') = 0
order by `查询时间` desc;

```



#### Focus on high-consumption queries

```sql
with now() - interval 24 hour as time_start -- 开始时间
  , now() as time_end -- 结束时间
select query_id,
    query,
    query_duration_ms as `查询时长ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'RealTimeMicroseconds')] / 1000 as `实际CPU时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'UserTimeMicroseconds')] / 1000 as `用户态CPU时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'SystemTimeMicroseconds')] / 1000 as `系统态CPU时间ms`,
    formatReadableSize(memory_usage) as `总内存消耗`,
    read_rows as ReadRows,
    formatReadableSize(read_bytes) as `总计读取字节`,
    written_rows as WrittenTows,
    formatReadableSize(written_bytes) as `总计写入字节`,
    result_rows as ResultRows,
    formatReadableSize(result_bytes) as `总计输出结果字节`
from system.query_log
where (
        event_time_microseconds >= time_start
        and event_time_microseconds <= time_end
    )
    and type in ('QueryFinish', 'ExceptionWhileProcessing')
order by query_duration_ms desc
limit 100;
```



### Investigate the situation during the execution of a query

To investigate and analyze the execution performance of a specific query, first obtain the start and end time of the query, and then replace the historical performance metrics and other query parameters such as `time_start` and `time_end` to obtain useful metrics for the period.



#### Get the time range of the query

```SQL
with '<查询ID>' as q_id -- 替换<查询ID>为真实查询ID，例如 D0V_Yabdl9bP9zixMQIxFA==
  , (select
      any(query_start_time_microseconds)
    , any(query_start_time_microseconds + interval query_duration_ms ms)
    , any(query_duration_ms)
    from
      system.query_log
    where query_id = q_id and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']) as time_span
  , time_span.1 as time_start
  , time_span.2 as time_end
  , time_span.3 as duration
select time_start, time_end;
```



#### Query historical metrics using a query time range

To facilitate analysis, the query time range is usually expanded by a certain amount before and after, for example, by 15 seconds, so that trends can be more easily seen. Replace the `time_start` and `time_end` parameters with the following `with` clause.

```SQL
with '<查询ID>' as q_id -- 替换<查询ID>为真实查询ID，例如 D0V_Yabdl9bP9zixMQIxFA==
  , interval 15 second as margin
  , (select
      any(query_start_time_microseconds)
    , any(query_start_time_microseconds + interval query_duration_ms ms)
    , any(query_duration_ms)
    from
      system.query_log
    where query_id = q_id and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']) as time_span
  , time_span.1 - margin as time_start
  , time_span.2 + margin as time_end
select time_start, time_end;
```



For example, the following query shows the changes in memory during the execution of the query `D0V_Yabdl9bP9zixMQIxFA==`.

```SQL
with interval 5 second as time_frame_size -- 时间间隔
, 100 as bar_width -- 条状图的宽度，当前是100
, (
  select max(value)
  from system.asynchronous_metric_log
  where metric = 'OSMemoryTotal'
) as max_mem
, 'D0V_Yabdl9bP9zixMQIxFA==' as q_id -- 替换<查询ID>为真实查询ID，例如 D0V_Yabdl9bP9zixMQIxFA==
, interval 15 second as margin
, (
  select any(query_start_time_microseconds),
    any(
      query_start_time_microseconds + interval query_duration_ms ms
    ),
    any(query_duration_ms)
  from system.query_log
  where query_id = q_id
    and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
) as time_span
, time_span.1 - margin as time_start  -- 查询范围的开始时间前一点
, time_span.2 + margin as time_end  -- 查询范围的结束时间后一点
select toStartOfInterval(event_time, time_frame_size) as timeframe,
  max(value) as `used_memory`,
  formatReadableSize(`used_memory`) as `used_memory_readable`,
  formatReadableSize(max_mem) as `max_memory`,
  bar(used_memory / max_mem, 0, 1, bar_width) -- 设置搁置
from system.asynchronous_metric_log
where metric = 'MemoryResident'
  and event_time >= time_start
  and event_time <= time_end
group by timeframe
order by timeframe desc;
```



#### Memory and CPU utilization during a query

Follow the previous method and replace `time_start` and `time_end`.

```SQL
with interval 5 minute as time_frame_size -- 时间间隔，当前是5分钟
, 25 as bar_width -- 条状图的宽度，当前是100
, (select max(value) from system.asynchronous_metric_log where metric = 'OSMemoryTotal') as max_mem
, 'D0V_Yabdl9bP9zixMQIxFA==' as q_id -- 替换<查询ID>为真实查询ID，例如 D0V_Yabdl9bP9zixMQIxFA==
, interval 15 second as margin
, (
  select any(query_start_time_microseconds),
    any(
      query_start_time_microseconds + interval query_duration_ms ms
    ),
    any(query_duration_ms)
  from system.query_log
  where query_id = q_id
    and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
) as time_span
, time_span.1 - margin as time_start  -- 查询范围的开始时间前一点
, time_span.2 + margin as time_end  -- 查询范围的结束时间后一点
select toStartOfInterval(event_time, time_frame_size) as timeframe,
	maxIf(value, metric = 'MemoryResident') as `used_memory`,
    formatReadableSize(`used_memory`) as `used_memory_readable`,
    formatReadableSize(max_mem) as `max_memory`,
    maxIf(value, metric = 'OSUserTimeNormalized') as cpu_usr,
    maxIf(value, metric = 'OSSystemTimeNormalized') as cpu_sys,    
    cpu_usr + cpu_sys as cpu,
    bar(used_memory / max_mem, 0, 1, bar_width) as barMem,
    bar(cpu_usr + cpu_sys, 0, 1, bar_width) as barCPU_usr
from system.asynchronous_metric_log
where metric in ['OSUserTimeNormalized', 'OSSystemTimeNormalized', 'MemoryResident']
	and event_time >= time_start
	and event_time <= time_end
group by timeframe
order by timeframe desc;
```



#### Other queries that are executed at the same time as the query

In some cases, the reason why a query is running slowly is not entirely its own fault, but rather because other queries are being executed in parallel. This requires an investigation of the running status of other queries during query execution.

The following query lists all concurrent queries during query execution (including the current query).

```SQL
with 'D0V_Yabdl9bP9zixMQIxFA==' as q_id -- 替换<查询ID>为真实查询ID，例如 D0V_Yabdl9bP9zixMQIxFA==
  , interval 15 second as margin
  , (select any(query_start_time_microseconds),
      any(query_start_time_microseconds + interval query_duration_ms ms),
      any(query_duration_ms)
    from system.query_log
    where query_id = q_id and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
    ) as time_span
  , time_span.1 - margin as time_start  -- 查询范围的开始时间前一点
  , time_span.2 + margin as time_end  -- 查询范围的结束时间后一点
select 
    query_id,
    query,
    event_time_microseconds,
    query_start_time_microseconds,
    (query_start_time_microseconds + interval query_duration_ms ms) as query_end_time_microseconds,
    query_duration_ms,
    formatReadableSize (memory_usage),
    type,
    databases
from
    system.query_log
where
    (query_end_time_microseconds >= time_start and query_end_time_microseconds <= time_end
    or
    query_start_time_microseconds >= time_start and query_start_time_microseconds <= time_end)
    and type in ['QueryFinish', 'ExceptionBeforeStart', 'ExceptionWhileProcessing']
order by event_time_microseconds;
```



### Query execution detail analysis

After it is known that a query has a problem, the specific reason for the problem (such as slow speed or excessive memory usage) can be analyzed in more detail.

A lot of execution details are hidden in the `trace_log` log. When the `trace_log` log is open, the CH will record the current code execution snapshot every so often during code execution, that is, the callstack, thread number, memory size requested (if it is a memory log), and other information at that time. This information is very helpful for analyzing problems such as deadlocks, performance bottlenecks, memory waste, and frequent memory requests.



#### View code execution process snapshots

The following query can obtain a series of call stack snapshots during the execution of a query. If a call stack appears frequently, it is likely to mean that the program execution is stuck in this place, which may be a performance bottleneck or a deadlock.

```SQL
with '<查询ID>' as qid  -- 替换<查询ID>为真实值，例如：Ep983OmKg4Ya9Zvyu9OB9A==
select
        event_time_microseconds,
        trace_type,
        thread_id,
        arrayMap(addr -> demangle(addressToSymbol(addr)), trace) as callstack
from
        system.trace_log
where
        trace_type in ['CPU']
        and query_id = qid
order by event_time_microseconds desc
settings allow_introspection_functions = 1;
```


#### Viewing memory requests and releases during code execution

The following query provides a snapshot of the memory requests made during the execution of a query. Each memory allocation is recorded. The following query shows how memory is consumed step by step.

```SQL
with '<查询ID>' as qid  -- 替换<查询ID>为真实值，例如：Ep983OmKg4Ya9Zvyu9OB9A==
select
        event_time_microseconds,
        size,
        formatReadableSize(size) as `本次分配内存`,
        sum(size) over w as size_running,
        formatReadableSize(size_running) as `累计分配内存`,
        thread_id ,
        arrayMap(addr -> demangle(addressToSymbol(addr)), trace) as callstack
from
        system.trace_log
where
        trace_type in ['Memory']
        and query_id = qid
window w as (rows between unbounded preceding and current row)
order by event_time_microseconds desc
settings allow_introspection_functions = 1;
```




#### Flame graph analysis

<omitted>



### IO analysis

To find queries with disk I/O as the bottleneck, you need to obtain the I/O load of all queries over a period of time and analyze the queries with heavy I/O.



#### I/O and CPU details for each SQL over a period of time

```SQL
with now() - interval 24 hour as time_start -- 开始时间
  , now() as time_end -- 结束时间
select query_id,
    query,
    query_duration_ms as `查询时长ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'RealTimeMicroseconds')] / 1000 as `实际CPU时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'UserTimeMicroseconds')] / 1000 as `用户态CPU时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'SystemTimeMicroseconds')] / 1000 as `系统态CPU时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'DiskReadElapsedMicroseconds')] / 1000 as `磁盘读取时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'DiskWriteElapsedMicroseconds')] / 1000 as `磁盘写入时间ms`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'IOBufferAllocs')] as `IO缓冲区分配次数`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'IOBufferAllocBytes')] as `IOBufferAllocBytes`,
    formatReadableSize(IOBufferAllocBytes) as `IO缓冲区分配大小`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'FileOpen')] as `文件打开次数`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'ReadBufferFromFileDescriptorReadBytes')] as ReadBufferFromFileDescriptorReadBytes,
    formatReadableSize(ReadBufferFromFileDescriptorReadBytes) as `文件读取字节数`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'WriteBufferFromFileDescriptorWriteBytes')] as WriteBufferFromFileDescriptorWriteBytes,
    formatReadableSize(WriteBufferFromFileDescriptorWriteBytes) as `文件写入字节数`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'WriteBufferFromFileDescriptorWrite')] as `文件写入次数`,
    ProfileEvents.Values [indexOf(ProfileEvents.Names, 'ZooKeeperTransactions')] as `ZooKeeper事务数`,
    ProfileEvents,
    read_rows as ReadRows,
    formatReadableSize(read_bytes) as `总计读取字节`,
    written_rows as WrittenTows,
    formatReadableSize(written_bytes) as `总计写入字节`,
    result_rows as ResultRows,
    formatReadableSize(result_bytes) as `总计输出结果字节`
from system.query_log
where (
        event_time_microseconds >= time_start
        and event_time_microseconds <= time_end
    )
    and type in ('QueryFinish', 'ExceptionWhileProcessing')
order by query_duration_ms desc
limit 100;
```



## Log analysis

To filter logs by keyword, use the following command:

```bash
grep <keyword> /var/log/clickhouse-server.log
```

For example,

```bash
grep MemoryTracker /var/log/clickhouse-server.log
```



For older log files that have been packaged in `.gz`, use the `zgrep` command to view them without having to unpack them. The command is as follows:

```bash
zgrep <keyword> /var/log/clickhouse-server.log.*.gz
```

For example,

```bash
zgrep MemoryTracker /var/log/clickhouse-server.log.*.gz
```
