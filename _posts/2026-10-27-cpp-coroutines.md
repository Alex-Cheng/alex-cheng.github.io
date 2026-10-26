# C++ 协程：用同步的写法组织异步的任务

程序有大量时间花在"等"上：等网络响应、等文件读完、等数据库返回。真正花在计算上的往往只占小头，其余时间 CPU 在空转。等待的时候能不能切换去做点别的事，等结果就绪了再从停下的地方继续？这就是协程（coroutine）要解决的问题。C++20 把它收进了语言核心，本文从机制讲起，手写一个最小 Generator，看清挂起与恢复到底发生在哪里。

## 协程是什么

协程是一种可以中途暂停、保存执行状态，之后从暂停位置继续执行的程序机制。生活中处处是它的影子：给 AI 发一条指令，等结果期间去写周报；结果出来了，先恢复"我刚问到哪一步"的记忆，切回来继续。协程把这个动作做成了语言机制——**挂起（suspend）与恢复（resume）**。

最容易混淆的是协程与线程的关系，它们解决的是完全不同的问题：

| | 解决的问题 | 关注点 |
| ---- | ---- | ---- |
| 线程 | 代码由哪个执行资源（CPU 核）运行 | 并发执行的"执行者" |
| 协程 | 程序如何挂起和恢复 | 执行流程的控制 |

> 协程不自动带来多线程。它提供的是可挂起、可恢复的执行机制，一个协程完全可以自始至终跑在同一条线程上。

## 有栈与无栈：两条路线

不管哪种实现，协程都要解决三件事：保存现场（记住执行到哪、保留还需要的数据）、交出控制权、恢复执行。业界走出了两条路线：

| | 有栈协程（Stackful） | 无栈协程（Stackless） |
| ---- | ---- | ---- |
| 保存现场 | 独立栈 + 完整寄存器上下文 | 挂起后仍需的变量存入协程帧 |
| 交出控制权 | 任意普通函数里都能挂起整条调用链 | 只能在协程函数内部明确的挂起点返回 |
| 恢复执行 | 切回独立栈，恢复上下文 | 重新进入状态机，按恢复点跳转 |

有栈协程更灵活，但代价是每个协程要备一份独立栈——一万个协程就是一万份栈空间，哪怕大部分时间只用到一点点；切换时要保存和恢复完整寄存器上下文，像线程切换一样；而且调用栈可能在任意函数里被切走，编译器很难做内联等激进优化。

无栈协程刚好反过来：编译器只把挂起后还会用到的变量存进协程帧，按需保存，没有冗余；挂起点明确（`co_await`、`co_yield` 标记），优化友好，甚至能把协程帧的堆分配整个优化掉（heap allocation elision）。这契合 C++ 的零开销原则：不用的状态不保存，不需要的栈不分配。

无栈协程的本质是状态机：编译器把协程函数按挂起点切成若干段并编号，协程帧里记录"当前状态"，每次 resume 就跳到对应那一段继续执行。它不是真的暂停了调用栈，而是把函数拆成了状态的跳转。Go goroutine、Windows Fiber、Lua coroutine 走的是有栈路线；C++20、Rust 和 C# 的 `async`/`await` 走的是无栈路线。

## 只定机制，不定策略

C++20 的语言层只交付底层零件：`co_await`、`co_yield`、`co_return` 三个关键字，加上协程帧、promise_type、awaiter 等机制。成品交给库来组装——C++23 的 `std::generator` 是标准库第一个协程类型，C++26 的 `std::execution`（sender/receiver 框架与 `task`）再把异步补齐。

> 标准给你发动机、变速箱和轮子，组装成轿车还是卡车由库决定。

好处是极度灵活，可以根据场景定制协程行为；代价是上手门槛高——光有语言原语，连一个能用的生成器都得自己组装。下一节就来做这件事。

## 三个关键字与一个约定

| 关键字 | 作用 |
| ---- | ---- |
| `co_await` | 等待一个操作完成，协程挂起 |
| `co_yield` | 产出一个值，协程挂起 |
| `co_return` | 结束协程，返回最终结果 |

函数体里出现其中任何一个，它就不再是普通函数，而是协程。普通函数的调用是"调用 → 执行 → 返回"一次完成；协程函数被调用时只是创建协程并返回一个对象，执行到挂起点停下，之后由调用方多次恢复。

另一个硬性约定：协程的返回类型必须能提供一个嵌套的 `promise_type`，编译器通过它与协程交互。

## 手写一个最小 Generator

目标：写一个整数生成器，逐次产出 1、2、3。C++23 已有现成的 `std::generator`，但手写一遍才能搞懂里面发生了什么。

```cpp
Generator generate_numbers() {
    std::cout << "  [协程] 开始执行\n";
    co_yield 1;
    std::cout << "  [协程] 恢复执行，产出 2\n";
    co_yield 2;
    std::cout << "  [协程] 恢复执行，产出 3\n";
    co_yield 3;
    std::cout << "  [协程] 执行结束\n";
}

int main() {
    auto gen = generate_numbers();   // 创建协程，此时尚未执行
    while (gen.next()) {             // 恢复执行，直到下一个 co_yield
        std::cout << "产出值: " << gen.value() << "\n";
    }
}
```

运行时会先打印"创建协程"侧的日志，再看到 `[协程] 开始执行`——这证明调用 `generate_numbers()` 并不执行函数体。每次 `gen.next()` 协程恢复执行，遇到下一个 `co_yield` 就把值交出去并挂起；局部变量在多次挂起之间保持不变，因为它们被存进了协程帧。

完整实现如下：

```cpp
struct Generator {
    struct promise_type {
        int current_value = 0;

        Generator get_return_object() {
            return Generator{
                std::coroutine_handle<promise_type>::from_promise(*this)};
        }
        std::suspend_always initial_suspend() { return {}; }
        std::suspend_always final_suspend() noexcept { return {}; }
        std::suspend_always yield_value(int value) {
            current_value = value;
            return {};
        }
        void return_void() {}
        void unhandled_exception() { std::terminate(); }
    };

    std::coroutine_handle<promise_type> handle;

    explicit Generator(std::coroutine_handle<promise_type> h) : handle(h) {}
    ~Generator() { if (handle) handle.destroy(); }

    Generator(const Generator&) = delete;
    Generator& operator=(const Generator&) = delete;
    Generator(Generator&& other) noexcept : handle(other.handle) {
        other.handle = nullptr;
    }
    Generator& operator=(Generator&& other) noexcept {
        if (this != &other) {
            if (handle) handle.destroy();
            handle = other.handle;
            other.handle = nullptr;
        }
        return *this;
    }

    bool next() {
        handle.resume();
        return !handle.done();
    }
    int value() const { return handle.promise().current_value; }
};
```

### promise_type：编译器的契约

编译器在编译协程函数时，会自动插入对 `promise_type` 成员函数的调用：

| 时机 | 编译器调用的函数 |
| ---- | ---- |
| 协程创建时 | `get_return_object()` |
| 开始执行前 | `initial_suspend()` |
| 遇到 `co_yield v` | `yield_value(v)` |
| 遇到 `co_return` | `return_void()` 或 `return_value(v)` |
| 执行完毕后 | `final_suspend()` |
| 未捕获异常 | `unhandled_exception()` |

`initial_suspend` 返回 `suspend_always` 是"懒惰"生成器的常见做法（先挂起，等调用方恢复）；返回 `suspend_never` 则创建后立即执行到第一个挂起点，异步任务常用。`final_suspend` 返回 `suspend_always` 表示帧由调用方负责销毁；返回 `suspend_never` 则执行完自动销毁（fire and forget 场景，但注意它必须声明为 `noexcept`）。定制这个类型就能完全控制协程行为，这正是"只定机制、不定策略"的体现。

### coroutine_handle：非拥有的遥控器

`std::coroutine_handle` 就像一个原始指针，提供 `resume()`、`done()`、`destroy()`、`promise()` 四个基本操作。它不负责资源管理，所以 `Generator` 的析构函数里必须手动调用 `destroy()` 来释放协程帧。

### 协程帧：一切状态的家

promise 对象、挂起后仍需的局部变量、恢复点索引，都在同一块内存里——协程帧：

```
┌──────────────────────────────────┐
│ 协程帧 (coroutine frame)         │ ← handle 指向这里
│   promise_type 对象              │
│   局部变量（挂起后仍会用到的）    │
│   恢复点索引（状态机的当前状态）  │
└──────────────────────────────────┘
```

注意两点：`handle` 指向整个协程帧而非 promise 本身，模板参数让它知道 promise 在帧里的偏移；也只有"挂起后还会用到"的变量才会搬进帧，其余留在栈上、挂起前就销毁了——这就是无栈协程"按需保存"的来源。整个过程中协程始终在调用方的线程上执行，`resume()` 就是一次普通函数调用，没有线程切换，没有调度器。

## 代价在哪里

协程不是免费的午餐，C++20 的协程尤其如此：

- **标准库滞后**：C++20 只给机制不给成品，`std::generator` 要到 C++23，通用异步 `task` 要等 C++26 的 `std::execution`。在此之前，想写异步代码要么自己组装，要么依赖第三方库（Asio、cppcoro 等）
- **协程帧默认堆分配**：heap allocation elision 是编译器优化而非语言保证，性能敏感场景要确认分配真的被省掉了
- **生命周期陷阱**：`coroutine_handle` 是非拥有指针，`final_suspend` 返回 `suspend_never` 时帧自动销毁，此后再 resume 或访问 promise 都是未定义行为；把 handle 存到别处也要小心悬空
- **挂起点受限**：挂起只能发生在协程函数内部，深层的普通函数无法整体挂起——这是无栈路线为效率付出的灵活性代价
- **调试体验**：状态机展开后的调用栈与源码对不上

另外，协程的用武之地是 I/O 密集型任务——有等待才有恢复的价值。纯 CPU 密集型计算没有等待，协程帮不上忙。

## 一句话总结

协程的本质是"挂起—恢复"：任务中途暂停、保存状态，条件满足后从断点继续。C++20 用无栈方案把它做成了状态机，用 `promise_type` 把策略交给库，用协程帧把开销压到按需付费——灵活是极限的，门槛也是实打实的。

---

视频版：B站「谦信CPP」· 现代 C++ 之道 第七集
