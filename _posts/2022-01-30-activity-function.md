# activity_appearance函数性能调优

要实现activity_appearance函数，函数本身逻辑不复杂，就是计数属于同一个案例内的多个行的某个属性列中的值出现的次数，例如某一行的“王二”是其所属案例中的第二次出现，则对应返回值为2。

为了点数不同的属性值，用到multiset或者unordered_multiset，multiset数据结构是红黑树，unordered_multiset数据结构是hash。但是发现insert的速度相当慢。
换了比较快的hasher，CityHash64，还是很慢。那么我理解是内部的数据结构对于插入运算的消耗比较大。CH自己实现了Hasher，没有用STL的。

从ColumnString列中获取某一行的值也不是速度瓶颈，因为直接返回类似{offset[i],offset[i+1]-offset[i]}这样的值，不涉及大量的内存复制操作。

CH中有自己开发的 ClearableHashMapWithStackMemory的HashMap，看名字是在把数据放在栈内存中的hashmap，不知道效率是否比stl的hashmap要快。试一下。

测试结果令人惊讶，原来的运行时间是2s，现在的运行时间是0.2s。原因正在分析。
