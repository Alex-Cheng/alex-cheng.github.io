# How ClickHouse's WITH-ALIAS is implemented



**WITH-ALIAS** contains two similar but different features:

- WITH <expression> as <alternate>
- WITH <alternative> as <subquery



## WITH <expression> as <alternate> feature

The following SQL shows the usage of the **WITH <expression> as <alternate>** feature.

```SQL
with c1 + 1 as c2 select c2 from t1.
```

When run, the alias `c2` in `select c2` is rewritten as the expression `c1+1`. Using the With... Alias feature can significantly reduce the size of the SQL.



### Syntax tree for WITH <expression> as <alternate>

Show the syntax tree with EXPLAIN.

```sql
explain ast with c1 as a1, f1() as a2 select a1, a2 from t1.
```

Get the result:

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

The key point of the above syntax tree is the use of `Identifier`, `Function` contains internally the alias alias attribute, which means "<expression> as <alternate name>" in the WITH clause. All inheritances from `ASTWithAlias` have the alias alias attribute. Here is the inheritance tree.

```ini
  ^ASTWithAlias$
  └── ASTWithAlias
      ├── ASTFunction
      ├── ASTLiteral
      ├─ ASTQueryParameter
      ├── ASTSubquery
      └─ ASTIdentifier
          └── ASTTableIdentifier
ðŸ™' ðŸ™'



`ASTWithAlias` can be specified as a syntax unit of an alias, including `ASTFunction`, `ASTLiteral`, `ASTQueryParameter`, `ASTSubquery`, `ASTIdentifier`. As an example, `sum(abc) as sum_value` is specifying an alias `sum_value` for `ASTFunction`, and `column1 as c1` is another example, specifying an alias for `ASTIdentifier`.



## WITH <alternate name> as <subquery> feature

`WITH... .SUBQUERY` is another similar feature used to define a subquery on WITH that can be referenced in SQL where the table is needed (e.g. after FROM). The following is an example:

```sql
with q1 as (select * from t1), q2 as (select * from t2) select * from q1.
```



`WITH <alternate> as <subquery>` is similar to `WITH <expression> as <alternate>` but the generated syntax tree is very different.



### Syntax tree for WITH <alternate> as <subquery>

Show the syntax tree with EXPLAIN.

```SQL
explain ast with q1 as (select * from t1), q2 as (select * from t2) select * from q1.
```

Get the result:

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

The key point of the above syntax tree is the use of `WithElement` to represent "<alternate name> as <subquery>" in the WITH clause.

If a query is a subquery, it is represented by `ASTSubquery`, otherwise it is represented by `ASTSelectQuery`. The WITH part is included in `ASTSelectQuery` and is obtained by the `with()` method.



##Visitors that handle the WITH clause



### ApplyWithSubqueryVisitor

Iterates through the syntax tree, replacing subqueries with aliases in WITH where the subquery alias is referenced.



### ApplyWithAliasVisitor

Iterates through the syntax tree, copying the aliased expressions (excluding subqueries) from the outer WITH to the inner query.



```sql
with c1 + 1 as a1, c2 * 2 as a2
select * from (select a1, a2 from t1).
```



### ApplyWithGlobalVisitor 

Pass the with clause of the first select of a union select to other select statements.

The following is an example of a union select with a with clause.

```sql
with 1 as a1
select a1
union all
select a1
union all
select a1
```

ApplyWithGlobalVisitor will copy the WITH content from the first select to the other select statements.



## Enable_global_with_statement switch

Set the `enable_global_with_statement` switch to control whether WITH... .ALIAS is not globally valid, `Propagate WITH statements to UNION queries and all subqueries`. If it is turned off, ApplyWithAliasVisitor and ApplyWithGlobalVisitor will not work and the following SQL will error out.

```sql
with 1 as a1
select a1
union all
select a1
union all
select a1
settings enable_global_with_statement =0.
```

`settings enable_global_with_statement =0` is removed and it works fine.



## Syntax tree for SELECT

Even if there is only one SELECT, it will be nested inside SelectWithUnionQuery, forming the following three-level structure.

      SelectWithUnionQuery (children 1)
       ExpressionList (children 1)
        SelectQuery (children 2)



Using a simplest example, the

```sql
explain ast select 1.
```

generates a syntax tree that

```
SelectWithUnionQuery (children 1)
 ExpressionList (children 1)
  SelectQuery (children 1)
   ExpressionList (children 1)
    Literal UInt64_1
```
