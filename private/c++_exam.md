# C++以及算法面试题

## C++基础
1.	关键字static的用法

包括类的静态成员变量、静态成员函数、全局静态变量、局部静态变量。

2.	类A某成员函数签名如下，三个const分别代表的含义是什么。

const char* const getName() const;
一个常量函数（第3个）返回一个指向常量字符（第1个）的常量指针（第2个）。
作为返回值，第2个const是多余的，就好比函数返回const int，const也是多余的，可以问下，看能否意识到。

3.	将某对象的地址转换为uint64_t类型的整数，应该用哪种cast。 reinterpret_cast 可以顺便问问其他的cast。

4.	（C++11）以下代码中的delete代表什么含义？

```
class Test
{
public:
Test() = delete;
};
```

禁用默认构造。

5.	构造函数中可否调用本类的虚函数？

可以调用，但行为特殊。虚函数的作用在于多态，而对象尚处于构造过程中，还没有多态行为（构造基类子对象时，this的类型为基类指针本身）。

6.	异常发生时，如何保证函数局部对象的析构函数能被执行到？

不需要额外操作，语言保证（或者说编译器保证）。

7.	什么叫模板特化？

8.	std::map一般用什么数据结构来实现？查找元素的时间复杂度是怎样的？

说出红黑树或平衡二叉树都可以，O(logN)

9.	编码时如需用到线性表，如何在std::vector和std::list之间做选择？

10.	（C++11）定义lambda的语法

[](){}：捕获列表、参数、函数体。还可以指明返回值，说出更好。

11.	哪些情况下会发生link error

12.	使用new创建新对象，如果创建失败会怎样？

抛出std::bad_alloc或者对象构造函数中抛出的异常。

13.	（C++11）override关键字的用法、用处。

14.	什么是纯虚函数（如何定义）及主要用途。

virtual = 0，定义接口、形成虚基类。基类声明，子类实现
实际基类也可以有实现，但子类仍然需要实现，不然仍是虚基类，不可以实例化。

15.	explicit关键字有什么用？

用于单参数构造函数，禁止隐式转换。

16.     emplace_back 与 push_back 的区别

emplace_back在C++ 11中引入，效率比push_back高，因为emplace_back直接在容器末尾创建对象，而push_back会先创建对象，然后通过拷贝构造函数或者移动构造函数添加到容器尾部。

17.     vector容器的reserve方法的意义，什么时候会用到
reserve方法与capacity的关系，通过reserve可以减少容器扩容时的需要重新内存搬家的次数。

18.     C++ 匿名namespace的作用以及它与static的区别
都可以防止全局变量或者函数跨TU（translation unit）命名冲突，但是static是把linkage修改为internal linkage，以避免TU之间命名冲突，而匿名namespace是通过名字改编（name mangling）生成一个独一无二的名字（所以“匿名”不是真的没有名字），因此自然能够避免TU之间的命名冲突。

### todo
菱形继承 
模板
extern
static

# 字符串


## 散列表

### 计算同一个组内的数据的序列号

假设有一个列表[(G1, X1), (G2, X2),(G3, X3),… ], G是连续的， 实现一个函数，返回[n1, n2, …],  n 是 X在该组G中的出现次序号。
例如：
输入：{ {"Group1", "A"}, {"Group1", "AB"}, {"Group1", "AB"}, {"Group1", "A"}, {"Group1", "C"}, {"Group1", "A"},
        {"Group2", "AB"}, {"Group2", "AC"}, {"Group2", "AB"}, {"Group2", "A"}, {"Group2", "AC"},
        {"Group3", "B"}, {"Group3", "B"}, {"Group3", "B"}, {"Group3", "A"}, {"Group3", "C"},
    }
输出：{1, 1, 2, 2, 1, 3,
      1, 1, 2, 1, 2, 
      1, 2, 3, 1, 1 }

问题一：
用C++编写程序，解决上述问题。
```C++

/*

假设有一个列表[(G1, X1), (G2, X2),(G3, X3),… ], G是连续的， 实现一个函数，返回[n1, n2, …],  n 是 X在该组G中的出现次序号。
例如：
输入：{ {"Group1", "A"}, {"Group1", "AB"}, {"Group1", "AB"}, {"Group1", "A"}, {"Group1", "C"}, {"Group1", "A"},
        {"Group2", "AB"}, {"Group2", "AC"}, {"Group2", "AB"}, {"Group2", "A"}, {"Group2", "AC"},
        {"Group3", "B"}, {"Group3", "B"}, {"Group3", "B"}, {"Group3", "A"}, {"Group3", "C"},
    }
输出：{1, 1, 2, 2, 1, 3,
      1, 1, 2, 1, 2, 
      1, 2, 3, 1, 1 }

*/

#include <iostream>
#include <vector>
#include <string>

using Data = std::vector<std::pair<std::string, std::string>>;

using Order = std::vector<size_t>;

Order calcOrder(const Data & data)
{
    Order o;
        
    return o;
}

void printOrder(const Order & order)
{
    for (auto & item : order) {
        std::cout << item << ", ";
    }
}

int main(int argc, const char * argv[]) {
    Data d { {"Group1", "A"}, {"Group1", "AB"}, {"Group1", "AB"}, {"Group1", "A"}, {"Group1", "C"}, {"Group1", "A"},
        {"Group2", "AB"}, {"Group2", "AC"}, {"Group2", "AB"}, {"Group2", "A"}, {"Group2", "AC"},
        {"Group3", "B"}, {"Group3", "B"}, {"Group3", "B"}, {"Group3", "A"}, {"Group3", "C"},
    };

    // 期望输出结果：
    // 1, 1, 2, 2, 1, 3,
    // 1, 1, 2, 1, 2,
    // 1, 2, 3, 1, 1,
    printOrder(calcOrder(d));
    
    return 0;
}

```


问题二：
当我们要实时处理大量的数据（例如十亿条数据），数据的特点是每个group包含的数据项的数量都在50以内，且同属一个group的数据聚在一起（可以理解成数据按照group排过序）。考虑如何改进算法及数据结构，以更高效地处理。

### 其他
1. 声明一个学生类，包含姓名、性别、年龄三个成员变量，并为其实现一个hash函数。

## 线性表

1.	反转单链表。如果是交谈的形式，也可以只问时间复杂度及基本思路。
2.	合并两个有序的单链表。

## 树与图

1.	为一个二叉树类实现拷贝构造函数。 也可以同时实现移动构造函数，考察C++知识点。
2.	按层次遍历二叉树。

## 递归


## 动态规划

### 装车问题（钢条问题）
假设有n种货物，重量分别是 [1，2，3，4，5，6，7]吨，其货物的价值是分别是 [1, 5, 7, 9, 10, 17, 18]，设计一个算法：给定一辆载重为m吨的卡车，求出最大货值的装货方案。

```
#include <iostream>
#include <vector>

using Data = std::vector<size_t>;
using Plan = std::vector<size_t>;

Plan calcLoadPlan(const Data & data, size_t m)
{
    Plan o;
    return o;
}

void printLoadPlan(const Plan & plan)
{
    for (auto & item : plan) {
        std::cout << item << ", ";
    }
}

int loadCargoTest() {
    // 假设有n种货物，重量分别是 {1，2，3，4，5，6，7} 吨，其货物的价值是分别是 {1, 5, 7, 9, 10, 17, 18}，设计一个算法：给定一辆载重为m吨的卡车，求出最大货值的装货方案。
    Data cargo { 1, 5, 7, 9, 10, 17, 18 };

    // 例如：
    // 当m=9时，{ 3, 6 } 为最优方案，货值为 7+17=24。
    size_t m = 9;
    printLoadPlan(calcLoadPlan(cargo, m));
    
    return 0;
}

```

## 贪心算法
### 凑钱问题
假设有一种货币，分别有A_1, A_2, ..., A_n几种面值的钞票，其中A_1 = 1。给定一个金额S，求最少的钞票凑成给定的金额S的方案。



## 分治

## 其他
1.	声明一个整数类，以便于求100的阶乘。 完整程序比较费时，可以定义出类的主要数据成员，以及所需要实现的接口函数，有时间可以实现一两个。
2.	打印1到N之间所有正序、反序都是质数的整数，成对打印，比如13和31。
3.	验证某字符串是否为合法的IPv4地址。
4.	牛顿迭代法求数的二次方根。
5.	声明一个矩阵类并实现其旋转操作。