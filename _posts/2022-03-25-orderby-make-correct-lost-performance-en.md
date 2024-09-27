# Order By guarantees absolutely correct results, but performance is greatly affected

The results of some aggregate functions are related to the order in which the data flows in, and the CH documentation clearly states that the results of such functions are indeterminate. Why is this? Let's use `explain pipeline` to find out.

Take a very simple query as an example:

```sql
select any( step ) from events group by request_id;
```

The definition of the events table is as follows:

```sql
CREATE TABLE default.events
(
    `ID` UInt64,
    `request_id` String,
    `step_id` Int64,
    `step` String
)
ENGINE = MergeTree
ORDER BY ID
```

This query reads the data from the events table, selects the step `step` and the request ID `request_id`, groups by `request_id` and takes the first `step`.



Let's take a look at the pipeline for this query:

```sql
localhost :) explain pipeline select any( `step`) from events group by request_id

┌─explain────────────────────────────────┐
│ (Expression)                           │
│ ExpressionTransform                    │
│   (Aggregating)                        │
│   Resize 32 → 1                        │
│     AggregatingTransform × 32          │
│       StrictResize 32 → 32             │
│         (Expression)                   │
│         ExpressionTransform × 32       │
│           (SettingQuotaAndLimits)      │
│             (ReadFromMergeTree)        │
│             MergeTreeThread × 32 0 → 1 │
└────────────────────────────────────────┘
```

It can be seen that there is no sorting step. This query is quite fast on a multi-core server because it makes full use of the multi-core until the final step, when it is merged into a single data stream to be processed by a single thread.

**However, it should be noted** that the result of this query is different each time. You can test this by adding a filter condition to count. The following SQL is used for the test:

```sql
select countIf(A='step1') from (select any( `step`) as A from (select * from events) group by request_id)
```

The results are: 2500579, 2500635, 2500660. The results are not far apart, but none of them is absolutely correct. This is because when executed in multiple threads, there is no strict guarantee that the data will be processed in the storage order of the table with engine=MergeTree. If you can tolerate the error, there is no problem, because the efficiency of this query is very high.

However, if you want to pursue absolute correct results, you need to explicitly specify the order. Modify the query as follows:

```sql
select any( step ) from (select * from events order by ID) group by request_id;
```

The query pipeline becomes this:

```sql
localhost :) explain pipeline select any( step ) from (select * from events order by ID) group by request_id;

┌─explain─────────────────────────────────┐
│ (Expression)                            │
│ ExpressionTransform                     │
│   (Aggregating)                         │
│   AggregatingTransform                  │
│     (Expression)                        │
│     ExpressionTransform                 │
│       (Sorting)                         │
│       MergingSortedTransform 36 → 1     │
│         (Expression)                    │
│         ExpressionTransform × 36        │
│           (SettingQuotaAndLimits)       │
│             (ReadFromMergeTree)         │
│             MergeTreeInOrder × 36 0 → 1 │
└─────────────────────────────────────────┘
```

Notice that an important step has been added to the pipeline: `MergingSortedTransform 36 → 1 `. This step ensures the correctness of the query, but it has a significant impact on efficiency because it groups the data streams of multiple threads together, sorts them, and then continues to have one thread complete the remaining processing steps. The test results show that queries with the ORDER BY clause can get consistent and correct results, but the efficiency is at least 10 times worse. The greater the number of cores on the server, the greater the difference.
