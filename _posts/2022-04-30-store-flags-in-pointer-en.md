# An optimized method of using the lower three bits of a pointer to store additional information

In the case of 8-byte alignment, the lower three bits of the pointer are all 0. In some cases, we need to maintain additional information corresponding to the pointer, such as flag bits, but we don't want to create a structure for this purpose. In this case, we can use the lower three bits of the pointer to store additional information.

For example, if we want the type of the atomic operation to be 64-bit data, we can use the CMPXCHG machine instruction to implement the CAS operation. In other words, we want to define variables of the type `std::atomic<T *>` to implement atomic operations, rather than defining `std::atomic<S>`, where S is some structure. This is where the above technique can be applied.

The specific implementation is as follows:

std::uintptr_t is an unsigned integer type that can represent address values (pointer values are address values). Convert the pointer to std::uintptr_t and then perform bitwise operations. The following code is an example:

```cpp
#include <iostream>
#include <stdint.h>

struct Data
{
    // 定义一些数据成员
    long int a;
    long int b;
    long int c;
};

// 定义三个标志位，不用细究三个标志位的具体含义，这个在这里不重要。
static constexpr std::uintptr_t HAS_DATA = 1;
static constexpr std::uintptr_t NEED_DATA = 2;
static constexpr std::uintptr_t CLOSED = 4;
static constexpr std::uintptr_t FLAGS_MASK = HAS_DATA | NEED_DATA | CLOSED;
static constexpr std::uintptr_t PTR_MASK = ~FLAGS_MASK;

int main()
{
    Data * dp = new Data();
    dp->a = 88;
    dp->b = 99;
    dp->c = 77;

    std::cout << "指针值为 " << std::hex << reinterpret_cast<int64_t>(dp) << std::endl;
    // 在指针上附加上标志位
    std::uintptr_t ptr_int = reinterpret_cast<std::uintptr_t>(dp) | HAS_DATA;
    std::cout << "加过标记位后 " << std::hex << ptr_int << std::endl;

    // 取标志位
    std::uintptr_t flags = ptr_int & FLAGS_MASK;
    std::cout << "标记位 " << flags << std::endl;

    // 需要用指针的时候，清零低三位，恢复指针值原来的值
    dp = reinterpret_cast<Data*>(ptr_int & PTR_MASK);
    std::cout << "使用恢复后的指针" << std::dec << dp->a << ", " << dp->b << ", " << dp->c << std::endl;
    return 0;
}
```
