# 如何提高程序性能

本文主要探讨提高程序性能的途径、方法和最佳实践。



## 三个方向

- 尽可能利用缓存

- 尽可能利用多核

还有一个小方向是***尽可能减少内存复制***，这个产生出右值引用、移动构造函数、移动赋值等概念。

> 貌似以上两条是“很简单而无干货的两句话”，但是却是确确实实的大方向，沿着这两个大方向，会衍生出很多优化方法出来。

沿着这两个方向，我们的基本方法是分层、折衷与交换。

> 分层与交换
>
> 计算机领域中甚至扩展到更大范围，都有一个“鱼与熊掌不可兼得”的道理。比如空间（存储容量、空间复杂度等）与时间（访问速度、时间复杂度等）通常是不可兼顾的。因此产生折衷、分层、“以X换Y”的方法论。



关于多核并行计算，有阿姆达尔定律（英语：Amdahl's law，Amdahl's argument）

![image](https://user-images.githubusercontent.com/1518453/194759190-94b44755-109b-4b32-a54c-8cc743e70682.png)


## 尽可能利用缓存

缓存是填补了存储系统的不同层级之间的速度差异。

### CPU与内存的速度差别很大

在CPU流水线的加持下，在精简指令系统下，通常一条指令只需要一个时钟周期。而内存访问（假使没有缓存）通常要耗费上百个时钟周期。两者差别是上百倍的。直观的来看也容易理解，内存条离CPU在主板上就相隔很远，其数据总线肉眼可见，而CPU芯片则是很小一块，其内部晶体管是纳米级的。

> #### 吞吐量与时延
>
> 这里说的速度，是时延而不是吞吐量。如果只看吞吐量，内存访问并不慢，因为是批量读取。如果看时延，内存访问很慢，因为要等上百个时钟周期。关于吞吐量和时延的区别可以打个比方，就是从几公里之外的冷冻仓库里拉一车雪糕到你家里，你要等很久，但是量很大。

### 芯片内的缓存CACHE

缓存是内置在芯片里的，分为L1、L2、L3等级别，用L_(N)表示各级缓存，N越小容量越小访问速度越快，N越大容量越大访问速度越慢。L1缓存能达到寄存器级别的访问速度（即读写只需要一个时钟周期）。



### 金字塔型的计算机存储系统

计算机存储系统采用分层和折衷的方法，下图展现了金字塔型的计算机存储系统。越往上容量越小、访问速度越快；越往下容量越大、访问速度越慢。不同层级的容量与速度的差别是x10，x100的。数据由外存到内存，再由内存到缓存，再由缓存到寄存器，然后被运算器处理。

在多核CPU中，每个核都有自己的L1、L2缓存，而L3及以下的缓存是多核共享的。

![image-20221009175138502](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/master/_posts/images/image-20221009175138502.png)

由于缓存的存在，CPU与内存的访问由直接访问变成了间接访问。

```Shell
CPU <-> 内存 
变成了
CPU <-> 缓存 <-> 内存
```



### 缓存的工作方式

#### 局部性原理

缓存的工作方式

#### Cache Line

一个`cache line`通常有32/64/128字节，对应内存中的一块区域（映射方法有多种，比如直接映射）

当读取内存时，首先看要读取的内存是否在缓存的某个cache line中，如果是，则访问缓存；否则从内存里加载数据到缓存的某个cache line中。在写入内存时，也是首先要看写入的内存是否在缓存的某个cache line中，如果是，则写入到缓存，未来某个时候会回写到内存；否则从内存里加载数据到缓存的某个cache line中。

对这块内存区域的写入，哪怕只是一个字节，也会使整个cache line失效。

#### 命中率

如果要访问的内存的数据已经在缓存中了，则成为“命中”，否则就是cache missing。

```
命中率 = 命中次数 / 总的访问次数
```

命中率很大影响性能，比如：95%命中率（未命中率5%）可能比90%的命中率（未命中率10%）快一倍。这是因为未命中而耗费的时间占主要成分，而未命中率5%与10%的差一倍。

### 提高命中率

尽可能利用缓存就是尽量提升缓存命中率，以下几种方法都是可以提高命中率的（但注意有些方法在多核环境下反而对性能有害）：

1. 提高空间局部性
   1. 优先使用顺序存储数据结构，比如PODArray、底层为顺序表的hash map；
   2. 用顺序扫描替代随机访问。
2. 提高时间局部性
   1. 让声明变量和使用变量的位置尽量靠近。
3. 避免cache line失效。



## 尽可能利用多核

当前CPU芯片的晶体管规模仍旧遵循摩尔定律，而CPU的单核主频和运算能力已经没有太大发展了（受到物理特性的限制），而CPU核的数量在增长。因此一定要利用好多核。

![img](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/master/_posts/images/how-to-make-program-faster-img1.png)

### 减少多线程之间的影响

利用好多核的要义就是尽量减少多线程之间的互相干扰，包括且不限于锁、缓存。

以一个分布式计数器作为例子。



#### 读写锁

使用`std::shared_mutex` 实现读写锁，代码如下：

```C++
class DistributedCounter {
public:
        typedef long long value_type;
        static std::string name() { return "lockedcounter"; };

private:
        value_type count;
        std::shared_mutex mutable mtx;
public:
        DistributedCounter() : count(0) {}

        void operator++() { std::unique_lock<std::shared_mutex> lock(mtx); ++count; }
        value_type get() const { std::shared_lock<std::shared_mutex> lock(mtx); return count; }
```

多个线程只有一个锁，因此线程之间干扰很厉害，效率损失很大。



#### 分桶-读写锁

先设置多个桶，每个桶都有计数器和读写锁，先哈希分片到一个桶上，再对该桶用锁。

```C++
class DistributedCounter
{
        typedef size_t value_type;
        struct bucket
        {
                std::shared_mutex sm;
                value_type count;
        };

        static size_t const buckets{ 128 };
        std::vector<bucket>counts{ buckets };
public:
        static std::string name() { return"lockedarray"; }

        void operator++() {
                size_t index = std::hash<std::thread::id>()(std::this_thread::get_id()) % buckets;
                std::unique_lock<std::shared_mutex> ul(counts[index].sm); counts[index].count++;
        }
        value_type get() { return std::accumulate(counts.begin(), counts.end(), (value_type)0, [](auto acc, auto& x) { std::shared_lock<std::shared_mutex> sl(x.sm); return acc + x.count; }); }
};
```

多个线程因为哈希的作用，对内存的访问分散在不同的桶上，因此线程间的干扰小了很多。但是线程间关于缓存的干扰比较大。



#### 分桶-独占cacheline-读写锁

由于一个cache line有32/64/128字节，前面的方法会导致多个桶会被装入一个cache line中，而对cache line中哪怕一个字节的修改都会使得cache line处于“被修改”状态，导致其他CPU核的同一个内存位置的cache line失效。

假设b1, b2, b3, b4能够被装入一个cache line中，有4个线程t1, t2, t3, t4处在4个CPU核c1, c2, c3, c4中。t1, t2, t3, t4分别访问b1, b2, b3, b4。那么会产生4个CPU核的L1缓存中都有一个cache line缓存了b1, b2, b3, b4。当线程t1修改了b1时，虽然并没有修改b2,b3,b4，但是却导致其他三个核的cache line失效。假如这时t2要访问b2，明明可以从自己的核的缓存中取值，却不得不以cache missing的逻辑从内存重新加载数据。

为了让每个桶独占cache line，加入padding把桶所占的内存“撑开”。代码如下：

```C++
class DistributedCounter
{
        typedef size_t value_type;
        struct bucket
        {
                std::shared_mutex sm;
                value_type count;
                char padding[128]; // “撑开”内存，独占一个cache line。
        };

        static size_t const buckets{ 128 };
        std::vector<bucket>counts{ buckets };
public:
        static std::string name() { return"lockedarray"; }

        void operator++() {
                size_t index = std::hash<std::thread::id>()(std::this_thread::get_id()) % buckets;
                std::unique_lock<std::shared_mutex> ul(counts[index].sm); counts[index].count++;
        }
        value_type get() { return std::accumulate(counts.begin(), counts.end(), (value_type)0, [](auto acc, auto& x) { std::shared_lock<std::shared_mutex> sl(x.sm); return acc + x.count; }); }
};
```



#### 分桶-独占cacheline-原子变量

原子变量通常比锁更轻量，因为可以编译成特殊的CPU机器指令，例如 `LOCK ADD X, Y` 、`XCHG`等。代码如下：

```C++
class DistributedCounter
{
        typedef size_t value_type;
        struct bucket
        {
                std::shared_mutex sm;
                std::atomic<value_type> count;
                char padding[128]; // “撑开”内存，独占一个cache line。
        };

        static size_t const buckets{ 128 };
        std::vector<bucket>counts{ buckets };
public:
        static std::string name() { return"lockedarray"; }

        void operator++() {
                size_t index = std::hash<std::thread::id>()(std::this_thread::get_id()) % buckets;
                counts[index].count++;
        }
        value_type get() { return std::accumulate(counts.begin(), counts.end(), (value_type)0, [](auto acc, auto& x) { return acc + x.count.load(); }); }
};
```

原子变量的访问时可以指定memory order，默认用的是理论上最慢却能保证结果一定正确的 *顺序一致性* 的memory order，在这个例子里可以用最快却最不严格的 *relaxed* memory order。在此不再赘述。

以下是以上4个方法在128核服务器上的测试结果：

![image2](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/master/_posts/images/how-to-make-program-faster-img2.png)

可以看出性能差别很大。

#### 其他方法

其他方法还包括无锁编程、自旋锁、pthread的读写锁，linux系统里的futex。

无锁编程从理论上看是最好的，因为线程之间几乎完全不干扰。



### 多核的性能必须在多核的机器上测试

多核相关的优化，在核数少的机器上可能并不能凸显出来对于性能方面带来的好处，在核多的机器上才能凸显出来性能的提升。

同样，要根据实际运行的机器的特性，做多核和缓存方面的性能优化。



### 单核的流水线

保证每个CPU核的执行流水线被充分使用，除了上面的缓存方面的优化外（cache missing就会破坏流水线），以下列出一些方法，这些方法也会帮助提高执行流水线的利用率。

1. 使用`[likely]`，`[unlikely]` 帮助分支判断；
2. 尽量用const T &，帮助编译器优化；
3. 加 __restrict 关键字帮助编译器优化；
4. 右值情况用右值，减少内存拷贝；
5. 选择合适的memory order，保证正确的前提下尽量少限制指令乱序，指令乱序会提高流水线利用率。



## 最佳实践总结

1. 尽量避免让每个线程独立访问的对象或者变量能够放在同一个cache line上；
2. 只读的内存与经常写入的内存尽量不要放在一起，避免被放在同一个cache line上；
3. 把多线程共享的部分尽量分成线程独享的分片（分桶）；
4. 尽量避免让频繁写入的内存区域影响其他的内存读写，即让该区域独占cache line；
5. 同时访问的几个变量或对象集合尽量放在一起；
6. 利用VTune等工具找到cache方面的瓶颈。

C++17的新特性：

- std::hardware_destructive_interference_size 
  若两个对象的内存地址距离  ***大于***  std::hardware_destructive_interference_size，则不会在一个cache line。

- std::hardware_constructive_interference_size
  若两个对象的内存地址距离  ***小于***  std::hardware_destructive_interference_size，则会在一个cache line。

  

## 不断地解决问题并产生新问题

这是一种规律，旧的问题解决了，并产生新的问题。

> 由于CPU的频率受限于物理定律而无法再有效提升，发展了多核CPU，即一个CPU芯片中包含多个“小CPU“，我们称之为CPU核心。
>
> 随后发现内存访问是瓶颈，因为内存不仅访问速度慢，而且还不能多核同时访问。为了解决这个问题引入了核内缓存，让每个CPU核都能并行地获取运算所需要的数据。
>
> 但这又带来了新的问题：多个CPU核中的缓存的数据如何同步（同一块内存的数据可能会被缓存在多个CPU核内）。
>
> 解决这个问题就引入了MESI协议。为了在实施MESI协议时尽量少“拖累”CPU（即让CPU核不用等同步完成），于是引入了存储缓冲区（store buffer）和无效队列（invalidate queue）的概念。
>
> 另外为了保证CPU执行流水线的效能，编译器和CPU可能会打乱指令执行顺序。
>
> 但这些优化可能让程序的执行结果变得不正确。因此，为了既保证正确又保证并行性，就引入了内存顺序（memory order）的概念……

## 参考资料

1. https://semiwiki.com/ip/312695-white-paper-scaling-is-falling/
2. https://courses.cs.washington.edu/courses/cse378/09wi/lectures/lec15.pdf
3. https://en.cppreference.com/w/cpp/thread/hardware_destructive_interference_size
4. https://courses.cs.washington.edu/courses/cse378/09wi/lectures/lec15.pdf
