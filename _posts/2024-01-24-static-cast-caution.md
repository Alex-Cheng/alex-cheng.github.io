# static_cast caution
It is likely to lead unexpected behavior and maybe dangerous to invoke `static_cast` on wrong C++ object. Below example demostrates it.

On the second invocation of `foo`, `foo(d2)`, the instance of class `D2` is casted into instance of class `D1` and the memory address for access to member variable `b` of `D1` is calculated as d2's address + offset of `b`. The resulted address is actually out of the available memory of instance `d2` because `d2` is instance of class `D2` which is smaller than class `D1`(D1 has a big member variable `arr`). That causeses unexpected behavior: if the memory which the address points is already allocated to the current process, the wrong data(the memory is occupied by another objects or values) are read; otherwise a "memory access violation" exception occurs.

```C++
#include <iostream>
#include <array>

using namespace std;

class Base
{
public:
    virtual void say()
    {
        cout << "hello, base;" << endl;
    }
};

class D1 : public Base
{
public:
    char a = '*';
    std::array<char, 10000> arr{};
    char b = '+';

public:
    void say() override
    {
        cout << "hello, D1;" << a << endl;
    }

    void jump()
    {
        cout << "jump " << b << endl;
    }
};

class D2 : public Base
{
public:
    long long v = 7777;

public:
    void say() override
    {
        cout << "hello, D2;" << v << endl;
    }
};

void foo(Base & bb);

int main()
{
    D1 d1;
    D2 d2;
    foo(d1);
    foo(d2); // cause memory access violation!!!
}

void foo(Base& bb)
{
    D1& d = static_cast<D1&>(bb);
    d.jump();
}
```

In my experiment, the "memory access violation" exception happens.
<img width="851" alt="image" src="https://github.com/Alex-Cheng/alex-cheng.github.io/assets/1518453/7123bf97-4948-4cf5-866a-a271fe3cfd94">


