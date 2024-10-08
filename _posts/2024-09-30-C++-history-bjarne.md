# Thriving in a Crowded and Changing World: C++ 2006–2020 读后总结

C++在编程语言排行榜里基本上一直在前三，可以说是经久不衰。可能很多人没有意识到C++无处不在，因为大多数 C++ 程序是在基础层，藏在应用的背后，对用户来说是不可见的。C++通常不开发web 应用程序（Java、Ruby on Rails、PHP等在这个领域中更合适）。但是C++的经常出现在诸如开发操作系统、数据库、浏览器内核、JavaScript V8引擎、JVMs、搜索引擎、大数据基础设施、WebAssembly等领域中。C++之父Bjarne Stroustrup的这篇长论文《Thriving in a Crowded and Changing World: C++ 2006–2020》解释了C++经久不衰的原因，C++从11到23的发展以及经验教训。

这篇文章就是来总结这篇论文，把我认为其中的精华的部分抽取出来并解释其内在逻辑。



## C++的思想

C++在演进的过程中，有一些指导思想和原则是一以贯之的。这也保证了C++的演进过程中不会跑偏。



### C++聚焦的领域

为什么C++经久不衰？因为C++切入了一个细分市场，这个市场具有以下两个本质需求：

1. 需要充分发挥硬件性能；
2. 需要构建大规模的复杂软件。



具有这两个特性的市场包括但不限于：

1. 操作系统
2. 数据库管理系统
3. 游戏引擎与图形系统
4. 实时量化系统
5. 工业软件
6. 科学计算



### 语言设计的原则

因为C++有自己的聚焦，因此在语言设计上有自己的原则和优先级，例如C++没有像C#和Java那样使用垃圾回收器（GC）。在语言生态系统中，C++坚持了以下原则：

1. 直接映射硬件

   C++被设计成可以直接操作硬件（以及调用操作系统）。在语言生态中总是处于基础语言的地位。简而言之，在机器语言（汇编语言）和C++之间不需要第三种编程语言。它和硬件之间没有“中介”。

2. 零成本抽象

   抽象是指高层次的编程语言概念，例如函数、结构体、类、接口。这些是原本在机器语言（汇编语言）上不存在而在中高级语言中被创造出来旨在更好地构建程序的抽象概念。零成本抽象的一个意思是如果自己实现这样的抽象（例如在C语言中可以实现面向对象编程的），不会比C++提供的更快；另外一个意思是如果不用这些抽象概念，就不会有额外的开销。遵循零成本抽象的原则，才能让C++成为一门可以写出高性能程序的编程语言。

3. 为用户自定义类型提供与内置类型一样的支持的静态类型系统
   用户可以扩展语言中的类型，自定义的类型就像内置类型一样。

4. 多种编程范式
   采用实用主义，一切从实际出发，不会坚持一种编程范式或者一种编程思想。不会有“一切皆xx“这种论断，而是”合适的场景用合适的方法“。

5. 基于实际问题和反馈的演进
   贴近用户，且实事求是，不拘泥于某些理论。



### 重要语言特性

基于上述的思想和原则，C++的演进过程中形成了很多重要的语言特性，下面列举部分除了上述的“直接映射硬件”、“零成本抽象”等较大粒度的特性之外的其他重要且更具体的语言特性。



#### 面向对象编程

诞生之日起就有的特性，这里不多赘述了。重要一点是C++力求用户自定义类型（类）与内置类型拥有同等地位、同样的效率。



#### 泛型编程与模板元编程

C++的模板非常重要的特性，由模板产生了泛型编程，并且后来人们发现模板是图灵完备的，于是发展出了模板元编程。模板元编程让编译器在编译期计算类型以及复杂的算法，从而让程序运行更快。其他语言例如C#和Java有看起来像模板的泛型编程但是没有模板元编程的特性。STL是泛型编程和模板元编程的集大成者，可以从STL的源代码中学习很多这方面的知识。



#### 静态类型与资源安全

采用静态类型，这样既可以在编译期检查和优化，也保证静态类型安全，同时保证资源安全。在资源安全方面使用了RAII。RAII保证在程序不管正常退出还是异常退出的情况下都能保证释放资源。C++11引入的基于所有权的智能指针配合RAII，基本上杜绝了内存泄漏问题。以前“C++程序容易内存泄漏”的固有印象已经是过时的了。



#### 编译期计算

编译期计算是C++的一个重要而独特的特性，指的是计算在代码编译阶段进行，而不用在程序运行时进行。编译器计算主要是包括常量表达式求值、模板元编程、常量折叠、类型计算等。注意C++的编译期计算的机制是图灵完备的，因此可以实现很复杂的计算。这个独特的特点使得C++能实现高效的程序。



## C++委员会及运作模式

C++的演进过程与她的委员会和运作风格紧密相关。C++标准是ISO标准，制定C++标准的组织是ISO国际C++标准委员会，正式名称为ISO/IEC JTC1/SC22/WG21。

C++委员会不受某个公司的控制，而是拥有一个广泛的基础：包含了工业界的各大公司例如微软、谷歌，也包括了各个国家科研机构，还包括了一些大学。C++委员会是一个基础非常广泛的、民主的组织，它对于“达成一致”的标准非常高，通常投票赞同的比例要在80%以上才能算通过，就连C++之父的提案也经常被否定（他自己说的）。也因此C++的演进过程中也遇到了一些效率低效、方向不清等问题。但是谢天谢地这些问题都渐渐克服了，C++还是向前不断演进。

C++委员会和它的运转模式这可能是其基业长青的原因之一吧。

另外由于C++是没有被大公司控制的，是中立的，所以在信创规定的语言中，C++赫然入列。



## C++11-20的重要演进内容

从C++11开始，C++经历几次重大演进。其中C++ 11、C++ 20包含重大改变，而C++14、C++17是前一个版本的补充或者是因为某些原因成为一个“小改进”版本。



### C++ 11

C++11的制定经过了C++标准委员会十多年的讨论和实践（上个标准还是C++98），这使得C++11的改动非常巨大，简直看起来像是一门新的语言。包含如下重要演进：



#### 更好的并发支持

1. 内存访问模型
   适应于多核时代的内存访问模型。多核时代意味着：1. 多核；2. 核内与核外缓存；3. 指令重排；4. 推测执行，等等。
2. 线程与锁
   1. Thread
   2. Lock
   3. Mutex
   4. Conditional variable
   5. Thread local
3. Futures（有人翻译成期值，即期望之值）
   1. Future
   2. Promise
   3. Packaged task
   4. Async



#### 更高效

**右值与移动语义**

右值概念与移动语义，减少内存拷贝，这对于提升程序性能是很重要的。移动语义包含移动构造和移动赋值，主要思想是把对方对象的资源“拿”过来，对方对象失去此资源，自己得到对方对象的资源。具体的例子是容器，容器里的元素是资源，当给定一个已有容器去用移动语义构造一个新容器时，新容器获得已有容器的所有元素的所有权，不会发生内存拷贝，而已有容器会失去所有权，变成一个空容器。

多核时代，内存拷贝相对于CPU和缓存来说开销很大，减少了内存拷贝会很大程度提升程序的执行效率。



**noexcept**

引入了noexcept关键字来标注一个函数不会抛出异常（对于容器的移动语义的构造和赋值非常重要）。



**constexpr**

`constexpr`可以修饰变量和函数，包括构造函数，实现编译期计算，这是C++程序速度快的一个原因。沿着这个方向在后续的C++版本中还有进一步的演进。

```c++
struct LengthInKM {
	constexpr explicit LengthInKM ( double d) : val (d) { }
	constexpr double getValue () { return val ; }
private :
	double val ;
};
constexpr int x = 10 * 10 + 120 + foo(); // 编译时确定表达式的值
constexpr LengthInKM l{100.0f};
```

注意constexpr的修饰不是强制的，因此如果条件不足它可能不会编译期计算。



#### 更简单方便的使用

1. auto
   自动推导类型，不仅仅是减少了打字工作量，而且某些时候根本没法写出来类型的名字，尤其是在模板元编程中。

2. 范围for循环
   范围for循环形如`for(auto x : container) { ... }`。不仅仅是一个好用的语法糖，而且范围for循环减少了出错的几率。

3. nullptr

   指针专属null常量，不再跟其他类型的null值混淆在一起了。

4. 统一初始化
   减少了很多关于变量初始化的写法的争议。

5. 用户自定义字面值

6. Raw字符串
   Raw字符串中没有转义这回事了，这个特性其他语言例如Python和Ruby里都有。

7. 属性
   一种标注，指示编译器做一些行为，例如用[[likely]]标注某一个分支更容易被执行到，借此优化编译后的机器码的分支预测。

8. 元组
   便捷的方式创建复合类型，不需要手工定义结构体。



#### 更好的对泛型编程的支持

泛型编程（及其后代模板元编程 ）在 C++98 中取得了巨大的成功。C++11在此基础上做了提升，包括：

1. Lambda表达式
   跟很多其他支持lambda表达式的语言例如Python一样，C++通过Lambda表达式支持函数式编程范式，包括支持函数式编程的闭包。配合auto关键字，lambda表达式更好用。

2. 可变参数模板
   很灵活，某些情况下很有用，例如实现一个基于模板元编程的`printf`模板函数。

3. 模板类型别名
   `template < typename T , typename A > class MyVector { /* ... */};` 
   `template < typename T > using Vec =  MyVector <T , MyAlloc <T > >;`

4. 减少对SFINAE的依赖

   标准库中引入enable_if、类型萃取（例如is_copy_assignable， is_nothrow_constructible）等工具，减少晦涩难懂的SFINAE。



#### 更好的静态类型安全

C++11总体上提升了静态类型安全，比如上面的关于对并发编程的支持中，引入了线程对象（`std::thread`以及相关内容）封装操作系统中的线程。再比如范围for循环语法帮助减少类型相关错误。更多的关于类型安全的提升列觉如下：

1. 基于资源所有权管理的智能指针

   原先C++98的auto_ptr被替换成了更全面的shared_ptr与unique_ptr，分别对应所有权共享和专有两种使用场景，这是更好的智能指针。配合`make_shared`和`make_unique`，基本上可以杜绝裸指针带来的内存泄漏、悬空指针等过去常发生的问题。

2. enum class

   解决C语言中enum的一些问题，包括跟整型数混用、枚举名不带类型前缀。这是更好的枚举类型。

3. std::array

   解决C语言中的数组的一些问题，包括形参退化、无法判断越界等问题。这是更好的数组。



#### 更强大的标准库

除了上述介绍的新的并发支持的标准库组件，C++11还引入了regex、chrono、random组件，以及基于哈希表的关联容器（C++98的关联容器只有一种基于红黑树的，C++11增加了基于哈希表的关联容器，以unordered_开头）。

更多信息通过查阅[cppreference.com](https://en.cppreference.com/w/)了解更多。



### C++14

C++14是C++11的一个补充。这个版本是一些小修小补，包含：

1. 二进制的字面量
   例如：0b1001000011110011
   
2. 数字分隔符，以提高可读性
   例如：0b1001’0000’1111’0011
   
3. 模板常量和变量
   例如：`template < typename T > constexpr T pi = T (3.1415926535897932385);`

4. 函数返回类型推断

5. 泛型lambdas表达式

6. constexpr函数中可以使用局部变量

7. Lambda的捕获列表可以使用移动语义
   例如：auto f = [p = move(ptr)] { /* ... */ };

8. 按类型访问元组

   例如：`x = get<int>(t);`

9. 标准库内新增字面量定义

   例如：`10i, "Hello!"s, 10s, 3ms, 55us, 17ns`



### C++ 17

C++17原本是要作为一个大版本的，因为C++14是小版本，C++委员会希望“大版本->小版本->大版本”这样交替出现。但是因为缺乏整体规划，一些重要的演进因为过于重要而引发更多的讨论和争论，最终被耽搁没有进入C++17；而一些小的细碎的“聪明的”想法由于本身体量小争议小，纷纷进入C++17。这样让C++17看起来是一个语言优化想法的“大杂烩”，毫无章法。在Bjarne看来，这是“大海迷航”，之后，C++标准委员会成立了方向小组，以纠正这个问题。



#### 语言特性

不管怎样，C++17还是引入了一些很有用的点点滴滴语言特性方面的改进。下面一一列出：

1. 构造函数模板参数推导
   允许写出`shared_lock lock{m};`这样的代码。shared_lock是模板但是可以省略模板类型参数，而由构造函数的参数`m`的类型推导得出。这是模板函数的类型推导的延展。

2. 结构化绑定

   原先需要先定义变量，例如`T1 x; T2 y; T3 z;`，然后用`tie(x,y,z) = f()`承接函数`f()`返回结果。现在只需要`auto [x,y,z]=f()`即可。非常甜的语法糖。但是注意结构化绑定并不是定义了x、y、z三个变量，这三个是“绑定”，所以x、y、z无法直接放在lambda的捕获列表中，这个问题直到C++20才解决。

3. 变参模板折叠表达式
   简化变参模板的用法，非常“炫技”，也确实能提升效率。这里仅举个例子：变参模板函数 `template  auto foo(TArgs ... args) { return (... + args); }` 可以实例化出一个接受任意数量参数并求和的 `foo` 函数。

4. 条件中显式测试
   语法糖，相当于把for循环定义中的第三个部份拿掉。

5. 模板值参数可用auto

   是auto的用法的扩展，即可以写出 `template <auto a=10> int foo() { return a + 10;} `这样的模板而不用指定模板值参数的类型。

6. 新属性有助于在编译期进行静态检查。

   编译器在编译期间对程序做静态检查，例如有变量未使用，编译器可以设置为对这些问题报错。新增的属性[[maybe_unused]]、[[nodiscard]]、[[fallthrough]]指导编译器做更精准的静态检查。

7. 常量表达式if

   用法为`if constexpr (<condition>) { ... } else { ... }` 非常好用的编译期计算特性，生成出不同的分支的代码。



#### 标准库

相对于单纯的语言特性，C++17中对于标准库的改进相对比较显著，特别是对并行算法的支持。以下是详细内容：

1. optional、variant和any
   填补了空白。

2. 避免死锁

   `scoped_lock`保证“要么全锁多个互斥量（mutex），要么全不锁”。消除了一个死锁的源头。

3. 支持读写锁

   `shared_mutex`、`shared_lock`、`unique_lock`三者实现了读写锁，填补了空白。

4. 并行STL算法

   STL的算法诸如`sort`可以指定并行和向量化版本，非常契合多核时代。

5. 文件系统

   无需赘述，早该有了。

6. string_view

   `string_view`只包含字符串的位置和长度的两个成员，是字符串的引用（string reference），没有字符串的“拥有权”。使用得当可以减少内存拷贝和内存消耗，优化性能。

7. 数学特殊函数
   一些很酷的数学函数。



#### 其他细碎

就像Bjarne所说的“大海迷航”一样，C++17包含了很多细碎的点，这里就不多赘述了，仅列举部份：

1. inline变量
2. 去除不必要的拷贝
3. 更严格的表达式求值顺序
4. 16进制浮点数字面量



### C++ 20

C++20引入了一些重要的特性：概念（concept）、协程（coroutine）、模块（modules）、范围（ranges），每一个都有重大影响。这个版本是一个“大”的演进。

#### 概念（concept）

概念滥觞于1980年代，那时候C++才刚刚出生不久。概念进入C++的标准的过程有些波折，原本预计会在C++11里，但是最终出现在C++20中。

概念与类不同，不像类层次那样有一个明显的继承关系。概念在模板元编程中用于限定模板类型参数。它描述的是一些行为，凡是满足这些规定行为的类型都满足此概念，没有继承概念。

这篇论文里花了很长的篇幅叙述了概念这一重要特性在C++11、C++14、C++17难产的过程，其中分为两派并发生激烈争论。期间发生了很多故事，例如有一次差点就在投票中达到了法定要求（C++委员会的投票要求很高，不是过半即可，而是80%以上赞成票才能算通过），由于某人提出一个问题而闯关失败。最终经过十多年的长跑，终于概念进入了C++标准里。

概念通过如下语法定义一个模版类型参数应该有的行为。

```c++
// 定义Sortable concept，要求类型T支持<, >, <=, >=运算符
template <typename T>
concept Sortable = requires(T a, T b) {
    { a < b } -> std::convertible_to<bool>;   // 必须支持 a < b，且返回值可以转换为 bool
    { a > b } -> std::convertible_to<bool>;   // 必须支持 a > b
    { a <= b } -> std::convertible_to<bool>;  // 必须支持 a <= b
    { a >= b } -> std::convertible_to<bool>;  // 必须支持 a >= b
};
```

然后在模板中使用概念限制模板类型参数。

```c++
// 定义一个排序函数，要求参数类型满足Sortable
template <Sortable T>
void sort(T* array, size_t size) {
    std::sort(array, array + size);
}
```

考虑到C#在2007年左右就有了限定泛型参数的语法，C++20才引入概念确实有点晚了。

引入概念的同时，标准库里增加了很多定义好的概念，并且范围（ranges）大量地定义和使用了概念，如果没有概念， 范围这一重大特性也会难产。

列举几个标准库里的概念：

1. `std::same_as<T, U>`
2. `std::convertible_to<From, To>`
3. `std::integral<T>`
4. `std::assignable_from<T, U>`
5. `std::move_constructible<T>`

例如我要写一个模板函数，接收模板类型参数T。如果我希望限制T类型必须有移动构造函数，那么我可以写成：

```c++
template <std::move_constructible T>
void foo(T arg) {
    ...
}
```

使用概念约束模板参数，能够得到清晰的错误提示，而不会像以前那样在模板推演的过程中报出一大堆乱七八糟难以理解的错误。



#### 模块（modules）

以往C++是通过把其他源代码作为文本包含在当前源代码文件中来实现代码复用的。`#include "a.h"`相当于把a.h文件的源代码复制进来。一直以来这样做有一些问题，列举一些：

1. `#include`的顺序是有关系的。
2. `#include`之间会互相影响，例如a.h文件中定义了一个宏会影响到b.h文件的代码。
3. 编译效率低下，C++编译之慢想必大家深有体会。因为：
   1. 哪怕用到其他头文件的某个小函数，也要include整个头文件并编译其源代码。
   2. include了某个文件A，哪怕不用文件A里面的任何内容，也会给编译的工作带来负担。

模块就是解决这些问题的。导入模块不是导入源代码而是导入编译好的结果。模块保证了：

1. 导入模块的顺序是无关的，即导入A和B等价于导入B和A。
2. 导入的多个模块之间互相无影响。
3. 导入的模块如果未使用，不会影响编译效率，就像“没有导入这个模块”一样。
4. 导入的模块如果未使用，对程序也没有任何开销，导入动作只使模块内的暴露出来的内容可访问而已。

基于以上的模块的特性，我们不用一个个`#include`各种C++标准库头文件了，而是可以导入一个std模块，减少了很多心智负担。



#### 协程（coroutine）

C++很早就有了协程，但是一直没有进入标准中。在C++20标准中协程终于进来了。

在异步编程场景中，协程是一个好东西。协程可以让一个函数挂起，然后去执行其他代码，在某个时间点中再恢复执行。C++20的协程是无栈协程（stackless coroutine）。无栈协程是一种只能挂起在自己的代码主体中，而不能挂起在由其调用的函数中的协程。这样一来，挂起只涉及保存单个堆栈帧（即协程状态），而不涉及保存整个堆栈。就性能而言，这是一个巨大的优势。

在C++的协程中以下关键字被引入：

1. co_await
2. co_yield
3. co_return

引入下划线是为了防止以英语为母语的人将 coreturn、coyield 和 coawait 误读为 core-turn、coy-ield 和 coa-wait。

协程的关键场景： 

1. 管道（pipelines）
2. 生成器（generators）



#### 范围（ranges）

替代原先的begin，end迭代器。

支持管道运算符，对一个数据源定义一系列的运算，就像管道一样连接起来。例如：`data_src | filter(...) | transform(...) | take(n)`，意味着对data_src先进行过滤（过滤条件这里省略掉了），再进行变换（变换算法这里也省略了），最后取前n个值。由于ranges这套编程范式是懒求值（lazy evaluation），所以实际上不会把data_src的所有的数据都经过一遍过滤和变换，而是计算去前n个（因为take规定了只输出前n个）。这种范式如果使用得当能够很好地避免无用的计算。



#### 进一步支持编译期计算

增加了`consteval`（与`constexpr`类似，但标注函数强制一定进行编译期求值），`constinit`（强制编译期初始化）。

同时增强了`constexpr`，允许`constexpr string`和`constexpr vector`，这意味着编译期可以构建复杂的类型（反映了用户自定义类型与内置类型同等地位这一原则）。并且给予constexpr标注的函数更多的能力，例如使用new和delete，这意味着编译期运算时可以使用自由内存。



#### 多线程编程补充

通过标准库里新增`jthread`和`stop_token`提供方便的可停止的线程的范式。用法是创建jthread的时候传入stop_token，jthread可以保证释放时自动等待线程结束，相当于自动调用的`.join()`，这也是为什么jthread用J字母打头的原因。

`stop_token`是用来作为主线程通知子线程“停止”的工具。子线程需要在运行中不断检查stop_token然后优雅退出。



#### 中等特性

剩下的就是一些相对没那么大的语言特性，但也是有些份量值得关注的。

1. 三路比较运算符<=>（可以替代原先小于、等于、大于三个运算符），因为长的像飞碟也称飞碟运算符。
2. 日期库chrono
3. Span
   轻量级的不拥有所有权的容器。
4. Format库
   提供类型安全的类似C语言的printf的函数。



#### 其他小特性

还有一些小特性，可能会自然而然用到，不需要太过关注，列举如下：

1. C99 样式的指定初始值设定项
2. 对 lambda 捕获的改进
3. 通用 lambda 的模板参数列表
4. 在范围 for 内初始化附加变量
5. 未计算上下文中的 lambda 捕获中的包扩展
6. 在某些情况下不再需要 typename
7. 属性 [[likely]] 和 [[unlikely]] 去影响分支预测
8. source_location提供源代码不使用宏的一段代码的位置
9. 语言特性测试宏
10. 带条件的explicit
11. 有符号整数保证是二进制补码
12. 数学常数，例如 pi 和 sqrt2
13. 位运算，例如旋转和计数



### 不远的未来

在未来的C++23、26中，有一些很重要的语言特性在酝酿之中。比如静态反射、契约（断言、前置条件、后置条件）、网络库和执行器。下面一一介绍。



#### 静态反射

Java和C#在很早就有反射这一重要特性，而且基于反射衍生出很多东西，例如面向切片编程。C++没有反射，因为要保证零成本抽象，但有框架例如Qt提供了静态的类似于反射的机制。在未来版本中静态反射会作为C++一个新的有用的语言特性，拭目以待。



#### 契约

契约包含断言、前置条件、后置条件，这些用assert也可以实现。为什么要加入语言标准呢？一个原因是可以帮助编译器进行静态检查和优化。



#### 网络库和执行器

这两个为什么要放在一起？因为要进入C++标准的网络库是基于asio（一个使用多年的网络库）制定的。网络库一定离不开并发和异步，而执行器就是关于并发和异步的。所以这两者应该是紧密结合的，在未来会一起进入C++标准。



## 关于异常处理的讨论

在这篇论文中单独讨论了异常处理，因为异常处理的争论由来已久，而且贯穿于C++的演进历史中。基本上分为两派：1. 异常（exception）派；2. 错误码派。中间还有一个“异常规范”（exception specification）小插曲。除此之外还有关于异常发生时的资源释放和清理的问题的讨论。



### 异常机制和错误码

异常机制（throw、try...catch...）和错误码都是服务于一个场景：当一个程序在此时此地无法妥善处理一个问题时，需要通知她的“上级”去处理。在异常还是错误码的争论中，关于异常，大家关注的是几个实际的问题：

1. 在内存空间有限的环境中，如何让异常处理机制不占用过多内存？
2. 对于实时性要求很高的系统，如何让异常处理机制保证响应时间？
3. 对于有些不稳定的系统，是否让程序直接挂掉重启比抛出异常处理更加合适？

实际上错误码是最早的处理错误的方式，早于异常处理机制，但是它有一些问题：

1. 构造函数和操作符函数无法返回错误码（实际上还是可以通过第三方变量传递的，太麻烦）。
2. 调用方可能会忘了检查和处理返回的错误码。
3. 调用非C++代码时，可能错误码是唯一的传递方式。
4. 在调用深处新增一个错误码，会导致上层调用函数都得被修改以正确处理这个新错误码，导致代码维护困难。
5. 需要管理错误码体系，以及调用方要知道所有的错误码。

Bjarne认为异常机制配合RAII可以很好的解决问题，一些诸如异常慢、异常会导致内存泄漏的观点都是误解。以往有些研究认为异常处理比错误码处理慢，但是经过科学的实验，异常机制并不比要达到同样效果的



### 曾经的异常规范（exception specification）

异常规范在C++11及以后的版本中已经没了。异常规范跟以前的Java的很像，就是用` throw(Type1, Type2, ...)` 的形式规定函数会抛出的异常，调用者必须处理这些异常。异常规范是在C++98中引入，但实践下来发现这种方式有诸多问题，于是在C++11中被废弃了。但是标注一个函数是否会抛异常的特性在很多地方很有用，例如容器类的在调整容量的时候会移动资源，在这种场景下容器类应该优先调用元素对象的移动构造函数，因为这样效率最高。但是如果移动构造函数抛了异常，那么在容器类无法恢复原先状态，因为移动构造函数会破坏原来的元素对象的状态。有了`noexcept`，元素类的移动构造可以被标注为`noexcept`从而向编译器保证自己不会抛异常。这样容器类可以放心大胆地调用其移动构造了。



### 资源释放的保证

不管是用异常还是错误码，资源不能泄漏，该释放的资源必须释放！关于异常发生时的资源释放问题，Java和C#常用try...catch..finally的范式去处理异常，并把不管是否发生异常都要进行的资源的释放和清理工作放在fanally代码块中。在保证资源释放和清理工作总是完成这一点上，C++采用另外一种做法，即RAII。RAII对象在离开作用域的时候一定会调用析构函数，而在析构函数中可以释放和清理RAII对象负责的资源（RAII对象的成员变量里会记录资源的相关信息）。RAII的这种方法非常巧妙。



## 发展过程中的经验教训

C++的发展历程中有些经验教训，总结下来是以下几点：

1. 只为专家，专家容易把事情搞得很复杂。
2. 一味模仿，别的语言有所以自己也要有。
3. 片面强调理论。
4. 过于激进，不顾兼容性。

概括下来，就是要避免毫无原则的实用主义或者教条的理想主义。

Bjarne Stroustrup在另一篇论文《Remember the Vasa！》（记住瓦萨号）中给出了更多的关于经验教训的讨论。瓦萨号是一艘17世纪的瑞典战舰，以其精美的雕刻和强大的火力而著称。然而，由于设计上的失误和国王的过度要求，这艘战舰在1628年首航时不幸沉没。

这篇论文总结了C++发展过程中积累的成功经验：

> 以实际问题驱动，力求简单、高效、易用，保持基本C++的设计原则（例如零开销原则），同时保障兼容性（尊重历史传承）。

中心思想就是“实事求是”，“实践检验真理”。



## 我的思考

很多道理是相通的。

商科领域中有关于市场经济的理论，市场经济中有一个重要的关系是供需关系。商科中也有关于商业定位的要素，包括：目标市场、价值主张、差异化、品牌个性、渠道与推广、反馈且调整。如果把C++看成一个产品，无疑是成功的。套用前面所说的商业定位的要素，C++具有以下定位：

1. 目标市场
   开发能够充分利用硬件资源、具有高性能的大规模软件的需求。

2. 价值主张
   直接映射硬件、直接调用操作系统、零成本抽象、编译期计算、多种编程范式、模块化及可扩展性、丰富的标准库、兼容过去积累的代码库等开发成果、强大的社区支持、跨平台性、强大的开发与构建工具支持。
   另外，C++是一个不受大公司控制的语言（换句话来说可能获得大公司的支持也比较少）。

3. 差异化（竞争对手分析）
   这里不做过多讨论，读者可以比较C++与Java、C#、Python、JavaScript等语言的差异。我个人认为Golang和Rust可能跟C++重合度比较高一些。

4. 品牌个性
   很早以前C++给人的印象可能是：高级（换句话说是难学难用且强大，一定程度上归功于“出神入化”的模板编程技巧例如SFINAE）、执行效率高且开发效率低、风险高（内存及资源泄漏、缓冲区溢出攻击、容易崩溃）。
   但是经过C++11及以后版本的改进中，以上印象中负面的部份已经得到纠正。用“现代C++”这个品牌与原先的“老C++”做切割。事实上，C++的演进路线正是：保持强大的同时，尽量保证使用简单，加入concept、constexpr等特性来替代原先的模板编程技巧，并尽量遵循洋葱原则即可深可浅；丰富标准库的内容，在保证零开销抽象的前提下，提供诸如并行编程等轮子以支持”以简单方法实现复杂功能“；保证直接映射硬件的前提下，采用RAII来保证内存及资源泄漏不会发生（简单来说，只要按照现代C++的方式管理内存及资源，基本上不会发生泄漏，new和delete关键字基本上不应在程序中使用）。

   C++的另外一个形象是：开放、独立、社区推动的可以被信赖的语言。

5. 反馈与调整

   这点至关重要，C++之父在文章中不止一次提到这一点。

一些哲学范畴中的优秀思想，如“知行合一”、“实事求是”、“具体问题具体分析”、“兼容并包”、“以人为本”、“少即是多”和“可持续发展”，在C++的发展演进中同样得到了体现。C++的发展原则强调不拘泥于理论、不盲目模仿，包容多种编程范式，始终以解决具体问题为导向。C++致力于简化使用体验，而非向仅供专家使用的复杂语言发展。此外，C++重视用户反馈，积极倾听并根据建议进行调整。一个重要原则是，C++确保传承过去的成果，始终遵循“不要搞砸我的历史代码”的理念。

所以，很多好的思想是相似的，只是可能表述方式不同。这些好的思想可以用在很多方面，人要学会融会贯通。

目前C++相对缺乏的是配套支持，例如教育资源和开发工具等，这一点在C++之父的本篇论文中也有提到。此外，模块化和标准库在网络编程（尤其是异步编程）以及统一执行器方面的支持也应尽快得到完善。这些领域的进步将进一步提升C++的易用性和功能性，使其更好地适应现代开发需求。