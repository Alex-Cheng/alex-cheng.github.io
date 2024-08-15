# ClickHouse性能调优 - 当磁盘IO是瓶颈的时候

##引言

ClickHouse的性能调优问题是一个大的话题。虽然ClickHouse以其高速的数据处理能力而闻名，但在实际使用中，磁盘IO常常成为影响系统性能的瓶颈。本文将探讨在磁盘IO成为瓶颈时，如何通过一系列优化措施来提升ClickHouse的整体性能。

## 磁盘IO瓶颈
磁盘IO瓶颈指的是在数据读写过程中，磁盘的读写速度跟不上数据处理的需求，导致系统性能下降。这种情况在数据量大、查询频繁的场景下尤为明显。常见的症状包括查询延迟增大、系统响应时间变长，同时CPU利用率并不高。

### 确认是磁盘IO瓶颈

找到耗时的查询，执行查询，观察执行统计信息，重点关注IO读取数据量。例如以下信息就表明查询所读取的数据很大，可能是磁盘IO瓶颈。
0 rows in set. Elapsed: 38.308 sec. Peak memory: 1.39 GiB. Processed 22.89 million rows, 385.79 GB (597.51 thousand rows/s., 10.07 GB/s.)

把MergeTree表转成Memory表，然后执行同样的查询。注意避开查询并用不到的大数据列，避免内存溢出。以下是一个例子。

```SQL
CREATE TABLE `big_table1_memory`
ENGINE = Memory AS
SELECT * EXCEPT `unused_big_column`
FROM `big_table1`
ORDER BY `id` ASC
```

将原先查询里的`big_table1`修改成`big_table1_memory`，执行查询，比较性能差异。
如果内存差异很大，基本可以判定是磁盘IO瓶颈（但也有可能是数据解压缩瓶颈）。

### 保证内存足够

解决磁盘IO瓶颈的方法是把数据搬到内存，所以必须保证内存充足。在一个实际例子中，服务器内存128G，非常充足，非常合适使用本文方法提升性能。

### 启用数据块缓存

在优化ClickHouse性能时，理解和配置缓存参数是非常重要的。以下是对几个关键配置项及其相互关系的解释：

#### 关键配置
1. uncompressed_cache_size

`uncompressed_cache_size` 参数是服务器参数，在config.xml中设置，用于指定ClickHouse在内存中用于存储未压缩数据的缓存大小。未压缩数据缓存可以减少对磁盘的访问，从而提高查询性能。
- 默认值：默认情况下，这个值可能会根据系统内存大小自动配置，通常为总内存的一部分。
- 作用：当数据从磁盘读取后，ClickHouse会将未压缩的数据块存储在这个缓存中。如果相同的数据块再次被访问，可以直接从缓存中读取，避免了重复的解压缩操作。

2. use_uncompressed_cache

`use_uncompressed_cache` 参数是用户参数，在users.xml中设置，是一个布尔值，用于启用或禁用未压缩数据的缓存。
- 默认值：通常为true，表示启用未压缩缓存。
- 作用：设置为true时，ClickHouse将使用未压缩数据缓存来提升查询性能。设置为false时，ClickHouse将不会使用这个缓存。

3. merge_tree_max_rows_to_use_cache

`merge_tree_max_rows_to_use_cache` 参数是用户参数，在users.xml中设置，定义了一个阈值，表示如果一个数据块的行数小于这个值，则该数据块可以被缓存在未压缩数据块缓存中。
- 默认值：根据具体版本和配置情况而定。
- 作用：这个参数帮助控制哪些数据块可以使用未压缩缓存，从而防止过大的数据块占用缓存空间。

4. merge_tree_max_bytes_to_use_cache

`merge_tree_max_bytes_to_use_cache` 参数是用户参数，在users.xml中设置，定义了一个阈值，表示如果一个数据块的大小（以字节为单位）小于这个值，则该数据块可以被缓存在未压缩缓存中。
- 默认值：根据具体版本和配置情况而定。
- 作用：与merge_tree_max_rows_to_use_cache类似，这个参数帮助控制哪些数据块可以使用未压缩缓存，防止过大的数据块占用缓存空间。

#### 参数之间的相互关系

- uncompressed_cache_size与use_uncompressed_cache：uncompressed_cache_size定义了缓存的大小，而use_uncompressed_cache决定了是否启用这个缓存。如果未启用缓存（use_uncompressed_cache = false），则uncompressed_cache_size的设置将无效。

- merge_tree_max_rows_to_use_cache与merge_tree_max_bytes_to_use_cache：这两个参数共同控制了哪些数据块可以使用未压缩缓存。一个数据块必须同时满足行数和字节大小的限制，才能被缓存在未压缩缓存中。

- 整体关系：uncompressed_cache_size提供了缓存空间，use_uncompressed_cache决定是否使用这个空间，而merge_tree_max_rows_to_use_cache和merge_tree_max_bytes_to_use_cache则细化了缓存策略，确保只有较小的数据块被缓存，从而有效利用内存并提升性能。

#### 示例配置
假设系统有足够的内存，以下是一个示例配置：

uncompressed_cache_size: 10GB
use_uncompressed_cache: true
merge_tree_max_rows_to_use_cache: 100000
merge_tree_max_bytes_to_use_cache: 104857600  # 100MB

- uncompressed_cache_size: 10GB：指定10GB的内存用于未压缩数据缓存。
- use_uncompressed_cache: true：启用未压缩数据缓存。
- merge_tree_max_rows_to_use_cache: 100000：数据块的行数少于100,000行时可以使用未压缩缓存。
- merge_tree_max_bytes_to_use_cache: 104857600：数据块的大小小于100MB时可以使用未压缩缓存。

通过合理配置这些参数，可以有效提升ClickHouse的查询性能，尤其是在磁盘IO成为瓶颈的情况下。

#### 检查命中率
用以下查询观察缓存命中率，这个命中率是从服务器启动到现在的累计值。

```
SELECT
    event,
    value, description
FROM
    system.events
WHERE
    event LIKE '%Cache%';
```

## 其他因素

压缩算法会减少磁盘IO的负载，但是会增加CPU的负载。

### 压缩算法对ClickHouse性能的影响

在ClickHouse中，压缩算法的选择对系统性能有着重要的影响。默认情况下，ClickHouse使用LZ4压缩算法，它在性能和压缩率之间提供了良好的平衡。以下是对压缩算法如何影响磁盘IO和CPU负载的详细解释。

**压缩算法的作用**

压缩算法通过减少数据的存储大小，降低了磁盘IO的工作量。具体表现为：
- 减少磁盘空间占用：压缩后的数据占用更少的磁盘空间，从而节省存储成本。
- 降低磁盘IO频率：由于数据变小，读取和写入操作需要访问的磁盘块数量减少，从而降低了磁盘IO的频率。

然而，压缩数据在读取时需要解压缩，这会增加CPU的负载。以LZ4为例，虽然它是一种快速的压缩算法，但解压缩操作仍然需要一定的CPU资源。

**压缩算法对性能的影响**

- 磁盘IO减少：压缩算法显著降低了数据的存储大小，因此减少了磁盘读写操作的次数。这对于IO瓶颈的系统尤为重要。
- CPU负载增加：解压缩操作需要消耗CPU资源。尽管LZ4的解压缩速度很快，但在数据量非常大的情况下，CPU的负载仍可能显著增加。

