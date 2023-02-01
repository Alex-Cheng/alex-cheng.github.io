# MergeTree表的三种格式
MergeTree表引擎有三种格式：Compact、Wide和In-memory，前两个为主要格式。具体区别是：
- Compact - 所有的列的数据放在一个文件；
- Wide - 每个列的数据放在一个文件；
- In-memory - 数据存在内存中，不在磁盘上。当数据量（行数和总共所占字节数）都很小的情况下采用。

`min_bytes_for_compact_part` 和 `min_rows_for_compact_part` 控制MergeTree表是否采用in-memory模式还是compact格式。
`min_bytes_for_wide_part` 和 `min_rows_for_wide_part` 控制MergeTree表是否采用wide格式还是compact格式。

两对设置项的关系是：
```
0 <= min_bytes_for_compact_part <=  min_bytes_for_wide_part
0 <= min_rows_for_compact_part<= min_rows_for_wide_part
```

这里用代码解释一下格式选择逻辑：

![image](https://user-images.githubusercontent.com/1518453/215983151-34185a33-3ae1-4916-b1d6-705d3296cd48.png)


设置 `min_bytes_for_compact_part` , `min_rows_for_compact_part` , `min_bytes_for_wide_part` , `min_rows_for_wide_part` 均为0，就可以强制所有的MergeTree表都采用wide格式。
