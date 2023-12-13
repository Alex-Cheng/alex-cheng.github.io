# Linux性能调优技术概览



## 概述

这里的Linux性能调优主要是关于Linux系统上程序的性能跟踪，因为只有收集到足够的准确的性能数据才能找到程序和系统的性能瓶颈。Linux性能调优的原理、框架、工具等内容包括三个方面：

1. 信息源
   通常是以“事件”的形式，也称为“事件源”。

2. 对接信息源的追踪框架

   从信息源中收集数据，隐藏相关的复杂性，对外提供使用接口（通常是编程接口）。

3. 前端操作界面

   用户操作界面工具（通常是命令行形式），让普通用户可以方便使用。



下图是性能监控体系：

![性能监测体系](/assets/image-20231114192048746.png)

性能调优所关心的问题大致分为三类：

1. CPU利用率和瓶颈
2. 内存利用和瓶颈
3. I/O情况（文件、磁盘、网络等）

这些信息可以通过监听不同类型的“事件”来获得，结合上下文信息，获得关于性能优化的洞察。



## 信息源（事件源）

由于性能主要以事件形式呈现，所以信息源也被称之为“事件源”。信息源主要分为硬件事件、静态探针（需要重新编译内核）和动态探针（不需要重新编译）。



### 硬件事件（CPU支持）

通常由性能监控计数器（PMCs）实现。性能监控计数器（PMCs）是处理器上的可编程硬件计数器，用于测量处理器中发生的事件。这些计数器可以记录各种硬件性能情况，如CPU的缓存、指令周期、分支预测等。由于PMCs是CPU自带的功能，因此能得到最底层的、用别的手段得不到的性能信息，例如只有通过PMC才能测量CPU指令执行的效率、CPU缓存命中率、内存/数据互联和设备总线的利用率，以及阻塞的指令周期等。

PMCs可以帮助查找应用程序中的瓶颈。例如，大量的条件分支指令可能表示一段逻辑，如果重新排列，可能会降低所需的分支数量。因此，PMCs在性能测试和优化中起着关键作用。PMCs可以支持的有（包含但不全是）：

- 追踪CPU缓存
- 追踪指令周期
- 追踪分支预测等硬件性能情况

请注意，不同的处理器和硬件平台可能具有不同的PMCs和相应的编程接口。因此，在使用PMCs时，需要参考特定的硬件和操作系统的文档以获取详细的信息和指导。例如Intel的芯片的性能监控计数器（在Intel这里称之为 PMU）的介绍  [Intel x86_64 PMU简介_小立爱学习的博客-CSDN博客](https://xiaolizai.blog.csdn.net/article/details/124238596?spm=1001.2101.3001.6650.1&utm_medium=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1)



### 静态探针

静态探针，是指事先在代码中定义好，并编译到应用程序或者内核中的探针，即“代码中埋点”。

#### Linux内核跟踪点（tracepoints）

Linux内核跟踪点就是linux内核源代码中预先定义的跟踪点（tracepoints）。Linux内核事件在代码中以函数的形式定义，并在需要的时候调用该函数以触发事件。以下是作为例子的代码碎片：

```c++

// 定义用于定义trace event函数的宏
#define DEFINE_EVENT(evt_class, name, proto, ...) \
static inline void trace_ ## name(proto) {}

// 以netif_receive_skb为例，定义相应的trace event函数
DEFINE_EVENT(net_dev_template, netif_receive_skb,

  TP_PROTO(struct sk_buff *skb),

  TP_ARGS(skb)

);// 

// 
int netif_receive_skb(struct sk_buff *skb)

{

  trace_netif_receive_skb_entry(skb); // 调用netif_receive_skb对应的trace event函数

  return netif_receive_skb_internal(skb);

}
```



通过`cat /sys/kernel/debug/tracing/available_events`显示内核代码中定义的事件，在作者当前环境中，有1565个定义的内核事件。

注：`/sys/kernel/debug/tracing/`目录下还有很多其他内容。



#### USDT探针 

USDT探针（User Statically-Defined Tracing）全称是用户级静态定义跟踪，需要在源码中插入 DTRACE_PROBE() 代码，并编译到应用程序中。这里不做详述。



### 动态探针

顾名思义，则是指没有事先在代码中定义，但却可以在运行时动态添加的探针（重点是不需要重新编译目标程序）。主要由kprobe（内核探针）和uprobe（用户态探针）组成。



#### 内核探针kprobes

kprobes(Kernel Dynamic Probes)主要用来对内核进行调试追踪, 属于比较轻量级的机制, 本质上是在指定的探测点(比如函数的某行, 函数的入口地址和出口地址, 或者内核的指定地址处)插入一组处理程序. 内核执行到这组处理程序的时候就可以获取到当前正在执行的上下文信息, 比如当前的函数名, 函数处理的参数以及函数的返回值, 也可以获取到寄存器甚至全局数据结构的信息。

kprobes机制可以实现三个类型的探测点：

- kprobe  可以被插入到内核的任何指令位置的探测点
- jprobe  内核函数入口的探测点
- kretprobe  内核函数返回处的探测点

在内核性能监控中，使用动态探针可以：

1. 调试时内核正常运行
2. 无需修改或者编译内核
3. 可随时启用和关闭

这些特性非常好用。适用的场景有：

- 检查某个内核函数是否被调用到
- 查看内核函数的耗时
- 注入bug修复代码相当于内核补丁



#### 用户态探针uprobes

uprobes (User Dynamic Probes)用来跟踪用户态的函数，包括用于函数调用的 uprobe 和用于函数返回的 uretprobe。



## 追踪框架  Tracing Framework

### ftrace

ftrace内置在Linux内核中，可以使用Linux内核跟踪点、kprobes和uprobs，并提供了一些功能：具有可选的过滤器和参数的事件跟踪；事件计数和计时，并在内核中数据汇总计算；以及函数执行流跟踪。请参见内核源代码中的ftrace.txt得到详细事例。

ftrace的一个最强大的跟踪器是用于跟踪函数执行流的function tracer。原理是在编译器中加入选项让编译器为每个函数中插入一个对特殊函数“mcount()”做调用操作的代码。在不启用function tracer时，这些代码会被替换成“NOP”（NOP是啥都不做的机器指令）；而在启用function tracer时则将“NOP”替换成对“mcount()”调用的代码。

ftrace不是内核态可编程的。

### perf_event

perf_events是Linux用户的主要跟踪工具，它的源代码在Linux内核中，通常通过Linux工具通用包添加。对应的命令行工具是“perf”。它可以做大部分“ftrace”可以做的事情。而且黑客攻击性也更少一些（因为它有更好的安全/错误检查）。

perf_events的一大特点是可以进行采样（性能数据采集主要就是探针和采样两种方法），并可以进行用户级的堆栈转换。

与ftrace一样，它不是内核态可编程的。

尽管如此，perf_event可以做很多事情，而且相对安全，推荐使用。

#### 采样（sampling）的工作原理

每隔一个固定时间（取决于采样率），看当前是哪个进程、哪个函数，然后给对应的进程和函数加一个统计值，这样就知道CPU有多少时间在某个进程或某个函数上了。



#### 可消费事件源

- 硬件事件，tracepoint， kprobes， uprobes等。
- 支持自定义动态事件
- 支持采样 



### eBPF

BPF，全称Berkeley Packet Filter，最初是一种优化包过滤器的技术。eBPF全称是Extended Berkerley Packet Filter，扩展了BPF功能，可以做除了包过滤之外的其他事情，比如内核事件追踪。

特点：

- 一个内核沙盒，可在events上安全高效地运行program

- 支持常用事件追踪，包括kprobe，uprobe，perf_event

- 在Linux上执行自定义分析程序来处理事件，包括dynamic tracing、static tracing、 profiling events



### SystemTap

号称最强大的追踪程序（但也可能最难用），通过自己写脚本，由stap编译为**驱动**并插入内核，几乎可以做任何事情，当然不太安全。

支持3.x等旧版本内核

以驱动的方式插入内核，几乎可以无所不做。



### sysdig

功能全面、强大，统一的语法

Sysdig 是一个超级系统工具，相较于 strace，它具有以下优势：

1. 功能强大：Sysdig 比 strace、tcpdump、lsof 等工具加起来还强大，可以捕获系统状态信息，保存数据并进行过滤和分析。
   sysdig = strace + tcpdump + htop + iftop + Lsof + docker inspect
2. 使用 Lua 开发：Sysdig 使用 Lua 编程语言开发，提供了灵活的脚本支持，用户可以根据自己的需求进行自定义脚本的编写，扩展其功能。
3. 命令行接口和交互界面：Sysdig 提供了命令行接口以及强大的交互界面，用户可以方便地使用命令行进行操作，也可以通过交互界面进行更直观的操作和监控。

因此，选择 Sysdig 可以获得更强大和灵活的系统监控和分析能力。



适用于：

- 主要用于容器（特别是k8s）的动态追踪
- 使用类似tcpdump的语法和lua后处理操作系统调用事件；
- 还可以通过eBPF来进行扩展。也可以用来追踪内核中的各种函数和事件。



### 其他

还有一些其他的追踪框架，这里仅仅列举一下：

1. LTTng
2. ktap
3. dtrace4linux
4. Oracle Linux DTrace
5. DTrace



## 前端工具

前端工具是命令行或者图形界面工具，是用户使用各种追踪框架功能的入口。

### ftrace - 文件系统

ftrace - 文件系统在`/sys/kernel/debug/tracing` 位置上构建一个文件系统，用户通过读写文件的方式来使用ftrace。

Unix的“一切皆文件”的哲学在这里体现的淋漓尽致。

```bash
#1、进入debugfs目录
$ cd /sys/kernel/debug/tracing
#如果找不到目录，执行下列命令挂载debugfs：
$ mount -t debugfs nodev /sys/kernel/debug

#2、查询支持的追踪器
$ cat available_tracers
#常用的有两种：
#
#- function 表示跟踪函数的执行；
#- function_graph 则是跟踪函数的调用关系；

#3、查看支持追踪的内核函数和事件。其中函数就是内核中的函数名，而事件，则是内核源码中预先定义的跟踪点。
#//查看内核函数
$ cat available_filter_functions
#//查看事件
$ cat available_events

#4、设置追踪函数：
$ echo do_sys_open > set_graph_function

#5、设置追踪器
$ echo function*graph > current_tracer
$ echo funcgraph-proc > trace_options

#6、开启追踪
$ echo 1 > tracing_on

#7、执行一个 ls 命令后，再关闭跟踪
$ ls
$ echo 0 > tracing_on

#8、最后一步，查看跟踪结果
$ cat trace
```



### perf工具

perf工具非常强大，如果用的好基本上可以完全满足应用程序的性能分析和调优工作的需求。

执行`sudo perf help`命令得到perf的使用说明。perf工具包含若干子命令，列举如下：

```bash
 usage: perf [--version] [--help] [OPTIONS] COMMAND [ARGS]

 The most commonly used perf commands are:
   annotate        Read perf.data (created by perf record) and display annotated code
   archive         Create archive with object files with build-ids found in perf.data file
   bench           General framework for benchmark suites
   buildid-cache   Manage build-id cache.
   buildid-list    List the buildids in a perf.data file
   c2c             Shared Data C2C/HITM Analyzer.
   config          Get and set variables in a configuration file.
   data            Data file related processing
   diff            Read perf.data files and display the differential profile
   evlist          List the event names in a perf.data file
   ftrace          simple wrapper for kernel's ftrace functionality
   inject          Filter to augment the events stream with additional information
   kallsyms        Searches running kernel for symbols
   kmem            Tool to trace/measure kernel memory properties
   kvm             Tool to trace/measure kvm guest os
   list            List all symbolic event types
   lock            Analyze lock events
   mem             Profile memory accesses
   record          Run a command and record its profile into perf.data
   report          Read perf.data (created by perf record) and display the profile
   sched           Tool to trace/measure scheduler properties (latencies)
   script          Read perf.data (created by perf record) and display trace output
   stat            Run a command and gather performance counter statistics
   test            Runs sanity tests.
   timechart       Tool to visualize total system behavior during a workload
   top             System profiling tool.
   version         display the version of perf binary
   probe           Define new dynamic tracepoints
   trace           strace inspired tool

 See 'perf help COMMAND' for more information on a specific command.

```

执行`perf help <子命令>`获取子命令的详细帮助信息。具体使用方法会在另一篇专题文章中介绍。



### trace-cmd 

ftrace的命令行工具，用于收集和展现ftrace的数据。

有以下几个常用命令：

- start
- stop
- reset
- record
  - -P {pid} 追踪进程
  - -p {available_tracers} 
  - function  表示跟踪函数的执行
  - function_graph  跟踪函数的调用关系
  - -g {function}  针对于function_graph，指定要追踪的函数名字
  - --max-graph-depth 5  指定记录的最大函数调用深度。
  - -c -F  同时追踪子进程
- report



### perf-tools

trace和perf_event的包装器。参见 [perf-tools](https://github.com/brendangregg/perf-tools)。



### bcc

帮助开发eBPF程序，简化开发复杂度。

核心开发语言是C，可以用python和lua编写。可以用C+Python组合开发。

bcc的GitHub项目中包含examples和tools，可以作为开发参考和开箱即用的工具。

需要：

1. 熟悉C，Python
2. 熟悉被跟踪事件和函数的特征，例如参数和返回格式
3. 熟悉eBPF提供的各种数据操作方法



### bpftrace

不用写代码，一行搞定，所以称为“One Liner Tools”。

1. 基于bcc实现
2. bpftrace用于单行程序和短脚本
3. 基于c语言和awk



## 参考资料

1. [Exploring USDT Probes on Linux | ZH's Pocket](https://leezhenghui.github.io/linux/2019/03/05/exploring-usdt-on-linux.html)
2. https://www.processon.com/view/link/62a09494637689075856157e
   密码：linux  
   感谢： Linux简说
   
4. [linux kprobe_/sys/kernel/debug/kprobes/blacklist-CSDN博客](https://blog.csdn.net/weixin_41028621/article/details/114239403)

5. [Intel x86_64 PMU简介_小立爱学习的博客-CSDN博客](https://xiaolizai.blog.csdn.net/article/details/124238596?spm=1001.2101.3001.6650.1&utm_medium=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1)

   
