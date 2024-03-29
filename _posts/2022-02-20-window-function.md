Window函数就是窗口函数，它是一个mapping性质的函数，是定义在SQL标准里的，在Oracle、MySQL 8.0、MSSQL上都被支持。在大数据分析的时候非常有用。

Window函数里可以包含分组（不叫group by，而是叫partition by）和排序，然后根据分组和排序后的结果做聚合等操作，但是跟真正的聚合函数有本质的区别。这个区别就是Window函数不会真的聚合多行为一行，即不会改变表的行数。所以它是一个mapping函数，而不是reduce 函数。

Window函数主要分为三组：

1. 排序函数
比如在包含多个班级的成绩的表中，为每个班级的学生成绩生成排序号。

2. 聚合函数
比如在包含多个班级的成绩的表中，为每个班级的学生成绩生成（当前行加上之前的行的行集的）平均成绩。

3. 分析函数
比如找到当前行的上一行的同列的值，用于前后比较。

Window函数在大数据分析中非常有用，尤其是在流程挖掘细分领域，经常需要把多行的某列的数据放在一起做运算，而一般的关系型数据库通常只对一行的多列数据做运算。Window函数能够把多行的数据变成一行，因此在流程挖掘中非常有用。
