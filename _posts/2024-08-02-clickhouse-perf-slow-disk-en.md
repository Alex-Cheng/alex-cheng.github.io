# ClickHouse performance tuning - when disk IO is the bottleneck

## Introduction

ClickHouse performance tuning is a big topic. Although ClickHouse is known for its high-speed data processing capabilities, in actual use, disk IO often becomes the bottleneck that affects system performance. This article will discuss how to improve the overall performance of ClickHouse through a series of optimization measures when disk IO becomes the bottleneck.

## Disk I/O bottleneck
A disk I/O bottleneck refers to a situation in which the disk's read/write speed cannot keep up with the demand for data processing during the data read/write process, resulting in a decline in system performance. This situation is particularly obvious in scenarios with large amounts of data and frequent queries. Common symptoms include increased query latency, longer system response times, and low CPU utilization.

### Confirm that it is a disk I/O bottleneck

Find time-consuming queries, execute them, and observe the execution statistics, focusing on the amount of data read by IO. For example, the following information indicates that the query reads a large amount of data, which may be a disk IO bottleneck.
0 rows in set. Elapsed: 38.308 sec. Peak memory: 1.39 GiB. Processed 22.89 million rows, 385.79 GB (597.51 thousand rows/s., 10.07 GB/s.)

Convert the MergeTree table to a Memory table and then execute the same query. Be careful to avoid querying and using large data columns that are not used to avoid memory overflow. Here is an example.

```SQL
CREATE TABLE `big_table1_memory`
ENGINE = Memory AS
SELECT * EXCEPT `unused_big_column`
FROM `big_table1`
ORDER BY `id` ASC
```

Change `big_table1` in the original query to `big_table1_memory`, execute the query, and compare the performance differences.
If the memory difference is significant, it can basically be determined that it is a disk IO bottleneck (but it may also be a data decompression bottleneck).

### Ensure that the memory is sufficient

The solution to the disk IO bottleneck is to move the data to memory, so it is necessary to ensure that the memory is sufficient. In a practical example, the server has 128G of memory, which is more than sufficient and very suitable for using the methods in this article to improve performance.

### Enable data block caching

When optimizing ClickHouse performance, it is important to understand and configure caching parameters. The following is an explanation of several key configuration items and their interrelationships:

#### Key configuration
1. uncompressed_cache_size

The `uncompressed_cache_size` parameter is a server parameter set in config.xml and is used to specify the cache size of ClickHouse for storing uncompressed data in memory. The uncompressed data cache can reduce disk access and thus improve query performance.
- Default value: By default, this value may be automatically configured based on the system memory size, and is usually a fraction of the total memory.
- Function: After data is read from the disk, ClickHouse stores the uncompressed data blocks in this cache. If the same data block is accessed again, it can be read directly from the cache, avoiding repeated decompression operations.

2. use_uncompressed_cache

The `use_uncompressed_cache` parameter is a user parameter set in users.xml. It is a boolean value that is used to enable or disable the caching of uncompressed data.
- Default value: usually true, which means that the uncompressed cache is enabled.
- Function: when set to true, ClickHouse will use the uncompressed data cache to improve query performance. When set to false, ClickHouse will not use this cache.

3. merge_tree_max_rows_to_use_cache

The `merge_tree_max_rows_to_use_cache` parameter is a user parameter set in users.xml that defines a threshold value below which a data block can be cached in the uncompressed data block cache.
- Default value: Depends on the specific version and configuration.
- Function: This parameter helps control which data blocks can be used in the uncompressed cache, thereby preventing excessively large data blocks from taking up cache space.

4. merge_tree_max_bytes_to_use_cache

The parameter `merge_tree_max_bytes_to_use_cache` is a user parameter that is set in users.xml and defines a threshold value below which a data block can be cached in the uncompressed cache.
- Default value: Depends on the version and configuration.
- Function: Similar to merge_tree_max_rows_to_use_cache, this parameter helps control which data blocks can be used in the uncompressed cache, preventing excessively large data blocks from taking up cache space.

#### Interrelation between parameters

- uncompressed_cache_size and use_uncompressed_cache: uncompressed_cache_size defines the size of the cache, while use_uncompressed_cache determines whether the cache is enabled. If the cache is not enabled (use_uncompressed_cache = false), the setting of uncompressed_cache_size will be invalid.

- merge_tree_max_rows_to_use_cache and merge_tree_max_bytes_to_use_cache: these two parameters together control which data blocks can be used in the uncompressed cache. A data block must meet both the row count and byte size limits in order to be cached in the uncompressed cache.

Overall relationship: uncompressed_cache_size provides the cache space, use_uncompressed_cache determines whether to use this space, and merge_tree_max_rows_to_use_cache and merge_tree_max_bytes_to_use_cache refine the cache strategy to ensure that only small data blocks are cached, thereby effectively using memory and improving performance.

#### Example configuration
Assuming that the system has sufficient memory, here is an example configuration:

uncompressed_cache_size: 10GB
use_uncompressed_cache: true
merge_tree_max_rows_to_use_cache: 100000
merge_tree_max_bytes_to_use_cache: 104857600 # 100MB

- uncompressed_cache_size: 10GB: specifies that 10GB of memory is used for the uncompressed data cache.
- use_uncompressed_cache: true: enables the uncompressed data cache.
- merge_tree_max_rows_to_use_cache: 100000: the uncompressed cache can be used when the number of rows in the data block is less than 100,000.
- merge_tree_max_bytes_to_use_cache: 104857600: the uncompressed cache can be used when the size of the data block is less than 100MB.

By properly configuring these parameters, the query performance of ClickHouse can be effectively improved, especially when disk IO becomes a bottleneck.

#### Check the hit rate
Use the following query to observe the cache hit rate, which is the cumulative value from the time the server was started.

```
SELECT
    event,
    value, description
FROM
    system.events
WHERE
    event LIKE '%Cache%';
```


## Other factors

Compression algorithms reduce the load on disk I/O, but increase the load on the CPU.

### The impact of compression algorithms on ClickHouse performance

In ClickHouse, the choice of compression algorithm has a significant impact on system performance. By default, ClickHouse uses the LZ4 compression algorithm, which provides a good balance between performance and compression ratio. The following is a detailed explanation of how the compression algorithm affects disk IO and CPU load.

**The role of the compression algorithm**

Compression algorithms reduce the workload on disk I/O by reducing the storage size of data. This is reflected in
- Reduced disk space occupation: Compressed data takes up less disk space, which saves storage costs.
- Reduced frequency of disk I/O: Since the data becomes smaller, the number of disk blocks accessed during read and write operations is reduced, which reduces the frequency of disk I/O.

However, compressed data needs to be decompressed when read, which increases the CPU load. For example, although LZ4 is a fast compression algorithm, decompression still requires some CPU resources.

**Performance impact of compression algorithms**

- Reduced disk I/O: Compression algorithms significantly reduce the storage size of data, thereby reducing the number of disk read and write operations. This is particularly important for systems with I/O bottlenecks.
- Increased CPU load: Decompression operations require CPU resources. Although LZ4 decompression is fast, the CPU load may still increase significantly when the amount of data is very large.
