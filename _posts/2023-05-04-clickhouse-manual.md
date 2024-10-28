# 常用ClickHouse问题诊断查询

Clickhouse是一个性能强大的OLAP数据库，在实际使用中会遇到各种各样的问题，同时也有很多可以调优的地方。本文阐述如何对ClickHouse做问题诊断和性能分析。



## 相关的系统表



| 序号 | 表名                           | 含义                                                         | 说明                                                      |
| ---- | ------------------------------ | ------------------------------------------------------------ | --------------------------------------------------------- |
| 1    | system.asynchronous_insert_log | 异步插入数据日志                                             | 2023年版本新加的                                          |
| 2    | system.asynchronous_metrics    | 系统当前性能度量指标                                         | 异步更新                                                  |
| 3    | system.asynchronous_metric_log | 系统历史性能度量指标                                         | 异步更新                                                  |
| 4    | system.crash_log               | 系统崩溃日志                                                 |                                                           |
| 5    | system.filesystem_cache_log    | 基于文件的缓存的日志                                         |                                                           |
| 6    | system.metric_log              | 系统历史性能度量指标                                         | 与system.asynchronous_metrics内容不一样                   |
| 7    | system.part_log                | 系统的数据part的日志，记录数据part的创建、合并、下载、移除、更新、移动 | 很有用                                                    |
| 8    | system.processes               | 当前正在运行的查询                                           | 很常用                                                    |
| 9    | system.query_log               | 系统的查询日志                                               | 很有用                                                    |
| 10   | system.query_views_log         | 各种视图的查询日志                                           | 通过实验发现并不会记录任何日志，即使打开log_query_views。 |
| 11   | system.query_thread_log        | 系统查询的线程方面日志                                       | 记录 thread_name, thread_id, master_thread_id 信息        |
| 12   | system.opentelemetry_span_log  | OpenTelemetry的span日志                                      | 见下方关于OpenTelemetry 的说明                            |
| 13   | system.processors_profile_log  | 查询执行过程中的详细i性能信息                                |                                                           |
| 14   | system.session_log             | 客户端登录/登出日志                                          | 可以用于安全防护                                          |
| 15   | system.settings                | 系统配置的设置信息                                           |                                                           |
| 16   | system.text_log                | 系统的文本日志，与日志文件的内容相同                         |                                                           |
| 17   | system.trace_log               | 系统运行跟踪日志，包含callstack。                            | 很有用                                                    |
| 18   | system.transactions_info_log   | 事务工作日志，包括开始和结束时间、状态                       |                                                           |
| 19   | system.zookeeper_log           | 对ZooKeeper的操作日志                                        |                                                           |

OpenTelemetry 是一个开放标准，用于生成、收集和处理分布式系统的跟踪、日志和度量数据。它提供了一组 API 和 SDK，可以集成到应用程序和基础设施中，以收集和传递数据，并将其汇聚到一个集中式的存储库中，以支持分析、监视和故障排除。




## 性能度量

性能度量的数据来源于`system.asynchronous_metrics`、`system.asynchronous_metric_log`、`system.metric_log`。



### 实时性能度量



#### 展示当前所有的性能度量指标

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
度量指标非常丰富，有300多个。以下是一些指标的说明：

| 度量指标                                      | 含义                                                 |
| --------------------------------------------- | ---------------------------------------------------- |
| CompiledExpressionCacheCount                  | 已编译并保存在缓存中的表达式的数量                   |
| jemalloc.*                                    | jemalloc相关指标，需要深入理解jemalloc内存分配       |
| MarkCacheBytes / MarkCacheFiles               | .mrk 文件的缓存                                      |
| MemoryCode                                    | ClickHouse代码所占内存大小                           |
| MemoryDataAndStack                            | 数据和堆栈所占内存大小（包括虚拟内存）               |
| MemoryResident                                | 占用真实内存的大小                                   |
| MemoryShared                                  | 共享内存大小                                         |
| MemoryVirtual                                 | 虚拟内存大小                                         |
| NumberOfDatabases                             | 数据库的数量                                         |
| NumberOfTables                                | 表的数量                                             |
| ReplicasMaxAbsoluteDelay                      | 集群副本最大的绝对延迟时间（单位：秒）               |
| ReplicasMaxRelativeDelay                      | 集群副本最大的相对延迟时间（单位：秒）               |
| ReplicasMaxInsertsInQueue                     | 单个Replicated表的要从其他副本抓取的part的最大数量   |
| ReplicasSumInsertsInQueue                     | 所有的Replicated表的从其他副本抓取的part的总计数量   |
| ReplicasMaxMergesInQueue                      | 单个Replicated表的merge队列里的merge任务的最大数量   |
| ReplicasSumMergesInQueue                      | 所有的Replicated表的merge队列里的merge任务的总计数量 |
| ReplicasMaxQueueSize                          | 单个Replicated表的任务队列的任务的最大数量           |
| ReplicasSumQueueSize                          | 全部Replicated表的任务队列的任务的最大数量           |
| UncompressedCacheBytes/UncompressedCacheCells | 解压缩后的数据的缓存所占内存空间                     |
| Uptime                                        | ClickHouse的在线累计时间（单位：秒）                 |



#### 重点指标 - 内存相关
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



#### 重点指标 - CPU相关

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
CPU的每个核都有对应的CPU指标，目前每个CPU核有大约10个指标，以`CPUx`为后缀。

| 度量指标（去掉后缀CPUx）     | 解释                                                         |
| ---------------------------- | ------------------------------------------------------------ |
| OSGuestNiceTime              | 度量虚拟机中的进程的“好”时间（nice time）的指标。Nice time表示进程优先级，范围为-20到+19，默认值是0。nice 值越小，表示该进程的优先级越高，即更容易获得 CPU 时间片。 |
| OSGuestTime                  | 度量虚拟机中的进程的时间的指标，表示虚拟机中运行的进程在使用 CPU 时的总时间，单位为纳秒，可以用来监测虚拟机中进程的 CPU 利用率和主机系统的负载情况。 |
| OSIOWaitTime                 | 进程等待 I/O 操作的时间的指标，可以用来监测进程对 I/O 设备的使用负载情况。一般这个指标如果高，说明瓶颈在I/O上，对强调吞吐量的系统是不利的。 |
| OSIdleTime                   | CPU空闲时间的指标，单位为纳秒。                              |
| OSIrqTime                    | 度量进程在硬件中断（如 I/O 设备完成操作、时钟中断等）服务例程中消耗 CPU 时间的指标。这个指标主要表示I/O中断对系统的影响，单位为纳秒。这个指标过高表示I/O中断处理时间是瓶颈，但优化的方法可能不在软件层面。 |
| OSNiceTime                   | 度量主机中进程的“好”时间（nice time）的指标。Nice time表示进程优先级，范围为-20到+19，默认值是0。nice 值越小，表示该进程的优先级越高，即更容易获得 CPU 时间片。 |
| OSSoftIrqTime                | 度量软中断服务例程消耗 CPU 时间的指标，单位为纳秒。          |
| OSStealTime                  | 度量虚拟化环境中虚拟机被宿主机“偷走” CPU 时间的指标，表示虚拟机中运行的进程因宿主机“偷走” CPU 时间而被迫等待的时间，单位为纳秒。该指标过高表示宿主机的负载过高，资源争夺激烈。 |
| OSSystemTime                 | CPU系统态时间的指标，表示进程在内核态中使用 CPU 的总时间，单位为纳秒。 |
| OSUserTime                   | CPU用户态时间的指标，表示进程在用户态中使用 CPU 的总时间，单位为纳秒。 |
| OSCPUVirtualTimeMicroseconds | 虚拟CPU上的运行时间，单位微秒。                              |

参考：[Metrics List](https://pastila.nl/?00014be2/6cb3dc5f2fc8f3c8ae55bd8a2ea39c2d.md)



### 历史性能指标

把 实时性能度量中的表`system.asynchronous_metrics`替换成`system.asynchronous_metric_log`，`system.asynchronous_metric_log`多了`event_date`和`event_time`两列。

例如，看历史内存相关的度量，用如下查询：
```SQL
select *
from system.asynchronous_metric_log
where
       metric ilike '%memory%'
order by
        event_time
desc;
```

下面介绍一些常用查询。



#### 内存占用峰值变化趋势（由近及远）
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



#### CPU使用峰值变化趋势

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



#### CPU与内存峰值变化趋势

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



#### 各种类型查询内存使用统计

用以下查询获得某个时间段的各种类型查询的内存使用统计结果。

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



### MergeTree相关的性能指标

#### Merge的性能指标

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



#### Mutations的性能指标

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




## 故障处理

在遇到当前系统发生故障的情况下，按照下面介绍的方法一一排除。



### 当前运行的查询

通过了解当前运行的查询，可以了解目前是否有查询长期运行。

```SQL
select query_id, * from system.processes;
```

或者更聚焦一些，

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



### 强制终止查询

对于长期执行而不结束的查询，需要及时终止以释放系统资源给其他查询使用，这样避免整个系统被卡死。

```SQL
kill query where query_id = '<查询ID>'; -- 替换<查询ID>为真正要终止的查询ID
```



### 查询错误分析

首先根据查询的错误提示找出错误关键字，替换`keyword`，用以下查询得到要找的出错的查询。

```SQL
with '%<包含关键字>%' as keyword  -- 把<包含关键字>替换为实际关键字
select event_time_microseconds, query_id, query, `exception`, exception_code, stack_trace  from system.query_log where exception ilike keyword order by event_time_microseconds desc;
```

通过`stack_trace`可以大致知道抛异常的地方。



### 系统崩溃分析

#### 查看所有崩溃日志

```SQL
select * from system.crash_log order by event_time desc;
```



#### 按照构建版本统计崩溃次数

```SQL
select min(event_time) as begin_time, max(event_time) as end_time, build_id, count() from system.crash_log group by build_id order by end_time desc;
```



## 调优分析

调优分析一般分为两步：1. 找到有问题的一个或者多个查询；2. 仔细审视有问题的查询的执行细节以及相关的性能指标细节。



### 已加载的表所占用内存分析

如果发现ClickHouse启动后在任何操作都没有的情况下就占用了大量的内存，很可能是加载的表占用过多内存。特别是`Join`、`Memory`、`Set` 引擎的表，这些会把数据全部加载到内存里。我们需要找出这样的加载就占内存的表。

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

同时MergeTree引擎家族也会预加载一些数据在内存中，也需要找出来。

```SQL
SELECT
	count() as `parts数量`,
    sumIf(data_uncompressed_bytes, part_type = 'InMemory') as `内存中的数据片大小`,
    formatReadableSize(sum(primary_key_bytes_in_memory)) as `主键占用内存`,
    formatReadableSize(sum(primary_key_bytes_in_memory_allocated)) as `为主键分配的内存大小`
FROM system.parts;
```



#### 用shell脚本实时刷新

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



### 需优化的查询的定位

在一个时间段内发生的众多查询中找出最需要优化的查询。

#### 某个时间段的所有查询并按执行时长排序

得到某个时间段里的所有查询并按执行时长从大到小排序。这样可以快速找到最耗时的查询。

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



#### 某个时间段的所有查询并按内存消耗大小排序

得到某个时间段里的所有查询并按内存消耗从大到小排序。这样可以快速找到最消耗内存的查询。

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



#### 某个时间段最耗CPU的SQL语句

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



#### 某个时间段最耗内存的SQL语句

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



#### 未完成的查询

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



#### 重点关注的高消耗查询

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



### 调查某个查询执行期间的情况

要调查分析某个具体查询的执行性能，首先得到这个查询的开始和结束时间，然后替换历史性能指标等查询中的 `time_start` 和 `time_end`，得到该期间的有用的度量指标。



#### 获取查询的时间范围

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



#### 用查询时间范围查询历史度量指标

为了方便分析，通常会将查询时间范围前后扩大一些，例如前后增加15秒，这样容易看到变化趋势。用以下`with`短语替换 `time_start` 与 `time_end` 参数。

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



例如，以下展示查询`D0V_Yabdl9bP9zixMQIxFA==`执行期间内存的变化。

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



#### 某查询运行时内存与CPU利用率

按照之前的方法，替换`time_start`与`time_end`。

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



#### 查询执行期间同时执行的其他查询

某些情况下一个查询运行过慢的原因并不完全是自身原因，而是因为同时有其他查询在并行执行，这就需要研究查询执行期间的其他查询的运行情况。

用以下查询列出查询期间所有的同时发生的查询（包括本查询在内）。

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



### 查询执行细节分析

当知道某个查询有问题之后，就可以更细节地分析某个查询的具体的问题（例如速度慢或者内存占用过多）的原因。

很多执行细节信息隐藏在`trace_log`日志中，在`trace_log`日志打开的时，CH在代码执行过程中每隔一段时间会记录当前的代码执行快照，即当时的代码执行callstack、线程号、申请内存大小（如果是关于内存的日志）等信息。这些信息对分析死锁、性能瓶颈、内存浪费、内存频繁申请等问题很有帮助。



#### 查看代码执行过程快照

下面查询可以获得某个查询的执行过程中的一系列调用堆栈快照。如果某个callstack频繁出现，就大概率意味着程序执行卡在了这个地方，这个地方可能就是性能瓶颈，或者是出现了死锁。

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


#### 查看代码执行过程的内存申请释放

下面查询可以获得某个查询的执行过程中的一系列申请内存的情况的快照。每次内存的分配都有记录。通过以下查询可以看到内存是怎么一步步被消耗的。

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



#### 火焰图分析

在另外一篇中详细介绍。

### IO分析

要找出磁盘I/O为瓶颈的查询，需要获得一段时间内的所有查询在I/O方面的负载情况，分析其中I/O重的查询。



#### 一段时间内每个SQL的I/O以及CPU详细情况

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



## 日志分析

按照关键字过滤日志，使用如下命令：

```bash
grep <关键字> /var/log/clickhouse-server.log
```

例如，

```bash
grep MemoryTracker /var/log/clickhouse-server.log
```



对于旧的已经打包成`.gz`的日志文件，用`zgrep`命令去查看，不需要专门解压缩了。命令如下：

```bash
zgrep <关键字> /var/log/clickhouse-server.log.*.gz
```

例如，

```bash
zgrep MemoryTracker /var/log/clickhouse-server.log.*.gz
```
