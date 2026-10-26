# C++ 协程 II：co_await 的等待机制与一个异步框架原型

C++20 的协程给了三个关键字，却几乎没有给任何"成品"：没有网络库，没有定时器，没有调度器。想真正用协程做异步，必须先回答一个问题——`co_await` 到底怎么等？谁来通知它"好了，可以回来了"？答案藏在 `co_await` 后面跟的那个对象里：**awaiter**。理解了它，你就理解了协程和整个异步世界之间的接口；再亲手装一个最小的事件循环，"谁来恢复协程"这件事就能自动运转起来。

## awaiter 三接口：三个问题，三种回答

先用一句话说全 `co_await` 的工作机制：**协程在 `co_await` 处检查结果是否就绪；没就绪就挂起自己，把"什么时候、由谁来恢复我"交给外部；条件满足后从挂起点继续，拿到结果往下走。**

"谁判断就绪、谁安排恢复、恢复时给什么"，这三件事由 awaiter 的三个接口负责：

| 接口 | 回答的问题 | 作用 |
| ---- | ---- | ---- |
| `await_ready()` | 结果是不是已经好了？ | 返回 true 就不挂起、直接继续——"无需等待时"的开销约等于零 |
| `await_suspend(handle)` | 挂起前要安排什么？ | 即将挂起时调用，你在这里决定"谁来恢复我"——存进事件循环、注册回调都行 |
| `await_resume()` | 恢复后返回什么？ | 恢复时调用，返回值就是整个 `co_await` 表达式的值 |

三个接口的调用时机与所在线程同样重要：

| 接口 | 什么时候调用 | 在哪个线程 |
| ---- | ---- | ---- |
| `await_ready()` | `co_await` 表达式求值时，第一个被调用 | 协程当前线程 |
| `await_suspend(handle)` | `await_ready()` 返回 false 之后、协程真正挂起之际；它返回后协程即挂起 | 协程当前线程，调用完控制权就交出去了 |
| `await_resume()` | 快路径：紧跟 `await_ready()` 之后；慢路径：`handle.resume()` 恢复之后第一件事 | 快路径：协程原线程；慢路径：调用 `resume()` 的那个线程 |

其中最关键的是 `await_suspend`——它是挂钩点，事件循环、I/O 完成端口、定时器，真实异步世界的魔法都发生在这一步：

> `await_ready` 和 `await_resume` 都是协程线程上的同步调用，只有 `await_suspend` 是控制权离开协程的那一刻。

顺带补全：`await_suspend` 除了返回 `void`，还有两种重载，职责各不相同：

| 返回类型 | 语义 |
| ---- | ---- |
| `void` | 协程保持挂起，等外部恢复 |
| `bool` | 返回 false 表示取消挂起，立即继续执行 `await_resume()` |
| `coroutine_handle` | 对称转移：不返回调用者，直接恢复句柄指向的另一个协程，避免深层递归 |

## 编译器眼中的 co_await

写下 `co_await expr` 后，编译器大致做这些事：先从 expr 拿到 awaiter（`expr` 本身、它的 `operator co_await` 成员或自由函数，标准库的 `std::suspend_always` / `std::suspend_never` 就是现成的 awaiter）；然后调 `await_ready()`——返回 true 就走快路径，直接调 `await_resume()` 取结果，整个过程没有任何挂起开销，这就是零成本抽象在协程上的体现。

返回 false 则走慢路径：保存协程状态，协程挂起，调 `await_suspend(handle)` 把句柄交给"安排恢复的人"。之后时间流逝，外部事件发生，某处调用 `handle.resume()`，协程恢复后第一件事就是调 `await_resume()` 取值，`co_await` 表达式返回，继续往下执行。

两个容易忽略的细节：其一，快路径下协程从没停过，但 `await_resume()` 照样会调——它永远在协程"逻辑上越过 `co_await` 这一点"的时刻执行；其二，慢路径下 `await_resume()` 跑在调用 `resume()` 的线程上，真实场景里可能就是网络库的 I/O 线程——它若要碰协程的局部状态，要清楚此刻在哪个线程。还有一个边界情况：挂起中的协程若被 `handle.destroy()` 销毁，`await_resume()` 永远不会被调用，挂起中的清理是 awaiter 设计者自己的责任。

## 三个最小 awaiter：把两条路径走一遍

光说不练还是抽象。下面写一个全程单线程、不碰网络的最小示例。先要一个最简单的协程返回类型 `Task`——不产出中间值，只负责"挂起、恢复、结束"：

```cpp
struct Task {
    struct promise_type {
        Task get_return_object() {
            return Task{std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        std::suspend_always initial_suspend() { return {}; }        // 初始挂起，等调用方启动
        std::suspend_always final_suspend() noexcept { return {}; } // 结束也挂起，调用方决定何时销毁
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };
    std::coroutine_handle<promise_type> handle;
    explicit Task(std::coroutine_handle<promise_type> h) : handle(h) {}
    ~Task() { if (handle) handle.destroy(); }
    void resume() { handle.resume(); }
};
```

然后是三个 awaiter，分别演示三种典型情况。

**第一个：结果总是就绪**——`await_ready()` 永远返回 true，像一次普通取值：

```cpp
struct ReadyAwaiter {
    int value;
    bool await_ready() const noexcept { return true; }   // 已就绪，不挂起
    void await_suspend(std::coroutine_handle<>) const noexcept {}  // 不会被调用
    int await_resume() const noexcept { return value; }  // 直接返回值
};
```

**第二个：总是挂起，等外部恢复**——`await_suspend` 把句柄交出去，外部想什么时候恢复就什么时候恢复：

```cpp
struct SuspendAwaiter {
    std::coroutine_handle<>* out_handle;  // 把句柄交给谁？
    bool await_ready() const noexcept { return false; }  // 需要挂起
    void await_suspend(std::coroutine_handle<> h) const noexcept {
        *out_handle = h;  // 挂钩点：把句柄交出去
    }
    void await_resume() const noexcept {}
};
```

**第三个：挂起等待，恢复时带回结果**——最接近真实异步 I/O 的模型：

```cpp
struct ReturnValueAwaiter {
    std::coroutine_handle<>* out_handle;
    int* result;  // 外部写入结果
    bool await_ready() const noexcept { return false; }
    void await_suspend(std::coroutine_handle<> h) const noexcept { *out_handle = h; }
    int await_resume() const noexcept { return *result; }  // 恢复时把结果带回来
};
```

用这三个 awaiter 写一个协程，main 里由调用方手动恢复，模拟"外部事件"：

```cpp
Task demo_coroutine(std::coroutine_handle<>& h1, std::coroutine_handle<>& h2, int& result) {
    int x = co_await ReadyAwaiter{42};                   // 路径 A：不挂起，直接得到 42
    co_await SuspendAwaiter{&h1};                        // 路径 B：挂起，等外部恢复
    int y = co_await ReturnValueAwaiter{&h2, &result};   // 挂起，恢复时带回结果
}

int main() {
    std::coroutine_handle<> h1, h2;
    int result = 0;
    auto task = demo_coroutine(h1, h2, result);

    task.resume();   // 协程启动，跑到第一个真正的挂起点停下
    h1.resume();     // 模拟：外部事件 #1 发生了
    result = 100;
    h2.resume();     // 模拟：异步操作完成，结果是 100
}
```

运行时能看到两条关键事实：`ReadyAwaiter` 那次 `co_await` 的日志里 `await_suspend` 根本没出现——快路径是真的没有挂起；而协程挂起后，控制权在 main 手里，**什么时候恢复、以什么理由恢复，完全由持有句柄的一方决定**。

## 组装原型：事件循环 + 定时器 awaiter

main 手动恢复只是教学简化。真实场景中协程成百上千，恢复时机由外部事件决定，不可能靠某个函数"记得"去恢复每一个协程。所以需要一个专门的角色，替我们记住"谁在等、等什么、什么时候该叫醒它"——事件循环。配上一个定时器 awaiter 作为第一个接入循环的等待源，框架原型就齐了。

事件循环内部只有两个数据结构——就绪队列和定时器堆：

```cpp
using Clock = std::chrono::steady_clock;

struct Timer {
    Clock::time_point deadline;
    std::coroutine_handle<> handle;
    bool operator>(const Timer& rhs) const { return deadline > rhs.deadline; }
};

class EventLoop {
public:
    void post(std::coroutine_handle<> h) { ready_.push_back(h); }              // 启动策略
    void call_later(Clock::time_point deadline, std::coroutine_handle<> h) {
        timers_.push({deadline, h});                                           // 定时策略
    }

    void run() {
        while (!ready_.empty() || !timers_.empty()) {
            // 1. 没有立即可做的事，睡到最近的定时器到点
            if (ready_.empty()) std::this_thread::sleep_until(timers_.top().deadline);
            // 2. 把到点的定时器转入就绪队列
            auto now = Clock::now();
            while (!timers_.empty() && timers_.top().deadline <= now) {
                post(timers_.top().handle);
                timers_.pop();
            }
            // 3. 取一个就绪协程，恢复执行
            if (ready_.empty()) continue;
            auto h = ready_.front();
            ready_.pop_front();
            h.resume();
        }
    }
private:
    std::deque<std::coroutine_handle<>> ready_;                                // 就绪队列（FIFO）
    std::priority_queue<Timer, std::vector<Timer>, std::greater<Timer>> timers_; // 定时器队列（最小堆）
};
```

`run()` 的主循环只有三步：睡到最近的定时器到点 → 到点的转进就绪队列 → 恢复一个就绪协程。定时器 awaiter 则把"等外部手动恢复"升级成"等事件循环到点恢复"：

```cpp
struct SleepAwaiter {
    EventLoop& loop;
    std::chrono::milliseconds duration;

    bool await_ready() const noexcept {
        return duration.count() <= 0;   // 零等待走快路径，不挂起
    }
    void await_suspend(std::coroutine_handle<> h) {
        loop.call_later(Clock::now() + duration, h);  // 挂钩点：句柄从这里进入事件循环
    }
    void await_resume() const noexcept {}
};
```

三接口一个没变，变的只是挂到谁身上。最后写两个交替 sleep 的协程，交给循环调度：

```cpp
using namespace std::chrono_literals;

Task worker(EventLoop& loop, const char* name) {
    print(name, "开始工作");
    co_await SleepAwaiter{loop, 100ms};
    print(name, "睡了 100ms 醒来，继续");
    co_await SleepAwaiter{loop, 50ms};
    print(name, "又睡 50ms，睡完收工");
}

int main() {
    EventLoop loop;
    std::vector<Task> tasks;
    tasks.push_back(worker(loop, "协程A"));
    tasks.push_back(worker(loop, "协程B"));
    for (auto& t : tasks) loop.post(t.handle);  // 放进就绪队列
    loop.run();                                 // 事件循环接管一切
}
```

运行输出的时间戳很有说服力：两个协程都在 0ms 启动、105ms 醒来——"同时"睡觉、"同时"醒来，全程只有 main 一个线程，等待期间线程在 `sleep_until` 里睡觉，CPU 时间为零。协程函数还是那个协程函数，装的东西从"调用方手动 resume"变成了"事件循环自动调度"：

> 三接口是标准定死的机制，循环、定时器、启动策略全是现装的库——机制定了，策略留给库。

## 不用手搓，标准库已经在路上

手搓是为了看清机制，工程上不用一直手搓。标准正在把这层做成成品：

| 版本 | 给了什么 | 一句话点评 |
| ---- | ---- | ---- |
| C++20 | 协程语言机制：三个关键字 + `coroutine_handle` / `promise_type` 等 | 只有零件，返回类型要自己封装 |
| C++23 | 第一个成品：`std::generator` | 生成器不用手写了 |
| C++26 | 异步执行框架：`std::execution`（sender/receiver 模型，P2300）+ 标准调度器 + `task` | 手搓的"事件循环 + 调度"，标准化的正是这一层 |

不过要如实交代：`std::execution` 标准已定（2024 年 6 月采纳），但主流标准库尚未提供实现，工程上可用参考实现 NVIDIA stdexec；标准网络库也不在 C++26 里，真实网络通信暂时仍要靠 Boost.Asio 或平台 API。

## 边界在哪里

这个原型只值几十行代码，它的价值是看清机制，距离生产还差得远：

- **生命周期靠手管**：`Task` 的析构直接 `destroy()` 句柄，没有引用计数、没有 owner 语义。协程还挂起着就被销毁时，awaiter 里登记的句柄就是悬垂指针——真实框架必须处理"协程死后回调找上门"的问题。
- **线程安全为零**：`EventLoop` 的队列和堆没有任何锁，只允许单线程使用。一旦多线程 `post` 或从 I/O 线程恢复协程，就是数据竞争。
- **异常无出路**：`unhandled_exception` 里直接 `std::terminate()`，协程体抛出的异常没有任何传递通道。
- **装配方式粗糙**：`SleepAwaiter` 通过引用直接拿着 `EventLoop`，每个协程都得手动传参。真实框架（包括 `std::execution`）会把调度器信息放进 `promise_type`，让协程"知道自己跑在哪个循环上"。
- **没有取消与组合**：超时取消、`when_all` 这类异步组合子，原型完全没有涉及。

理解了 awaiter 三接口，这些短板各自的解法其实都能在机制里找到位置——这也是先看清机制再上框架的意义。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第八集
