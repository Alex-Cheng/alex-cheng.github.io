# 关于ClickHouse的一些小技巧

## 设置变量
```SQL
set param_name='Alex';
select {name:String};
```

## projection的使用
ClickHouse里的projection（投影）是物化的，也就是说数据会复制存一份。
Projection对于不同的排序的查询的效率提升很有帮助，特别是行数很大的表。因为如果有一个projection的`order by`的设定跟查询的`order by`一样，则可以直接读取projection而不用排序数据。

在2亿行数据的大宽表`variant_simulate._joined_events`上做实验。

按照`_Dimension1_T1`排序，查询语句为：

```sql
select _Dimension1_T1 from  _joined_events order by _Dimension1_T1 format Null
```

时间是4秒。
```sql
Query id: 056df638-72b4-486f-b18a-94507ef2ecf7

Ok.

0 rows in set. Elapsed: 4.218 sec. Peak memory: 3.38 GiB. Processed 200.00 million rows, 1.80 GB (47.42 million rows/s., 426.78 MB/s.)
Peak memory usage: 1.70 GiB.
```

添加projection投影，命名为`_dimension1_t1_proj`，并物化它，再执行同一个查询。

```sql
alter table _joined_events
add projection _dimension1_t1_proj (
        select _Dimension1_T1
        from _joined_events
        order by _Dimension1_T1
    );
    
alter table _joined_events materialize projection _dimension1_t1_proj;
```
查询及执行结果为：
```sql
select _Dimension1_T1 from  _joined_events order by _Dimension1_T1 format Null

0 rows in set. Elapsed: 1.874 sec. Peak memory: 3.38 GiB. Processed 200.00 million rows, 1.80 GB (106.73 million rows/s., 960.61 MB/s.)
Peak memory usage: 14.95 MiB.
```
时间是1.8秒。快了2倍不止。

