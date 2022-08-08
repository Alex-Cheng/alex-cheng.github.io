# 原子变量与内存访问顺序模型


本文主要介绍原子变量和内存访问顺序模型，解答一下几个问题：这里涉及到以下知识体系：

- 多核CPU与存储体系
  
- 原子变量
  
- 内存模型
  - 最终一致性
  - 顺序一致性
  - release-acquire

- 自旋锁
  - 用原子变量实现
  - 退避策略

下面一一阐述。



## 多核CPU与存储体系

由于CPU的频率受限于物理定律而无法再有效提升，发展了多核CPU，即一个CPU芯片中包含多个“小CPU“，我们成为CPU核心。如果能够充分利用每个CPU核心的运算能力，那么整体的计算机处理性能就能大大提升。而程序中内存访问的频率非常高，基本上只要做计算，都免不了从内存中加载数据，然后还要把运算的结果写回到内存。而目前的x86/x64的多核系统是SMP结构，共享内存，同时只能有一个CPU核心访问内存（*CPU核心要访问内存，首先要获得内存总线的控制权，任何时刻只有一个CPU核心能获得内存总线的控制权*），所以访问内存变成了瓶颈。

为了解决这个瓶颈，我们让每个CPU核心都有自己的一级缓存（L1 cache），但是这又带来另外一个问题：多核中如何协调和同步缓存里的数据，这就引入了MESI协议。为了在实施MESI协议时尽量少“拖累”CPU，于是引入了存储缓冲区（store buffer）和无效队列（invalidate queue）。

下面一一解释。

### 总体结构

```asciiarmor
|-------------------------------------|
|   核1   |   核2   |   核3   |   核4  |  1. 离核越近访问速度越快；
|  寄存器  |  寄存器  |  寄存器 |  寄存器 |  2. 寄存器和一级缓存是每核独享；
| 一级缓存 | 一级缓存 | 一级缓存 |一级缓存  |  
| 二级缓存 | 二级缓存 | 二级缓存 |二级缓存  |  
|-------------------------------------|
|               三级缓存（L3）          |  3. 下级缓存（比如L3缓存）和内存是多核共享；
|               内存                  |
|-------------------------------------|
|              外存                    |  4. 外存最慢，特别是在时延方面跟内存和缓存比起来非常大，吞吐量的差别相比之下会小些。
|-------------------------------------|
```



### 缓存结构

```asciiarmor
|------------------------------------------------|
|                       缓存                      |
|------------------------------------------------|
|         缓存行(cache line) 一般64或128字节       | 
|  包含：对应的内存块地址（tag...）+ 数据 + MESI 状态   |
|------------------------------------------------|
|                更多的缓存行                     |
|                 ...  ...                       |
|------------------------------------------------|
```



### MESI协议

每个缓存行都有一个状态：

- M - 已修改，与内存的数据不一致，其他CPU核心的缓存**并没有**缓存该内存块；
- E  - 独占，与内存数据一致，其他CPU核心的缓存**并没有**缓存该内存块；
- S - 共享，与内存数据一致，其他CPU核心的缓存**也已经**缓存了该内存块；
- I   - 无效，该缓存行无效，表明其他CPU核心已经修改了对应内存块的内容（导致该缓存行的内容是**过期的**）。



### 存储缓冲区与失效队列

每个缓存行都对应内存的一小块，按照MESI协议，当一个CPU核心修改缓存行的内容时，需要通知同样缓存了这个内存块的其他CPU核心的缓存，反之亦然。但是为了效率不能让CPU等待通知这个动作完成，或者在被通知的时候不应该中断当前的任务而去实时地处理。因此引入了存储缓冲区（store buffer）与失效队列（invalidate queue）。

```asciiarmor
|----------------|                               | |----------------|
|    CPU核心      |   ->  store buffer      ->    | |    CPU核心      |
|                |         <MESI协议              | |                | 
|    缓存         |   <-  invalidate queue  <-    | |    缓存         |
|----------------|                               | |----------------|

```

存储缓冲区与失效队列的目的就是不影响CPU的执行，把同步更新改为异步更新。但这样又带来了缓存数据不一致的问题。

***数据不一致的问题***

> *假设CPU核1的加载了内存块addr1的数据；同时CPU核2也加载了内存块addr1的数据，当CPU核1修改了addr1的数据时，即使数据的修改及时地写回到了内存，CPU核2的缓存也可能没有更新，导致CPU核1的对addr1数据的修改对CPU核2来说“**不可见**”。*
>
> 过去会用volatile去标注多线程共享的变量，但是这种方法在现在已经不适用了。



## 原子变量

原子变量是可以跨线程共享的变量，也成为“线程安全”的变量，它不会因为多线程访问而产生竞态条件（race-condition）的问题或者是因为CPU 缓存的原因而引起的数据没有及时更新的问题。用原子变量就能解决上述的问题。

```c++
#include <iostream>
#include <thread>
#include <atomic>

std::atomic<int> a = 0;

void worker()
{
    for (int i = 0; i < 1000000; ++i)
    {
        a.fetch_add(1);
    }
}

void multiThreadAdd()
{
    auto t1 = std::thread(worker);
    auto t2 = std::thread(worker);
    auto t3 = std::thread(worker);

    t1.join();
    t2.join();
    t3.join();
    // 应该输出3000000，用原子变量得到了预期的结果。
    std::cout << "sum is: " << a << std::endl;
}

int main()
{
    multiThreadAdd();
}

```

原子变量就是强制让上面提到的存储缓冲区与失效队列得到适当的处理，以保证一个线程对原子变量的修改能够被其他线程“**看得到**”。之所以这里说“适当的处理”是因为后面提到的memory_order会导致行为上的差异。

基础类型的原子变量的操作，例如CAS，基本上是由CPU的机器指令实现，而互斥锁和读写锁需要调用操作系统并且要进入系统态，因此原子变量操作比互斥锁和读写锁的效率要高的多（测试下来要高一个数量级）。



### volatile不适用

用`volatile`并不能解决上述的数据不一致的问题，可以用以下代码测试：

```c++
#include <iostream>
#include <thread>

volatile int a = 0;

void worker()
{
    for (int i = 0; i < 1000000; ++i)
    {
        a += 1;
    }
}

void multiThreadAdd()
{
    auto t1 = std::thread(worker);
    auto t2 = std::thread(worker);
    auto t3 = std::thread(worker);

    t1.join();
    t2.join();
    t3.join();

    // 应该输出3000000，但是用volatile并不能得到预期的结果。
    std::cout << "sum is: " << a << std::endl;
}

int main()
{
    multiThreadAdd();
}

```

而且`volatile`的初衷是表示用访问内存的形式来实质上访问IO设备，即把IO设备映射成内存区域，并不是用于解决多线程的问题的。



## 内存模型

原子变量的方法 `fetch_add` 是可以接受第二个参数 `std::memory_order` 的，定义了6种可用值，如下所示：

- memory_order_relaxed
- memory_order_consume
- memory_order_acquire
- memory_order_release
- memory_order_acq_rel
- memory_order_seq_cst

这个参数揭示了三种内存访问模型：

- 最终一致性
- 顺序一致性
- 获取-释放

三种内存访问模型跟代码重排序很有关系。



### 代码重排序

代码乱序是提升CPU处理性能的一种有效办法。在编译阶段，编译器会根据自己的判断在不改变程序运行结果的前提下调整代码的执行顺序，提升CPU流水线的性能；在运行阶段，CPU也会打乱指令以提升CPU流水线的性能。

但在多线程中，这样的代码重排序可能会产生在单线程中不会出现的问题。

代码重排序有利于提升CPU流水线性能，因此我们在保证程序结果正确的前提下尽量不要禁止代码重排序。



### 最终一致性

`memory_order_relaxed`代表了最终一致性。最终一致性只保证原子变量上读写的原子性和修改顺序的一致性（即一个线程对原子变量的修改一定会被其他线程**“正确地”**看到），不会阻止代码重排序。

看一下 [std::memory_order - cppreference.com](https://en.cppreference.com/w/cpp/atomic/memory_order#Sequentially-consistent_ordering) 上的例子：

```c++
// Thread 1:
r1 = y.load(std::memory_order_relaxed); // A
x.store(r1, std::memory_order_relaxed); // B

// Thread 2:
r2 = x.load(std::memory_order_relaxed); // C 
y.store(42, std::memory_order_relaxed); // D
```

从表面上看不可能出现 `r1 = r2 = 42`的情况，但实际上却可能，这是由于代码重排序造成的。当D重排序到C的前面（单线程下C和D谁先执行结果都一样），就可能产生 `r1 = r2 = 42`。

但上面计数器的例子中可以使用`memory_order_relaxed`得到正确的结果，下面是代码片段。

```c++
void worker()
{
    for (int i = 0; i < 1000000; ++i)
    {
        a.fetch_add(1, std::memory_order_relaxed);
    }
}
```

最终一致性最不严格，理论上来讲效率最高（实际测试没发现）。



### 顺序一致性

顺序一致性是最严格的，在`memory_order_relaxed` 的效果之上增加了新的保证：

> 保证原子变量以及非原子变量的内存访问的顺序，禁止编译器对代码重排序，可能会生成专门的指令禁止CPU对指令重排序

顺序一致性最严格，理论上也是最慢。



### 获取-释放

获取-释放模式包含：获取和释放两步骤，并在一定程度上禁止代码重排。

- 获取（Acquire）

  本线程知道所有其他线程对内存所做的修改，即让本线程所在的CPU核心上的失效队列（invalidate queue）为空。

- 释放（Release）

  本线程所做的所有对内存的修改，都已经通知到其他CPU核心（进入对方的失效队列中），即让本线程所在的CPU核心上的存储缓冲区（store buffer）为空。



`memory_order_acquire`代表获取操作，`memory_order_release`代表释放操作，`memory_order_acq_rel`代表获取加释放同时发生，`memory_order_consume`类似于`memory_order_acquire`，其区别可以忽略不计。

获取-释放模式适用范围很广，基本上它就是互斥锁的实现模式。



### 内存屏障

互斥锁和原子变量访问（memory order为`memory_order_relaxed`的除外）内存屏障用于阻止编译器和CPU对代码指令做重排序的，并且在某些CPU中会需要专门的指令来阻止CPU层面上的指令重排。

内存屏障分为好几种，这里不展开叙述。



STL的`atomic`模块的方法的`memory_order`参数的默认值基本上都是顺序一致性`memory_order_seq_cst`，这是稳妥的做法，但是牺牲了性能。为了更好的性能，在确定的情况下可以用其他的memory order 替代。



## 自旋锁

一般的互斥锁或者读写锁都不可避免地要调用操作系统的API，要经过用户态和系统态的切换，因此效率不高。而自旋锁（spin lock）是一种高效的避免操作系统层面调用的同步锁，是原子变量的应用场景之一。自旋锁由原子变量的`exchange`方法来实现。下面是一个简单（但可能有问题）的自旋锁的实现。

```c++
#include <atomic>
#include <iostream>
#include <thread>

class SpinLock
{
private:
    std::atomic<bool> mtx{false};

public:
    void lock()
    {
        while (mtx.exchange(true, std::memory_order_release));
    }

    void release()
    {
        mtx.store(false, std::memory_order_release);
    }
};

int s = 0;
SpinLock lck;

void worker()
{
    for (int i = 0; i < 1000000; ++i)
    {
        lck.lock();
        s += 1;
        lck.release();
    }
}

int main()
{
    auto t1 = std::thread(worker);
    auto t2 = std::thread(worker);
    auto t3 = std::thread(worker);

    t1.join();
    t2.join();
    t3.join();

	// 一样能得到正确的结果。
    std::cout << "sum is: " << s << std::endl;
}
```



## 性能提升思路

1. 尽量让操作数据在核内缓存中；

2. 尽量不要禁止代码重排序（在保证正确的前提下）；

3. 能用原子变量解决的问题不要用操作系统提供的锁；

4. 利用好自旋锁。

   

## 引用

1. [std::memory_order - cppreference.com](https://en.cppreference.com/w/cpp/atomic/memory_order)

2. [std::atomic_thread_fence - cppreference.com](https://en.cppreference.com/w/cpp/atomic/atomic_thread_fence)

3. [敲黑板！原子变量与内存模型是什么鬼！-阿里云开发者社区 (aliyun.com)](https://developer.aliyun.com/article/585355)
