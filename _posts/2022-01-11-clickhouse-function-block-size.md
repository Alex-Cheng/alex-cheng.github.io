# 设置max_block_size对CH函数执行的影响

max_block_size设置对某些CH函数的执行结果是有影响的。

## 函数接收参数的形式是column

CH处理数据的基本单位是block，block顾名思义是数据表中的“一块”，即行的子集+列的子集。而函数接收参数的形式是column，column可以看作是仅有“一列”的block，而column里面的数据是数据表中该列的一部分数据。

## 不同的参数对应不同的column
一般CH函数中的参数有几种：
1. 常数
   例如 `select toString(100)`

2. 列 
   例如 `select toString(number) from numbers(10)`

3. 子函数
   例如 `select toString(pow(number,2)) from numbers(10)`
   
## 列作为参数时input_rows_count的含义

CH的函数接口是`IFunction`和`IExecutableFunction`，执行体的函数签名如下所示，其中有一个参数是`input_rows_count`。

```
    ColumnPtr executeImpl(const ColumnsWithTypeAndName & arguments, const DataTypePtr & result_type, size_t input_rows_count) const override;
```

当SQL上的函数的参数为列时，例如`select toString(pow(field1,2)) from table1`。CH会把table1的列field1的数据分成连续的几段，每段的行数是由max_block_size（也受其他一些因素影响但主要是max_block_size）决定的。例如max_block_size等于10000，那么数据分段就是(0~10000), (10000~20000), (20000, 30000)... 

传入的参数`input_rows_count`就是表示arguments里的column列的数据大小（即行数）。如果数据分成(0~10000), (10000~20000), (20000, 30000)三段，则会调用函数执行体三次，每次的`input_rows_count`参数为10000。

### 分段的好处

分段的好处有几点：

1. 可以并行，多个线程同时调用函数执行体，传入不同分段为参数；
2. 节约内存，每次处理一部分，内存重复利用，避免一次消耗太多内存。

### 分段会影响函数执行结果

以下面的SQL为例，

```
SELECT
    number,
    runningDifference(number) AS diff
FROM numbers(200000)
WHERE diff != 1
```

这段SQL是求除了“第一”行之外的每行的number列的值和上一行number列的值的差，“第一行”的runningDifference()函数的返回值直接设为0。因为number列是自增的，差值总是为1，理论上来说我们只有一个“第一行”，所以结果中只会有一个0，其他全是1。但是运行结果则不是这样的。我们会看到有两个0，即有两个“第一行”。

```
SELECT
    number,
    runningDifference(number) AS diff
FROM numbers(200000)
WHERE diff != 1

Query id: cfdc8140-ee8c-499c-a487-dbf4e708b271

┌─number─┬─diff─┐
│      0 │    0 │
└────────┴──────┘
┌─number─┬─diff─┐
│  65505 │    0 │
└────────┴──────┘
┌─number─┬─diff─┐
│ 131010 │    0 │
└────────┴──────┘
┌─number─┬─diff─┐
│ 196515 │    0 │
└────────┴──────┘

4 rows in set. Elapsed: 0.002 sec. Processed 262.02 thousand rows, 2.10 MB (125.09 million rows/s., 1.00 GB/s.)
```

行0，65505, 131010, 196515都是被认为是“第一行”，可以看出都是65505的倍数（65506 * n, n = 0,1,2,3）。这是因为作为输入参数的列的数据被按照65505大小分成了4段，每段数据作为参数调用一次函数的执行体，每段的第一行都被认为是“第一行”而使得该行上函数运行结果为0。

### 控制分段大小

在查询末尾加上`settings max_block_size=<分段最大行数>`，例如`settings max_block_size=100000000`，就能控制分段的行数大小。

对于需要全局数据才能得出正确结果的函数，例如neighbor函数，需要设定`settings max_block_size`保证一次传入全部数据。
