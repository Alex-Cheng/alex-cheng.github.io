# Atomic variables and memory access order models


This article mainly introduces atomic variables and memory access order models, and answers some questions. The following knowledge systems are involved:

- multi-core CPUs and storage systems

- atomic variables

- memory models
- eventual consistency
- sequential consistency
- release-acquire

- spinlocks
- implementation with atomic variables
- avoidance strategies

will be explained one by one below.



## Multi-core CPUs and memory systems

Since the frequency of CPUs cannot be effectively increased due to physical laws, multi-core CPUs have been developed, that is, a CPU chip contains multiple “small CPUs”, which we call CPU cores. If the computing power of each CPU core can be fully utilized, the overall computer processing performance can be greatly improved. The frequency of memory access in a program is very high. Basically, whenever there is a calculation, it is inevitable to load data from memory, and then write the result back to memory. However, the current x86/x64 multi-core system is an SMP structure with shared memory, and only one CPU core can access memory at a time (*To access memory, a CPU core must first gain control of the memory bus, and only one CPU core can gain control of the memory bus at any given time*). Therefore, accessing memory has become a bottleneck.

To solve this bottleneck, we let each CPU core have its own level 1 cache (L1 cache), but this brings another problem: how to coordinate and synchronize the data in the cache in a multi-core system. This introduces the MESI protocol. In order to minimize the “drag” on the CPU when implementing the MESI protocol, a store buffer and an invalidate queue are introduced.

I will explain them one by one below.

### Overall structure

```asciiarmor
|-----------------------------------------------------------------------|
|       Core 1    |      Core 2     |     Core 3      |      Core 4     | 1. The closer the access, the faster the speed;
|     Register    |    Register     |     Register    |     Register    | 2. Registers and L1 cache are exclusive to each core;
|     L1 cache    |    L1 cache     |     L1 cache    |     L1 cache    | 
|   Level 2 cache |   Level 2 cache |   Level 2 cache |   Level 2 cache | 
|-----------------------------------------------------------------------|
|                            Level 3 cache (L3)                         | 3. The lower cache (e.g. L3 cache) and memory are shared by multiple cores;
|-----------------------------------------------------------------------|
|                            Memory                                     |
|-----------------------------------------------------------------------|
|                            External storage                           | 4. External storage is the slowest, especially in terms of latency, which is very large compared to memory and cache.
|-----------------------------------------------------------------------|
```



### Cache structure

```asciiarmor
|------------------------------------------------|
|                       Cache                    |
|------------------------------------------------|
|         Cache line usually 64 or 128 bytes     | 
| contains:                                      |
| - address of corresponding memory block(tag...)|
| - data + MESI status                           |
|------------------------------------------------|
|         more cache lines                       |
|           ... ...                              |
|------------------------------------------------|
```



### MESI protocol

Each cache line has a status:

- M - modified, does not match the data in memory, and the cache of the other CPU cores **does not** cache this memory block;
- E - exclusive, matches the data in memory, and the cache of the other CPU cores **does not** cache this memory block;
- S - shared, matches the data in memory, and the cache of the other CPU cores **has already** cached this memory block;
- I - invalid, the cache line is invalid, indicating that the contents of the corresponding memory block have been modified by other CPU cores (making the contents of this cache line **out of date**).



### Store buffer and invalidate queue

Each cache line corresponds to a small piece of memory. According to the MESI protocol, when a CPU core modifies the content of a cache line, it needs to notify the caches of other CPU cores that also cache this memory block, and vice versa. However, in order to be efficient, the CPU cannot wait for this action to be completed, or it should not interrupt the current task when being notified and process it in real time. Therefore, a store buffer and an invalidate queue are introduced.

```asciiarmor
|----------------|                        | |----------------|
|   CPU core     | -> store buffer ->     | |    CPU core    |
|                |    <MESI protocol      | |                | 
|   cache        | <- invalidate queue <- | |    cache       |
|----------------|                        | |----------------|

```

The purpose of the store buffer and invalidate queue is to change synchronous updates to asynchronous updates without affecting CPU execution. However, this in turn brings the problem of inconsistent cached data.

***Data inconsistency problem***

> *Suppose that CPU core 1 loads the data of memory block addr1; at the same time, CPU core 2 also loads the data of memory block addr1. When CPU core 1 modifies the data of addr1, even if the modified data is written back to the memory in time, the cache of CPU core 2 may not be updated, resulting in the modification of the data of addr1 by CPU core 1 being “**invisible**” to CPU core 2. *
>
> In the past, volatile was used to mark variables shared by multiple threads, but this method is no longer applicable.



## Atomic variables

Atomic variables are variables that can be shared across threads and are also “thread-safe” variables. They will not cause race conditions due to multi-threaded access or problems where data is not updated in time due to the CPU cache. Using atomic variables can solve the above problems.

```cpp
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
    // Should output 3000000, using an atomic variable to get the expected result.
    std::cout << "sum is: " << a << std::endl;
}

int main()
{
    multiThreadAdd();
}

```

Atomic variables are used to ensure that the storage buffer and the invalidation queue mentioned above are handled properly, so that modifications to an atomic variable by one thread can be “**seen**” by other threads. The reason for saying “properly handled” here is that the memory_order mentioned later will lead to differences in behavior.

Operations on atomic variables of basic types, such as CAS, are basically implemented by the CPU's machine instructions, while mutexes and read-write locks require calls to the operating system and entry into the system state. Therefore, atomic variable operations are much more efficient than mutexes and read-write locks (tested to be an order of magnitude higher).



### volatile is not applicable

Using `volatile` does not solve the above data inconsistency problem. You can test it with the following code:

```cpp
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

Moreover, the original intention of `volatile` is to indicate that memory access is used to essentially access IO devices, i.e., to map IO devices into memory regions, and it is not used to solve multi-threading issues.



## Memory model

The atomic variable method `fetch_add` can accept a second parameter `std::memory_order`, which defines 6 available values, as follows:

- memory_order_relaxed
- memory_order_consume
- memory_order_acquire
- memory_order_release
- memory_order_acq_rel
- memory_order_seq_cst

This parameter reveals three memory access models:

- eventual consistency
- sequential consistency
- acquire-release

The three memory access models are related to code reordering.



### Code reordering

Code reordering is an effective way to improve CPU processing performance. During the compilation phase, the compiler will adjust the execution order of the code according to its own judgment without changing the result of the program execution, so as to improve the performance of the CPU pipeline. During the execution phase, the CPU will also reorder instructions to improve the performance of the CPU pipeline.

However, in multi-threading, such code reordering may cause problems that do not occur in single-threading.

Code reordering is beneficial to improving CPU pipeline performance, so we try not to prohibit code reordering as long as the correct result of the program is guaranteed.



### Final consistency

`memory_order_relaxed` represents final consistency. Final consistency only guarantees the atomicity of reads and writes to atomic variables and the consistency of the modification order (i.e., a thread's modification to an atomic variable will definitely be seen by other threads** “correctly”**), and will not prevent code reordering.

Look at the example on [std::memory_order - cppreference.com](https://en.cppreference.com/w/cpp/atomic/memory_order#Sequentially-consistent_ordering):

```cpp
// Thread 1:
r1 = y.load(std::memory_order_relaxed); // A
x.store(r1, std::memory_order_relaxed); // B

// Thread 2:
r2 = x.load(std::memory_order_relaxed); // C 
y.store(42, std::memory_order_relaxed); // D
```

On the surface, it seems impossible for `r1 = r2 = 42` to occur, but in fact it is possible due to code reordering. When D is reordered in front of C (in single-threaded execution, the result is the same regardless of which of C and D executes first), `r1 = r2 = 42` may occur.

However, the above example of a counter can use `memory_order_relaxed` to get the correct result. The following is a code snippet.

```cpp
void worker()
{
    for (int i = 0; i < 1000000; ++i)
    {
        a.fetch_add(1, std::memory_order_relaxed);
    }
}
```

Final consistency is the least strict, and theoretically the most efficient (no practical test found).



### Sequential consistency

Sequential consistency is the strictest, adding new guarantees on top of the effects of `memory_order_relaxed`:

> guarantees the order of memory accesses for atomic variables as well as non-atomic variables, prohibits the compiler from reordering code, and may generate special instructions to prohibit the CPU from reordering instructions

Sequential consistency is the strictest and theoretically the slowest.



### Acquire-Release

The Acquire-Release model involves two steps: acquire and release, and to some extent prohibits code reordering.

- Acquire

This thread knows all the modifications made to memory by other threads, i.e., the invalidate queue on the CPU core where this thread is located is empty.

- Release

All memory modifications made by this thread have been notified to other CPU cores (entered the other party's invalidate queue), that is, the store buffer on the CPU core where this thread is located is empty.



`memory_order_acquire` represents an acquire operation, `memory_order_release` represents a release operation, and `memory_order_acq_rel` represents an acquire-and-release operation. `memory_order_consume` is similar to `memory_order_acquire` and the difference is negligible.

The acquire-and-release model is widely applicable and is basically an implementation model for mutexes.



### Memory barriers

Mutexes and atomic variable access (except for memory order `memory_order_relaxed`) Memory barriers are used to prevent the compiler and CPU from reordering code instructions, and on some CPUs, special instructions are required to prevent instruction reordering at the CPU level.

There are several types of memory barriers, which will not be described here.



The default value of the `memory_order` parameter for the methods of the STL `atomic` module is basically the sequential consistency `memory_order_seq_cst`, which is a safe approach but sacrifices performance. For better performance, other memory orders can be used in certain situations.



## Spin locks

A mutex or read-write lock generally involves an inefficient call to the operating system API and switching between user mode and kernel mode. A spin lock is a highly efficient synchronization lock that avoids calls to the operating system and is one of the application scenarios for atomic variables. A spin lock is implemented using the `exchange` method of an atomic variable. The following is a simple (but possibly problematic) implementation of a spin lock.

```cpp
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



## Performance improvement approaches

1. Try to keep the data for operations in the kernel cache;

2. Try not to prohibit code reordering (provided that correctness is guaranteed);

3. Don't use locks provided by the operating system for problems that can be solved using atomic variables;

4. Make good use of spinlocks.



## References

1. [std::memory_order - cppreference.com](https://en.cppreference.com/w/cpp/atomic/memory_order)

2. [std::atomic_thread_fence - cppreference.com](https://en.cppreference.com/w/cpp/atomic/atomic_thread_fence)

3. [Knock on the blackboard! What the hell are atomic variables and the memory model! - Alibaba Cloud Developer Community (aliyun.com)](https://developer.aliyun.com/article/585355)
