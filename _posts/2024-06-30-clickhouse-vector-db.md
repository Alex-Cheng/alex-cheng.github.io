# ClickHouse的向量处理能力



## 引言

在过去，非结构化数据（如文本、图片、音频、视频）通常被认为难以在数据库中直接使用，因为这些数据类型的多样性和复杂性。然而，随着技术的发展，嵌入技术可以将非结构化数据（如文本、图像、音频、视频）转换为向量，以便进行高效的向量相关的处理，例如相似度计算和搜索。这种向量相关的处理能力对于推荐系统、图像语义搜索和自然语言处理等应用非常重要，以下列举了部分应用场景：

- **推荐系统**：特别适用于电商网站，通过向量搜索找到相关产品，还可以编码页面浏览和过去的购买记录。
- **问答系统**：使用向量编码不同的同义词，提升问答系统的准确性。
- **图像和视频搜索**：利用多模态模型，根据文本搜索图像和视频，适用于音乐、电影推荐系统等。
- **欺诈检测**：通过编码用户行为或登录模式，检测异常行为以防止欺诈。
- **多语言搜索**：跨语言搜索，同一概念在不同语言中编码为相同向量。

数据库的向量处理能力是指数据库系统能够高效处理和操作高维向量数据的功能。它包括：

1. 向量数据的表示
2. 向量数据的计算
3. 向量数据的搜索
4. 向量数据的索引
5. 向量数据的存储

通过把非结构化数据转变成向量，带有向量处理能力的通用OLAP数据库就能够统一有效地处理和分析结构化数据和非结构化数据了。将结构化和非结构化数据结合在一个平台上，有以下好处：

1. 简化数据管理和数据库基础设施
2. 综合分析结构化数据和非结构化数据
3. 结合现有数据库系统的其他功能（如过滤、全文搜索和分析）



## 向量的产生

向量可以有非常大的维度，蕴含大量的信息，可以表示词、句子、文档、图片、视频、基因、动作等等。向量数据是通过各种技术和算法从非结构化数据中生成的，以下是一些常见的方法：

1. **文本数据**：
   - **词嵌入**：利用Word2Vec、GloVe等模型将单词或短语转换为向量。
   - **句子和文档嵌入**：使用BERT、GPT等预训练模型将句子或文档转换为向量表示。

2. **图像数据**：
   - **卷积神经网络（CNN）**：通过预训练的图像分类模型（如ResNet、Inception）提取图像的特征向量。

3. **音频数据**：
   - **MFCC（梅尔频率倒谱系数）**：提取音频信号的特征。
   - **预训练模型**：如VGGish模型，将音频片段转换为向量。

4. **视频数据**：
   - **帧级别嵌入**：对视频的每一帧进行图像特征提取，然后聚合这些特征。
   - **时序模型**：使用3D卷积网络或循环神经网络（RNN）处理视频序列，生成视频嵌入。

只要把非结构化数据转换为向量，就可以在数据库中进行高效的存储、检索和计算。

用户可以下载现成的模型并进一步训练或微调，也可以下载或生成自己的数据集进行实验。可以在本地运行模型生成向量，也可以调用公有云服务生成向量。一旦有了数据集，就要考虑存放模型数据的地方，就要考虑向量数据库或者具有向量能力的通用数据库。这里我们选择ClickHouse通用OLAP数据库并检验其向量相关的能力。



## ClickHouse的向量能力

按照上述几个维度，我们研究和实践ClickHouse的向量能力。

### 向量数据的表示

在ClickHouse中向量被表示为Array(Float32)。以流程分析场景为例，流程变体就是一种流程的执行流（例如 申请->退回->重新申请->批准->执行），我们创建一个表用于处理流程变体。在这张表中添加一列`variant_embedding`，用于存放流程变体的嵌入向量。建表SQL示例如下：

```SQL
create table t_process_variants(
    id Int64,
    activities Array(String),
    variant_embedding Array(Float32)
) engine = MergeTree()
order by id;
```

可以通过在本地运行CLIP语言模型，或者调用公有AI云服务生成流程变体的嵌入向量（embeddings）。这里我通过阿里云的[模型服务灵积](https://help.aliyun.com/zh/dashscope/) 生成流程变体的嵌入向量，每个向量有1536个维度。

### 向量数据的计算

向量数据的常用计算是相似度计算，以及向量的数学运算。

**向量之间的相似度计算**

对向量数据常用的操作之一是搜索相似内容，这需要计算向量之间的距离。距离较小的两个向量表示的内容在概念上是相似的。常用的距离度量包括：

1. **cosineDistance**：
   - 余弦距离 [Cosine similarity - Wikipedia](https://en.wikipedia.org/wiki/Cosine_similarity#Cosine_distance)
   - 衡量两个向量夹角的余弦值。
   - 计算公式：
     \[ \text{CosineSimilarity}(\mathbf{x}, \mathbf{y}) = \frac{\mathbf{x} \cdot \mathbf{y}}{||\mathbf{x}||_2 \cdot ||\mathbf{y}||_2} \]
   - 适用于衡量向量方向上的相似度，而不是绝对大小。
   
2. **L2Distance**：
   - 欧几里得距离 [Euclidean distance - Wikipedia](https://en.wikipedia.org/wiki/Euclidean_distance)
   - 衡量两个向量在空间中的直线距离。
   - 计算公式：
     \[ \text{EuclideanDistance}(\mathbf{x}, \mathbf{y}) = \sqrt{\sum_{i=1}^{n} (x_i - y_i)^2} \]
   - 常用于实际距离的计算。

以下是搜索相似的流程变体的SQL查询：

```sql
with [...] 
	as search_var
select activities,
    L2Distance(
        search_var,
        variant_embedding
    ) as dist
from t_process_variants
order by dist asc
limit 5
```

或者用余弦距离。

```
with [...] 
	as search_var
select activities,
    cosineDistance(
        search_var,
        variant_embedding
    ) as dist
from t_process_variants
order by dist asc
limit 5
```

除此之外，ClickHouse还提供了其他的距离计算。

1. L1Distance
   曼哈顿距离。
2. L2SquaredDistance
   欧几里得距离的平方（或者说省去了开平方）。
3. LpDistance
   p-范数距离。
4. LinfDistance
   L∞距离（也称为切比雪夫距离）是p-范数距离的一种特殊形式，其中p趋向于无穷大。

**向量的数学运算**

向量的加、减可以直接用运算符`+`、`-`来完成。

```
SELECT [1, 2] + [2, 3]

Query id: 0cd21c01-b110-4278-8899-bfbce608724a

   ┌─plus([1, 2], [2, 3])─┐
1. │ [3,5]                │
   └──────────────────────┘
```

```
SELECT [1, 2] - [2, 3]

Query id: 4ceb3180-f690-4b22-8416-479a3772bf11

   ┌─minus([1, 2], [2, 3])─┐
1. │ [-1,-1]               │
   └───────────────────────┘
```

向量的点乘使用函数`dotProduct`。

ClickHouse中，没有直接提供向量的叉乘（Cross Product）功能。

其他简单的向量计算例如`[1,2,3] / 2`，可以用`arrayMap`完成。

### 向量数据的搜索

向量搜索一般用向量距离函数加一个阈值来完成，并配合其他普通列上的条件，综合查询需要的结果。例如查询跟某个流程变体相似的且张三参与了的流程。

```sql
with [...] 
	as search_var
select activities,
    cosineDistance(
        search_var,
        variant_embedding
    ) as dist
from t_process_variants
where dist < 0.5
	and has(operators, '张三') -- operators列包含所有参与者的姓名
order by dist asc
limit 3
```



### 向量数据的索引

上述的向量搜索是线性的，因为要一个一个的算向量距离，其时间复杂度是O(n)。通过添加向量索引可以降低时间复杂度，代价是牺牲精确度，但是在很多场景中这点精确度的牺牲是可以容忍的。

#### 近似最近邻搜索索引（Annoy索引）

Annoy（Approximate Nearest Neighbors Oh Yeah）索引是一种数据结构，是为了提升大规模最近邻向量搜索的效率，虽然它在 ClickHouse 中仍处于实验阶段，但它能在准确性和计算效率之间取得平衡。Annoy索引用于在高维空间中进行近似最近邻搜索。它通过随机超平面将空间划分成多个小区域，每个区域包含一部分数据点。这些区域形成一棵二叉树，节点代表超平面，子节点代表子区域，叶节点则包含实际的数据点。通过随机化插入和使用启发式算法，确保树的平衡和效率。

Annoy索引当前支持两种距离：

1. 余弦距离 cosineDistance
2. 欧几里得距离 L2Distance

**Annoy 索引的工作原理:**

- **构建:** Annoy 索引通过多次使用随机超平面分割空间来构建树结构，可以在创建时指定树的数量（NumTree）和距离函数（DistanceName）。DistanceName 代表使用的距离函数，只能是L2Distance或者cosineDistance，默认是 L2Distance。NumTree 代表算法创建的树的数量。树的数量越多，索引的构建和查询速度就会越慢，但准确性也会越高。默认情况下，NumTree 设置为 100。
- **搜索:** 查询时，通过比较向量和超平面，估算距离，决定进一步探索哪个子节点，最终得到一个近似的最近邻集合，搜索速度比线性扫描快得多，时间复杂度是O(logN)。



可以用在创建表或者修改表的时候创建一个Annoy索引，在INDEX字句中指定索引类型为Annoy。

```sql
INDEX {ann_index_name} {向量列} TYPE annoy([{距离函数}[, {树的数量}]])
```

例如：

```sql
alter table t_process_variants
add index variant_embedding_idx variant_embedding type annoy('cosineDistance', 100)
```



**使用注意事项:** 

1. Annoy 索引适用于使用 `ORDER BY DistanceFunction(Column, vector)` 或 `WHERE DistanceFunction(Column, Point) < MaxDistance` 的查询，必须使用 `LIMIT` 子句来控制返回结果的数量。
2. 必须打开设置开关allow_experimental_annoy_index才能启动Annoy索引的作用，默认是关闭的。



### 向量数据的存储

向量用Array(Float32)存储有些奢侈，因为很多情况下16位浮点数就够了，在行业内专门有这样的类型叫bfloat16，很多数据集和训练出来的模型都是采用bloat16。

但是ClickHouse当前并没有Float16这样的类型。所以还是得用Array(Float32)，但是bfloat16相当于Float32的低16位置为0后的结果。因此我们可以在存储向量之前用函数清除其Float32内容的低16位。这样存储时低16位的0会被压缩算法压缩。



## 总结

ClickHouse具备强大的向量处理能力，能够高效处理和操作高维向量数据。通过将非结构化数据（如文本、图片、音频、视频）转换为向量，ClickHouse可以实现推荐系统、问答系统、图像和视频搜索等多种应用。向量数据在ClickHouse中被表示为`Array(Float32)`，并支持多种相似度计算方法，如余弦距离和欧几里得距离。ClickHouse支持近似最近邻搜索索引（Annoy索引），通过随机超平面分割空间来提高搜索效率，适用于大规模向量搜索。此外，为了节省存储空间，可以采用bfloat16格式，从而实现高效的压缩和存储。

总的来说，ClickHouse的向量数据库功能通过高效处理和搜索高维向量数据，在多个应用领域展现出显著价值，使其成为推荐系统、问答系统、图像和视频搜索等领域的理想选择。

