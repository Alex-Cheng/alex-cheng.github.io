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

```yaml
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

以上语法树关键之处是用`Identifier`，`Function` 内部包含alias别名属性，表示WITH子句中的"<表达式> as <别名>"。所有继承于`ASTWithAlias`都带有alias别名属性。以下是继承树。

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

```yaml
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



## 处理WITH子句的Visitor们



### ApplyWithSubqueryVisitor

遍历语法树，将WITH中的带别名的子查询替换引用子查询别名的地方。



### ApplyWithAliasVisitor

遍历语法树，将外层的WITH的带别名的表达式（不包括子查询）复制到内层查询中。



```sql
with c1 + 1 as a1, c2 * 2 as a2
select * from (select a1, a2 from t1);
```



### ApplyWithGlobalVisitor 

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



## Enable_global_with_statement 开关

设置`enable_global_with_statement`开关控制WITH...ALIAS是不是全局有效，“Propagate WITH statements to UNION queries and all subqueries”。如果关闭，ApplyWithAliasVisitor 和 ApplyWithGlobalVisitor 将不会工作，下面的SQL就会出错。

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



## SELECT的语法树

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

