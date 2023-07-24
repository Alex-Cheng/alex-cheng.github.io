# ClickHouse的WITH-ALIAS是如何实现的



**WITH-ALIAS**包含相似但不同的两个特性：

- WITH <表达式> as <别名>
- WITH <别名> as <子查询>



## WITH <表达式> as <别名> 特性

以下SQL展示了 **WITH <表达式> as <别名>** 特性的用法。

```SQL
with c1 + 1 as c2 select c2 from t1;
```

运行的时候，`select c2` 中的别名`c2`会被改写为表达式`c1+1`。 使用With...Alias特性能够大大缩小SQL的大小。



### WITH <表达式> as <别名> 的语法树

用EXPLAIN展现语法树。

```sql
explain ast with c1 as a1, f1() as a2 select a1, a2 from t1;
```

得到结果：

```ini
SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 3)
   ExpressionList (children 2)
    Identifier c1 (alias a1)
    Function f1 (alias a2) (children 1)
     ExpressionList
   ExpressionList (children 2)
    Identifier a1
    Identifier a2
   TablesInSelectQuery (children 1)
    TablesInSelectQueryElement (children 1)
     TableExpression (children 1)
      TableIdentifier t1
```

以上语法树关键之处是用`Identifier`，`Function` 内部包含alias别名属性，表示WITH子句中的"<表达式> as <别名>"。

所有继承于`ASTWithAlias`都带有alias别名属性。以下是继承树。

```ini
  ^ASTWithAlias$
  └── ASTWithAlias
      ├── ASTFunction
      ├── ASTLiteral
      ├── ASTQueryParameter
      ├── ASTSubquery
      └── ASTIdentifier
          └── ASTTableIdentifier
```

`ASTWithAlias` 可以被指定为一个alias别名的语法单元，包括 `ASTFunction`, `ASTLiteral`, `ASTQueryParameter`, `ASTSubquery`, `ASTIdentifier`。举个例子，`sum(abc) as sum_value` 就是为`ASTFunction` 指明一个别名`sum_value`，`column1 as c1`也是另一个例子，为`ASTIdentifier`指定一个别名。



### Enable_global_with_statement 开关

enable_global_with_statement开关会影响到表达式别名的处理。这个开关控制WITH...ALIAS是不是全局有效，“Propagate WITH statements to UNION queries and all subqueries”。如果关闭，ApplyWithAliasVisitor 和 ApplyWithGlobalVisitor 将不会工作，下面的SQL就会出错。

```sql
with 1 as a1
select a1
union all
select a1
union all
select a1
settings enable_global_with_statement =0;
```

`settings enable_global_with_statement =0`去掉就可以正常工作。



### 表达式别名的处理

表达式别名由ApplyWithAliasVisitor、ApplyWithGlobalVisitor、QueryAliasesVisitor、ExecuteScalarSubqueriesVisitor、QueryNormalizer访问者类来处理。

当打开enable_global_with_statement开关时，ApplyWithAliasVisitor和ApplyWithGlobalVisitor这两个访问者类会将表达式别名复制到subquery子查询和UNION语句中的其他SELECT查询（且称之为“兄弟查询”吧）中。

QueryAliasesVisitor访问者类会遍历整个AST树，搜集所有的表达式别名，构建出一个别名映射表，从`String -> IAST`。QueryNormalizer会根据收集的表达式别名把出现别名的地方替换成实际的AST（通过IAST的clone的新对象）。



#### ApplyWithAliasVisitor

遍历语法树，将外层的WITH的带别名的表达式（不包括子查询）复制到内层查询中。

```sql
with c1 + 1 as a1, c2 * 2 as a2
select * from (select a1, a2 from t1);
```



#### ApplyWithGlobalVisitor 

将union select的第一个select的with子句传递给其他select语句。

以下是一个带with子句的union select的示例。

```sql
with 1 as a1
select a1
union all
select a1
union all
select a1
```

ApplyWithGlobalVisitor 会把第一个select上的WITH内容复制到其他select语句上。



#### QueryAliasesVisitor

收集AST树中的表达式别名，并且做以下两件事情：

1. 对于没有alias别名的subquery子查询，此Visitor会为其加上唯一的alias别名；
2. 保证其上的prefer_alias_to_column_name属性置为true。

为subquery子查询加上别名是因为subquery会被随后的优化器修改，导致以subquery内容生成subquery字段名的算法无法使用，因为当subquery的内容被优化器改变后，此算法生成的字段名就会更以前的不一样，这样会破坏一个不变式：*同一个subquery在不同的时候对应的字段名必须一样*。

Subquery子查询在随后的处理中可能会变成字面值。例如把子查询`(SELECT sum(number) FROM numbers(10))` 变为 `(SELECT sum(number) FROM numbers(10)) as _subquery_1`。这个子查询会被`ExecuteScalarSubqueriesVisitor`转换成最终的字面值，即`(45 as _subquery_1)`。

需要显式地将`prefer_alias_to_column_name` 设置为true的原因是关于分布式表引擎**Distributed engine**的一个缺陷。对于分布式表引擎Distributed engine，查询被发到远程服务器时会丢失`prefer_alias_to_column_name`属性，因此对于带`_subquery_`前缀的别名的子查询或者是字面值，`QueryAliasesVisitor`会将其`prefer_alias_to_column_name`属性重新置为true。

对于`ARRAY JOIN`和`LEFT ARRAY JOIN`有特殊处理逻辑，跳过其AST树上的一级和二级子节点，专处理第三级子节点，这里不是很优雅，可能会隐藏着bug。



#### ExecuteScalarSubqueriesVisitor

将可以求值为一个单值的子查询替换成求出的单值，作为字面值替代原有的子查询。例如子查询`(SELECT sum(number) FROM numbers(10)) as _subquery_1`会变成`(45 as _subquery_1)`。其上的`prefer_alias_to_column_name`属性会被置为true。



#### QueryNormalizer

根据别名映射表，替换别名为实体AST。有一些设置开关控制其行为细节：

1. max_expanded_ast_elements  

   展开后的AST节点的数量上限。

2. max_ast_depth
   AST树的深度限制。

3. prefer_column_name_to_alias
   尽量用列名替代别名。

4. allow_self_aliases
   允许`a1 + 1 as a1`这样的表达式别名，现在的代码中allow_self_aliases都为true。





## WITH <别名> as <子查询> 特性

`WITH...SUBQUERY`是另外一个相似的特性，用于定义WITH上的子查询，在SQL的需要表的地方（例如FROM后面）可以引用。下面是一个例子：

```sql
with q1 as (select * from t1), q2 as (select * from t2) select * from q1;
```



`WITH <别名> as <子查询>` 与 `WITH <表达式> as <别名>`虽然很类似但是生成的语法树差别很大。



### WITH <别名> as <子查询> 的语法树

用EXPLAIN展现语法树。

```SQL
explain ast with q1 as (select * from t1), q2 as (select * from t2) select * from q1;
```

得到结果：

```ini
SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 3)
   ExpressionList (children 2)
    WithElement (children 1)
     Subquery (children 1)
      SelectWithUnionQuery (children 1)
       ExpressionList (children 1)
        SelectQuery (children 2)
         ExpressionList (children 1)
          Asterisk
         TablesInSelectQuery (children 1)
          TablesInSelectQueryElement (children 1)
           TableExpression (children 1)
            TableIdentifier t1
    WithElement (children 1)
     Subquery (children 1)
      SelectWithUnionQuery (children 1)
       ExpressionList (children 1)
        SelectQuery (children 2)
         ExpressionList (children 1)
          Asterisk
         TablesInSelectQuery (children 1)
          TablesInSelectQueryElement (children 1)
           TableExpression (children 1)
            TableIdentifier t2
   ExpressionList (children 1)
    Asterisk
   TablesInSelectQuery (children 1)
    TablesInSelectQueryElement (children 1)
     TableExpression (children 1)
      TableIdentifier q1
```

以上语法树关键之处是用`WithElement` 表示WITH子句中的"<别名> as <子查询>"。

如果一个查询为子查询，它是用`ASTSubquery`来表示，否则就是用`ASTSelectQuery`来表示。在`ASTSelectQuery`中包含WITH部分，通过`with()`方法获得。



### 子查询别名的处理

子查询别名的处理相对比较简单。访问者类ApplyWithSubqueryVisitor遍历AST树，替换别名为真实子查询AST实例。



#### ApplyWithSubqueryVisitor

遍历语法树，将WITH中的带别名的子查询替换引用子查询别名的地方。



## 其他细节



### SELECT的语法树结构

即使只有一个select，也会被套进 SelectWithUnionQuery里面，形成以下三层结构。

      SelectWithUnionQuery (children 1)
       ExpressionList (children 1)
        SelectQuery (children 2)



用一个最简单的为例，

```sql
explain ast select 1;
```

生成的语法树，

```
SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 1)
   ExpressionList (children 1)
    Literal UInt64_1
```



### prefer_alias_to_column_name的作用

`prefer_alias_to_column_name`用于指示用别名作为内部的列的名字，这个可以避免为了得到内部列名而需要的大量的递归调用`IAST::appendColumnName`方法。



### ASTArrayJoin

`ARRAY JOIN`和`LEFT ARRAY JOIN`是一种特殊的语法，在代码中经常被特殊处理。以下是它的AST树的示例：

```sql
CREATE TABLE arrays_test
(
    s String,
    arr Array(UInt8)
) ENGINE = Memory;

INSERT INTO arrays_test
VALUES ('Hello', [1,2]), ('World', [3,4,5]), ('Goodbye', []);

SELECT s, arr
FROM arrays_test
ARRAY JOIN arr;
```

以上SQL中的SELECT查询的AST为：

```ini
SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 2)
   ExpressionList (children 2)
    Identifier s
    Identifier arr
   TablesInSelectQuery (children 2)
    TablesInSelectQueryElement (children 1)
     TableExpression (children 1)
      TableIdentifier arrays_test
    TablesInSelectQueryElement (children 1)
     ArrayJoin (children 1)
      ExpressionList (children 1)
       Identifier arr
```

