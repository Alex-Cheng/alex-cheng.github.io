# 多线程与同步



多线程并行执行能够大大提升程序运行效率，但是也要注意随之带来的线程间同步问题，避免竞态条件（“Race Condition”）引起的难以发现的bug。这篇总结一下线程的创建和销毁、等待和恢复、加锁和解锁、锁的类型以及在某些情况下可以替代锁的原子操作。



## 启动线程

创建`std::thread`对象可以启动一个线程，例如：

```c++
#include <iostream>
#include <thread>

void worker()
{
	for (size_t i = 0; i < 10; ++i)
	{
		std::cout << "thread: " << std::this_thread::get_id() << std::endl;
	}
}

int main()
{
	std::thread t1(worker);
	t1.join();
}
```

`std::thread`的构造函数接收一个可执行对象和零到多个参数，在创建完毕后对应的线程就已经被创建并启动。

一个线程只能被一个`std::thread`对象关联，这个用`std::thread`的拷贝构造函数和拷贝赋值操作都被禁用来保证这一点。

`std::thread`对象的状态有*joinable*和*unjoinable*。*joinable*是表示有线程对应，它是可以“join”到本线程上来的，*join* 操作可以看作是当前线程等待`thread`对应的线程，直到它结束，就好像两条河流汇集在一起一样。*unjoinable*是表示没有线程对应或者对应的线程已经结束。一个*joinable*的线程在join之后就处于*unjoinable*状态。



### 主要方法

**`thread.join()`**  -  等待`thread`对象对应的线程结束，然后继续执行，就是将两条执行流汇集一起。之后该对象处于 *joinable* 状态。

**`thread.detach() `**  -  让`thread`对象与具体线程解绑，之后该对象处于 *unjoinable* 状态。



### std::thread对象的析构

我们遵从RAII的原则让`std::thread`管理线程资源，一般会在栈内存中创建`std::thread`对象同时获取线程资源，在离开作用域时析构该对象。执行`std::thread`对象的析构时，要保证其处于 *unjoinable* 状态，即要么未绑定实际线程资源（执行了`detach()`后的状态），要么实际线程已经结束（执行了`join（）`后的状态）。否则会调用`terminate()`强制结束程序，因为STL不知道析构时该怎么办：1. 默默执行`detach()`方法会导致实际线程失去控制；2. 默默执行`join()`方法会导致可能会无限等待下去。



## 普通锁

普通锁的行为是加锁和解锁，加锁即获取资源，解锁即释放资源。加锁后别的线程不可以再加锁，只能等待原先加锁的线程解锁后，才能加锁。这种方法保证了临界区互斥，即保证同时只能有一个线程执行临界区代码。



### 互斥量mutex

`std::mutex` 基础mutex（互斥量）。

`std::timed_mutex` 比基础mutex多两个带等待时间的方法：`try_lock_for()` 和`try_lock_until()`。

`std::recursive_mutex` 在基础mutex的基础上允许同一线程多次加锁。

`std::recursive_timed_mutex` 结合了`std::timed_mutex` 和 `std::recursive_mutex` 的特点。



### 加锁类

应该用RAII的方式保证互斥量的加锁和释放，避免在某些情况，比如抛出异常时某个加锁的mutex没有得到释放的情况。RAII的方式要用到 `std::lock_guard` 和 `std::unique_lock` 。

`std::lock_guard` 用法简单且轻量，其用法蕴含在构造函数里：

```c++
    explicit lock_guard(_Mutex& _Mtx); // 构造对象时，给互斥量加锁（获取锁）。

    lock_guard(_Mutex& _Mtx, adopt_lock_t);  // 构造对象时，获取互斥量，但是此时该互斥量已经在当前线程中加了锁，所以不执行加锁操作。
```

简单示例：

```c++
void foo()
{
    std::mutex mutex;
    {  // 进入花括号内范围加锁，离开花括号范围则释放。
        std::lock_guard<std::mutex> lock(mutex);
    }    
}
```



`std::unique_lock` 有跟`std::lock_guard`一样的简单用法，同时也有更丰富的用法。

```c++
class unique_lock { // whizzy class with destructor that unlocks mutex
public:
    using mutex_type = _Mutex;

    unique_lock() noexcept : _Pmtx(nullptr), _Owns(false) {}  // 创建对象但不带mutex互斥量

    _NODISCARD_CTOR explicit unique_lock(_Mutex& _Mtx)  // 创建对象并带有未加锁mutex互斥量，并同时加锁

    _NODISCARD_CTOR unique_lock(_Mutex& _Mtx, adopt_lock_t)  // 带有已加锁的mutex互斥量，不再加锁

    unique_lock(_Mutex& _Mtx, defer_lock_t) noexcept  // 带未加锁的mutex互斥量，但此时并不加锁

    _NODISCARD_CTOR unique_lock(_Mutex& _Mtx, try_to_lock_t)  // 带未加锁的mutex互斥量，并同时加锁，不过使用try_lock()

    template <class _Rep, class _Period>
    _NODISCARD_CTOR unique_lock(_Mutex& _Mtx, const chrono::duration<_Rep, _Period>& _Rel_time)  // 带有未加锁mutex互斥量，并同时加锁，并且引入等待超时机制，调用try_lock_for()时指定等待时长 

    template <class _Clock, class _Duration>
    _NODISCARD_CTOR unique_lock(_Mutex& _Mtx, const chrono::time_point<_Clock, _Duration>& _Abs_time)  // 带有未加锁mutex互斥量，并同时加锁，并且引入等待超时机制，调用try_lock_for()时指定等待到某个时间点
        
    _NODISCARD_CTOR unique_lock(_Mutex& _Mtx, const xtime* _Abs_time)  // 带有未加锁mutex互斥量，并同时加锁，并且引入等待超时机制，调用try_lock_for()时指定等待到某个时间点

    _NODISCARD_CTOR unique_lock(unique_lock&& _Other) noexcept : _Pmtx(_Other._Pmtx), _Owns(_Other._Owns)  // 移动构造，即可以在程序之间传递unique_lock实例
        
    void lock();  // 手动加锁
    bool try_lock(); // 尝试手动加锁
    bool try_lock_for(const chrono::duration<_Rep, _Period>& _Rel_time);  // 尝试手动加锁，并设定等待时间长度
    bool try_lock_until(const chrono::time_point<_Clock, _Duration>& _Abs_time);  // 尝试手动加锁，并设定等待到哪个时间点
    void unlock(); // 手动解锁
    bool owns_lock(); // 返回是否已加锁（已获得锁）
    explicit operator bool() const noexcept; // 返回与owns_lock()一样的值
}
```



`std::lock_guard` 只有构造函数和析构函数，只有一个简单用法，就是定义一个`std::lock_guard` 局部变量，这样在这个局部变量的作用域范围内都是在互斥锁的保护之下。

`std::unique_lock`功能就丰富的多，可以用于更复杂的场景，例如需要同时给多个互斥量加锁同时要避免死锁的情况。比如以下代码：

```c++
std::mutex a, b, c;

void lockMultiple()
{
	std::unique_lock<std::mutex> lock1(a, std::defer_lock);
	std::unique_lock<std::mutex> lock2(b, std::defer_lock);
	std::unique_lock<std::mutex> lock3(c, std::defer_lock);

	std::lock(lock1, lock2, lock3);  // 实现原子性同时加锁，避免死锁发生
}
```

不像`std::lock_guard`，`std::unique_lock`可以在构造之后的某个时间点加锁，也可以在析构之前释放。



### 辅助函数

- std::try_lock，尝试同时对多个互斥量上锁。
- std::lock，可以同时对多个互斥量上锁。

- std::call_once，如果多个线程需要同时调用某个函数，call_once 可以保证多个线程对该函数只调用一次。

`std::try_lock()`和`std::lock()`均可以实现为多个互斥量同时加锁且能保证原子性而避免死锁（设想多个线程同时对多个互斥量加锁的情况）。



## 读写锁 

读写锁可以减少不必要的互斥，例如在没有写操作的时候，同时发生读操作是允许的。读写锁用`std::shared_lock<std::mutex>` 实现，例如如下示例代码：

```c++
#include <iostream>
#include <mutex>
#include <shared_mutex>
#include <thread>

namespace {

    std::shared_mutex mtx;
    int count;

    int read()
    {
        std::shared_lock<std::shared_mutex> lck(mtx);  // 读锁用std::shared_lock
        std::cout << "read: " << count << std::endl;
        return count;
    }

    void write()
    {
        std::unique_lock<std::shared_mutex> lck(mtx);  // 写锁用std::unique_lock
        count++;
        std::cout << "write: " << count << std::endl;
    }
}

int main()
{
    std::thread read_threads[10];
    std::thread write_threads[10];

    for (int i = 0; i < 10; i++) {
        write_threads[i] = std::thread(write);
        read_threads[i] = std::thread(read);
    }

    for (int i = 0; i < 10; i++) {
        read_threads[i].join();
    }
    for (int i = 0; i < 10; i++) {
        write_threads[i].join();
    }
    return 0;
}

```

互斥量用`std::shared_mutex`，读锁用`std::shared_lock`，写锁用`std::unique_lock`。

`std::shared_lock`的成员方法和使用方式与`std::unique_lock`类似，不再赘述。



## 自旋锁

自旋锁的好处是不用调用系统API，因此不用从用户态转到系统态。当前的C++（C++20）没有实现自旋锁，但是可以用来实现原子操作的`std::atomic_flag` 来实现。在下面介绍`std::atomic_flag`时会列出详细示例代码。



## 原子操作

对于一个简单的值的读取和修改，不必用给临界区代码块加锁的方式，这样效率很不高。而更好的方法是使用原子操作，原子操作意思是该操作不可分割，要么完成度0%，要么完成度100%，不可能存在中间状态。

### std::atomic_flag基本用法

`std::atomic_flag`非常简单，在C++20之前主要就是两个函数 `test_and_set()`与`clear()`。

- `test_and_set()` 设置`std::atomic_flag`实例的标志状态为true，并且返回它原先的旧值；
- `clear()` 设置`std::atomic_flag`实例的标志状态为false。

C++20增加了如下几个函数：

- `test()` 

  返回标志状态。

- `wait()` 

  如果当前标志状态与给定的old值相同，则当前线程阻塞直到接收到唤醒通知信号，通知信号由`notify_one()`和`notify_all()`函数调用发出，唤醒后如果当前标志状态与给定old值的比较结果仍为相同，则将继续再次阻塞，否则结束等待继续往下执行；如果当前标志状态与给定的old值不同，则继续往下执行。

- `notify_one()`

  唤醒一个等待（阻塞）线程。

- `notify_all()`

  唤醒多个等待（阻塞）线程。

所有读取和改变标志状态的函数都会有一个带默认值的参数`std::memory_order order = std::memory_order_seq_cst`，例如：

```c++
bool test_and_set(std::memory_order order = std::memory_order_seq_cst) volatile noexcept;
```

一般用默认值就够了，因此不需要专门指定这个参数。后面会详细介绍`std::memory_order`。



### 用atomic_flag实现自旋锁

自旋锁用到了原子操作，而并没有调用操作系统的API，因此节省了用户态与系统态切换的代价。下面是用`std::atomic_flag`实现自旋锁的示例代码：

```c++
#include <atomic>

class Spinlock
{
private:
    std::atomic_flag atomic_flag = ATOMIC_FLAG_INIT;

public:
    void lock()
    {
       while (atomic_flag.test_and_set(std::memory_order_acquire))  // 不断重试，返回值为true代表处于上锁状态。
        {
        }
     
    }
    void unlock()
    {
        atomic_flag.clear(std::memory_order_release);  // 释放锁，此时如果存在另外一个线程在等待获取锁，则那个线程上的lock()方法将会退出while循环，退出方法，同时状态重新为上锁状态（标志状态为true）
    }
};
```

实际上在STL的代码实现中也存在内部定义的自旋锁实现，只是没有暴露出来。



### 普通atomic变量

`std::atomic`的基本定义如下：

```c++
template< class T >
struct atomic;
```

其他定义与上面类似，例如`template< class U > struct atomic<U*>`，这里先不介绍。

原子类型中比较重要的几个方法如下：

- `store`
  原子性地将旧的内容替换成给定的新的内容。

- `load`

  返回当前内容。

- `exchange`

  读取并返回原子变量的旧值，并赋予新值。

- `wait`，`notify_one`，`notify_all`

  与`std::atomic_flag`相同，不再赘述。

- `compare_exchange_weak` 与 `compare_exchange_strong`

  CAS操作，分布式系统常用，后面专门介绍。



### CAS操作

CAS意思是*Compare And Swap*，是分布式系统和并行程序中很重要的一个保证状态正确的机制。CAS是比较当前值是不是已经改变了，如果已经改变就不能更新，只有没有改变才能更新。一个实际例子是分布式交易系统中的减库存`S=S-1`，在给`S`减1的过程中不能被其他程序改变。

在STL里的`atomic`模块中有两个CAS函数值得说一下：

- `compare_exchange_weak`
- ``compare_exchange_strong`



两个函数的原型如下：

```c++
bool compare_exchange_weak( T& expected, T desired,
                            std::memory_order success,
                            std::memory_order failure ) noexcept;
                            
bool compare_exchange_weak( T& expected, T desired,
                            std::memory_order success,
                            std::memory_order failure ) volatile noexcept;

bool compare_exchange_weak( T& expected, T desired,
                            std::memory_order order =
                                std::memory_order_seq_cst ) noexcept;

bool compare_exchange_weak( T& expected, T desired,
                            std::memory_order order =
                                std::memory_order_seq_cst ) volatile noexcept;

bool compare_exchange_strong( T& expected, T desired,
                              std::memory_order success,
                              std::memory_order failure ) noexcept;

bool compare_exchange_strong( T& expected, T desired,
                              std::memory_order success,
                              std::memory_order failure ) volatile noexcept;

bool compare_exchange_strong( T& expected, T desired,
                              std::memory_order order =
                                  std::memory_order_seq_cst ) noexcept;

bool compare_exchange_strong( T& expected, T desired,
                              std::memory_order order =
                                  std::memory_order_seq_cst ) volatile noexcept;

```

这两个函数会比较原子变量的当前值与`expected`值（即期望值），如果相等，则把当前值修改成`desired`值（即设定值），返回true；如果不相等，则将`expected`值改成原子变量的当前值，不改变原子变量的值，返回false。

比较与赋值都是基于bit位的，不会调用构造函数、比较运算符函数和赋值运算符函数，类似于只调用`std::memcmp`和 `std::memcpy`来进行比较和赋值。



`*-weak`与`*-strong`的区别是前者允许偶尔的假失败，即明明两者值相同而返回false。这种假失败可能是因为内存对齐的原因，也可能是因为同一个值的二进制表示不是总是相同。但是weak的版本是效率更高。



### std::memory_order

`std::memory_order` 指定了内存访问的方式，包括常规的、非原子的内存访问。在多核系统上没有任何约束的情况下，当多个线程同时读写多个变量时，一个线程可以观察到值的变化顺序不同于另一个线程写入它们的顺序。实际上，甚至在多个读数据的线程之间也可能观察到不同顺序的数据更改。由于内存模型所允许的编译器转换，甚至在单处理器系统上也可能发生一些类似的影响。STL库中所有原子操作的函数中都有默认的`std::memory_order`参数，比如`std::memory_order_seq_cst` 就作为某些原子操作函数的默认值，其含义是保证顺序一致性，即所有的线程观察到的整个程序中内存修改顺序是一致的，这也是效率最低的一种方式，意味着不能很好地利用CPU Cache。在高级场景下可以为STL库的原子操作显式地给出不同于默认值的std::memory_order参数来进行效率优化。

可选择的内存序（memory order）常量

- std::memory_order_relaxed
- std::memory_order_consume
- std::memory_order_acquire
- std::memory_order_release
- std::memory_order_acq_rel
- std::memory_order_seq_cst

以上的常量作为参数传递给atomic原子变量的函数中，解决的是多核编程中对共享变量访问的效率与正确性兼顾的问题，因为每个核有自己的cache和寄存器，所以同一个变量在多个线程中是可能有多个副本的，这样多个线程在多个核中对同一个变量读写可能会出现不可见对方的修改的问题。这部分需要另开一篇解释，这里不再详述。



## 等待与唤醒

`wait`家族用于等待，包含`wait`、`wait_for`、`wait_until`；`notify`家族用于唤醒，包含`notify_one`、`notify_all`。

`wait`与`notify`出现在`atomic`、`condition_variable`、`future`等类型的成员列表中，其行为都是相似的：

> 调用`wait`家族成员以挂起当前线程并等待唤醒（以及可能的附加条件成立），调用`notify`家族成员以唤醒。



### 条件变量condition_variable

`condition_variable`是同步原语，用于阻塞一个或者多个线程，并在条件合适的时候唤醒它们。以C++ Reference的示例代码做例子。

```c++
#include <iostream>  // 互斥量
#include <atomic>  // 原子变量
#include <condition_variable> // 同步原语
#include <thread>
#include <chrono>

using namespace std::chrono_literals;
 
std::condition_variable cv;
std::mutex cv_m;
int i;
 
void waits(int idx)
{
    std::unique_lock<std::mutex> lk(cv_m);  // 加锁，在 cv_m 上。
    if(cv.wait_for(lk, idx*100ms, []{return i == 1;}))  // 等待给定时间段（idx*100 ms），同时暂时性地释放锁，唤醒条件为 i == 1，若是条件不成立及时被notify唤醒也会立即重新进入等待状态。
        std::cerr << "Thread " << idx << " finished waiting. i == " << i << '\n';
    else
        std::cerr << "Thread " << idx << " timed out. i == " << i << '\n';
}
 
void signals()
{
    std::this_thread::sleep_for(120ms);
    std::cerr << "Notifying...\n";
    cv.notify_all(); // 唤醒所有cv上的等待线程，但是这次由于i == 1条件为false，因此唤醒实际是不成功的，被唤醒的线程会立即重新进入等待状态。
    std::this_thread::sleep_for(100ms);
    {
        std::lock_guard<std::mutex> lk(cv_m);
        i = 1;  // 在同步锁的保护下，修改共享变量i的值。
    }
    std::cerr << "Notifying again...\n";
    cv.notify_all(); // 唤醒所有cv上的等待线程，这次唤醒成功，因为i == 1条件为true。
}
 
int main()
{
    std::thread t1(waits, 1), t2(waits, 2), t3(waits, 3), t4(signals);
    t1.join();
    t2.join();
    t3.join();
    t4.join();
}

/*
输出：

Thread 1 timed out. i == 0
Notifying...
Thread 2 timed out. i == 0
Notifying again...
Thread 3 finished waiting. i == 1

*/
```





## Promise模式

Promise模式在很多语言中都很常见，这套模式是通用的。

`promise<T>`由worker线程持有，worker线程会将执行结果存入`promise<T>`。

`promise<T>::get_future()`返回的`future`实例被需要执行结果的另一个线程持有，并通过调用`future::get`方法等待并获得最终worker线程的执行结果。

`promise<void>`是另一种特殊的形式，这种情况下没有执行结果可存入，仅仅把`promise<void>`当成信号量来用，空调`set_value`即可发送信号，让阻塞线程继续执行。



以下是C++ reference上的示例代码：

```c++
#include <vector>
#include <thread>
#include <future>
#include <numeric>
#include <iostream>
#include <chrono>
 
void accumulate(std::vector<int>::iterator first,
                std::vector<int>::iterator last,
                std::promise<int> accumulate_promise)
{
    int sum = std::accumulate(first, last, 0);
    accumulate_promise.set_value(sum);  // 调用set_value并传入执行结果，并唤醒等待线程。
}
 
void do_work(std::promise<void> barrier)
{
    std::this_thread::sleep_for(std::chrono::seconds(1));
    barrier.set_value();  // 空调set_value，只为了唤醒另外的那个线程。
}
 
int main()
{
    // Demonstrate using promise<int> to transmit a result between threads.
    std::vector<int> numbers = { 1, 2, 3, 4, 5, 6 };
    std::promise<int> accumulate_promise;
    std::future<int> accumulate_future = accumulate_promise.get_future();
    std::thread work_thread(accumulate, numbers.begin(), numbers.end(),
                            std::move(accumulate_promise));
 
    // future::get() will wait until the future has a valid result and retrieves it.
    // Calling wait() before get() is not needed
    //accumulate_future.wait();  // wait for result
    std::cout << "result=" << accumulate_future.get() << '\n';  // 调用 accumulate_future.get()即暗含了wait()方法的调用，处于等待状态直到promise上设置了结果。
    work_thread.join();  // wait for thread completion
 
    // Demonstrate using promise<void> to signal state between threads.
    std::promise<void> barrier;
    std::future<void> barrier_future = barrier.get_future();
    std::thread new_work_thread(do_work, std::move(barrier));
    barrier_future.wait();
    new_work_thread.join();
}
```

