# 对于同一个成员方法分别定义左值和右值的实现版本
有时候需要对同一个成员方法定义不同的实现，比如如果当前`this`右值时，可以用一些移动语义来优化性能。这时候需要通过添加函数的限定符来为this为右值时定义专门的方法实现。

在函数声明后面加上&，表示该方法只能被左值对象调用；在函数声明后面加上&&，表示该方法只能被右值对象调用。配合const限定符就有四种组合。下面的代码详细展示这四种组合。其中右值常数是没有什么意义的，但是语法上是允许的。

```C++
#include <iostream>

// 在函数声明后面加上&，表示该方法只能被左值对象调用。
// 在函数声明后面加上&&，表示该方法只能被右值对象调用。
struct Person
{
    void say() const &  // this为左值常数的say()方法版本。
    {
        std::cout << "const lvalue say()." << std::endl;
    }

    void say() const&&   // 常量右值没有什么意义，移动语义理论上是要修改原对象的内容的，否则就是复制了（真正的复制是不会影响原对象的）。
    {
        std::cout << "const rvalue say()." << std::endl;
    }

    void say() &  // this为左值的say()方法版本。
    {
        std::cout << "lvalue say()." << std::endl;
    }

    void say() &&  // this为右值的say()方法版本。
    {
        std::cout << "rvalue say()." << std::endl;
    }
};

int main()
{
    Person a;
    a.say();

    const Person& b = a;
    b.say();

    std::move(a).say();

    std::move(b).say();
}

```
