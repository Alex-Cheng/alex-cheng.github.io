# RAII：让资源管理自动、确定、零泄漏

上一篇文章讲了零成本抽象这条设计哲学。为了兑现它，C++ 放弃了垃圾回收——那么在没有 GC 的前提下，内存之外还有文件句柄、锁、线程、网络连接这些资源，如何保证它们不泄漏？C++ 给出的答案是 RAII（Resource Acquisition Is Initialization）：把资源的生命周期绑定到栈对象的生命周期上，获取即构造，释放即析构。这是 C++ 实现资源安全的核心机制，也是现代 C++ 各项特性的地基。

## 栈对象承担所有权

RAII 的原理一句话就能说完：让一个栈对象**拥有**资源。构造函数里获取资源，析构函数里释放资源，作用域决定一切——进入左花括号时构造，离开右花括号时析构，没有任何例外路径。

这里的关键词是所有权（ownership）。它描述的不是"谁能用资源"，而是"谁对资源的生命周期负责"：

> Ownership 除了权利，还意味着责任：程序执行一旦离开栈对象的作用域，对象就被自动且确定地析构。

所有权分两种。独占所有权，可转让不可复制；共享所有权，可复制但通常需要引用计数来决定最后一个负责释放的人。实践中独占所有权是常态，共享是例外。

## 标准库里的 RAII

标准库大量采用这个模式，把易错的资源管理封装成安全的作用域对象：

| 资源 | RAII 工具 |
| ---- | ---- |
| 锁 | `std::lock_guard`、`std::unique_lock` |
| 内存 | `std::unique_ptr`、`std::shared_ptr` |
| 文件 | `std::ifstream` / `std::ofstream` |
| 线程 | `std::jthread`（C++20，析构时自动 join） |

## 异常安全的试金石

异常路径是资源泄漏最常见、也最隐蔽的来源：每一处提前 `return`、每一个抛出的异常，都可能跳过释放代码。有 GC 的语言用 `try / finally` 解决这个问题，比如 C#：

```csharp
FileStream fs = null;
try
{
    fs = new FileStream("test.txt", FileMode.Open);
    // 使用 fs
    // ...
}
finally
{
    if (fs != null)
    {
        fs.Close();   // 一定会执行
    }
}
```

（顺带一提，现代 C# 通常直接写 `using`，由编译器生成上面的 `try / finally`。）

C++ 不需要这个语法，因为析构本身就是 `finally`：

```cpp
std::ifstream ifs("test.txt");
if (ifs) {
    // 使用 ifs
    // ...
}
```

RAII 的保证是：**异常不会跳过析构**。栈展开时，已构造完成的对象会逐一析构。于是异常路径与正常路径遵循同一套释放规则，异常不再是资源安全的"特殊情况"——无需 `try / finally`，也无需 GC。

## 工程实践：从定制 deleter 到定制 RAII 类

日常写法有清晰的优先级：

1. 尽量不用裸 `new`，用 `std::make_unique`；
2. 无状态 deleter 的 `std::unique_ptr`，大小和运行时开销与裸指针 `T*` 基本持平；
3. 需要共享所有权的特殊情况用 `std::make_shared`；
4. 内存之外的资源，用定制了 deleter 的 `std::unique_ptr`；
5. 确有必要时，再自己实现 RAII 类。

举个真实例子。AutoCAD 的 ObjectARX 里，`resbuf` 是表示变长异构链表的结构，由 `acutBuildList` 在堆上分配，必须用 `acutRelRb` 显式释放。手工管理的代码里，每个提前退出和每个 `catch` 分支都得写一遍释放，漏一处就泄漏。而定制一个 deleter，一行搞定：

```cpp
auto deleter = [](resbuf* p) {
    if (p) acutRelRb(p);
};

// 不管如何离开作用域，resbuf 都会被释放
std::unique_ptr<resbuf, decltype(deleter)> rb(
    acutBuildList(
        RTSHORT, 1,
        RTSTR, _T("Hello"),
        RTNONE
    ),
    deleter
);
```

如果资源逻辑更复杂，就写一个定制 RAII 类：独占所有权，可移动不可拷贝——拷贝意味着两个对象对同一份资源负责，这正是要杜绝的。

```cpp
class RbHolder {
public:
    explicit RbHolder(resbuf* p) : rb(p) {}
    ~RbHolder() {
        if (rb) acutRelRb(rb);
    }

    resbuf* get() const { return rb; }

    RbHolder(const RbHolder&) = delete;
    RbHolder& operator=(const RbHolder&) = delete;

    RbHolder(RbHolder&& other) noexcept : rb(other.rb) {
        other.rb = nullptr;
    }

    RbHolder& operator=(RbHolder&& other) noexcept {
        if (this != &other) {
            if (rb) acutRelRb(rb);   // 先释放自己已持有的资源
            rb = other.rb;
            other.rb = nullptr;
        }
        return *this;
    }

private:
    resbuf* rb;
};
```

两个细节值得注意：移动赋值前要先释放自己已持有的资源，否则赋值一次泄漏一次；移动构造和移动赋值都应标记 `noexcept`，这样容器扩容时才会选择移动而非拷贝。

> 资源安全不再依赖人的小心翼翼，而是交由类型系统和编译器来保障。

## 边界在哪里

RAII 不是万能的，它有几处实实在在的局限：

- **析构顺序依赖**。栈对象的析构顺序与构造相反，由作用域结构决定。当两个对象的释放有跨对象的逻辑依赖（比如某对象析构时要回调另一个已析构对象），RAII 的自动顺序未必符合业务语义，需要人为安排成员声明顺序或持有关系。
- **构造函数中途抛异常**。对象没构造完成就不会调用自身析构函数——好在已构造完成的成员和基类子对象仍会正确析构，所以"构造函数里获取资源"本身是安全的；但构造函数抛异常意味着调用方要处理失败路径，资源获取可能失败的类型不适合放进 `noexcept` 上下文。
- **`shared_ptr` 循环引用**。两个对象互相持有 `shared_ptr`，引用计数永远不归零，双双泄漏。解法是其中一方改用 `std::weak_ptr`，但这需要人主动识别环。
- **析构不能失败**。析构函数默认不应抛异常（栈展开期间抛异常会直接 `std::terminate`），需要在释放时报告错误的资源（比如 `fclose` 的缓冲区刷写失败），RAII 类得另设计接口。

另外 RAII 只保证"有人负责释放"，不保证释放的**时机**符合性能预期：`shared_ptr` 的控制块有额外开销，`make_shared` 的单块分配会让对象内存延迟到所有 `weak_ptr` 消失才释放。这些都是使用时要权衡的工程细节，不是机制缺陷。

## 一句话总结

RAII 不只是技巧，而是 C++ 在没有 GC 的前提下实现资源不泄漏的核心保障：确定性的释放、天然的异常安全、与移动语义和智能指针的无缝配合。它把正确性写进类型里，让编译器替人守住资源安全。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第三集
