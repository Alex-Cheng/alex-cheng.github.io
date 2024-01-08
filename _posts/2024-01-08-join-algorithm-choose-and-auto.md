# ClickHouse的JOIN算法选择逻辑以及auto选项

ClickHouse中的JOIN的算法有6种：
1. Direct;
2. Partial merge;
3. Hash;
4. Grace hash;
5. Full sorting merge;
6. Parallel hash。

Setting配置`join_algorithm`用于指定JOIN算法，它可以设置为多个值，例如join_algorithm='direct,hash,partial_merge'。在选择最终JOIN算法的时候是根据setting配置`join_algorithm`, 以及JOIN操作的Strictness、Kind和参与JOIN的右表表引擎类型共同决定。
Setting配置`join_algorithm`的可选值（可以组合，前面的例子已经展示了）如下所示：
1. default
2. auto
3. hash
4. partial_merge
5. prefer_partial_merge
6. parallel_hash
7. direct
8. full_sorting_merge
9. grace_hash

## JOIN算法的选择逻辑

上面已经提到`join_algorithm`上可以指定多个值，相当于是一个多路开关，它规定了哪些JOIN算法可以使用。而在具体JOIN语句执行时则根据具体情况（例如Strictness、Kind和右表表引擎类型）选择合适的JOIN算法。如果没有合适的JOIN算法，则会报错。选择逻辑按照优先级从高往低列举如下：

1. 如果setting `join_algorithm` 包含'direct'或'default'，则优先尝试Direct join。Direct join的使用条件是：

   | Strictness | Kind | 右表引擎                                             | JOIN关键字/条件                                    |
   | ---------- | ---- | ---------------------------------------------------- | -------------------------------------------------- |
   | ANY        | LEFT | 键值对表引擎，如<br />Join engine、Dictionary engine | 必须为Join表引擎的关键字<br />单连接条件（不带OR） |

   

2. 如果setting `join_algorithm` 包含'partial_merge'或者'prefer_partial_merge'，则尝试使用Partial(sorting) merge join。Partial(sorting) merge join的使用条件是：

   | Strictness  | Kind                                 | 右表引擎 | JOIN关键字/条件      |
   | ----------- | ------------------------------------ | -------- | -------------------- |
   | ALL         | INNER<br />LEFT<br />RIGHT<br />FULL | -        | 单连接条件（不带OR） |
   | ANY \| SEMI | INNER<br />LEFT                      | -        | 连接条件（不带OR）   |

   

3. 如果setting `join_algorithm` 包含'parallel_hash'，则尝试使用Parallel hash join。Parallel hash join的使用条件是：

   | Strictness     | Kind            | 右表引擎 | JOIN关键字/条件      |
   | -------------- | --------------- | -------- | -------------------- |
   | 除了ASOF的所有 | INNER<br />LEFT | -        | 单连接条件（不带OR） |

   

4. 如果setting `join_algorithm` 包含'hash'或'default'，或者虽然包含'parallel_hash'或'prefer_partial_merge'但是前面对应使用条件不满足，则尝试使用Hash join。Hash join的使用条件是：

   | Strictness | Kind | 右表引擎 | JOIN关键字/条件 |
   | ---------- | ---- | -------- | --------------- |
   | 所有       | 所有 | -        | -               |

   

5. 如果setting `join_algorithm` 包含'full_sorting_merge'，则尝试使用Full sorting merge join。Full sorting merge join的使用条件是：

   | Strictness | Kind                                 | 右表引擎 | JOIN关键字/条件      |
   | ---------- | ------------------------------------ | -------- | -------------------- |
   | ALL \| ANY | INNER<br />LEFT<br />RIGHT<br />FULL | -        | 单连接条件（不带OR） |

   

6. 如果setting `join_algorithm` 包含'grace_hash'，则尝试使用Grace hash join。Grace hash join的使用条件是：

   | Strictness     | Kind                                 | 右表引擎 | JOIN关键字/条件      |
   | -------------- | ------------------------------------ | -------- | -------------------- |
   | 除了ASOF的所有 | INNER<br />LEFT<br />RIGHT<br />FULL |          | 单连接条件（不带OR） |

   

7. 如果setting `join_algorithm` 包含'auto'，则尝试先使用Hash join。当切换条件触发且Partial merge join的使用条件满足时切换到Partial merge join。





## Auto的逻辑

当`join_algorithm`设置为'auto'时，ClickHouse会自行（不一定算是很智能）根据内存消耗情况选择JOIN算法。

首先采用hash join，并在JOIN运算期间记录生成的哈希表的行数和所消耗的内存。当行数或者消耗内存大小达到阈值时，切换到partial merge join算法。

阈值由settings设置`max_rows_in_join` 和`max_bytes_in_join`设定。



## 设置join_overflow_mode

当`join_algorithm`为'hash'时，在阈值`max_rows_in_join` 和`max_bytes_in_join`被超过时的行为取决于`join_overflow_mode`的设定。join_overflow_mode有两种取值：

1. THROW

   抛异常。

2. BREAK

   中断执行，返回部分结果。



