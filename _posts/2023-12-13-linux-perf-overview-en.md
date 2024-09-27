# Overview of Linux performance tuning techniques



## Overview

Linux performance tuning here is mainly about performance tracking of programs on Linux systems, because only by collecting accurate enough performance data can the performance bottlenecks of programs and systems be found. The principles, frameworks, and tools of Linux performance tuning include three aspects:

1. Information sources
are usually in the form of “events”, also known as “event sources”.

2. Tracking frameworks that interface with information sources

collects data from the information source, hides the complexity involved, and provides an external interface for use (usually a programming interface).

3. Front-end operating interface

The user operating interface tool (usually in the form of a command line) allows easy use by ordinary users.



The following figure shows the performance monitoring system:

![Performance monitoring system](/assets/image-20231114192048746.png)

Performance tuning concerns can be roughly divided into three categories:

1. CPU utilization and bottlenecks
2. Memory utilization and bottlenecks
3. I/O conditions (files, disks, networks, etc.)

This information can be obtained by monitoring different types of “events”, and combined with contextual information, to gain insights into performance optimization.



## Information sources (event sources)

Since performance is mainly presented in the form of events, the information sources are also referred to as “event sources”. The information sources are mainly divided into hardware events, static probes (recompilation of the kernel is required) and dynamic probes (recompilation is not required).



### Hardware events (supported by the CPU)

are usually implemented using performance monitoring counters (PMCs). Performance monitoring counters (PMCs) are programmable hardware counters on the processor that measure events that occur in the processor. These counters can record various hardware performance conditions, such as the CPU cache, instruction cycles, branch prediction, etc. Since PMCs are a built-in feature of the CPU, they can provide the lowest-level performance information that is otherwise unavailable. For example, only PMCs can measure the efficiency of CPU instruction execution, the CPU cache hit ratio, the utilization of memory/data interconnects and device buses, and blocked instruction cycles.

PMCs can help identify bottlenecks in an application. For example, a large number of conditional branch instructions may indicate a piece of logic that, if rearranged, may reduce the number of branches required. PMCs therefore play a key role in performance testing and optimization. PMCs can support the following (including but not limited to):

- Tracking CPU caches
- Tracking instruction cycles
- Tracking branch prediction and other hardware performance

Please note that different processors and hardware platforms may have different PMCs and corresponding programming interfaces. Therefore, when using PMCs, you need to refer to the specific hardware and operating system documentation for detailed information and guidance. For example, Intel's chip performance monitoring counter (called PMU here at Intel) introduction [Intel x86_64 PMU Introduction_Xiaoli's Learning Blog-CSDN Blog](https://xiaolizai.blog.csdn.net/article/details/124238596?spm=1001.2101 .3001.6650.1&utm_medium=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort _base1&depth_1-utm_source=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1)



### Static probes

Static probes are defined in the code in advance and compiled into the application or kernel, i.e. “pointers buried in the code”.

#### Linux kernel tracepoints

Linux kernel tracepoints are predefined tracepoints in the Linux kernel source code. Linux kernel events are defined in the code as functions and the function is called to trigger the event when required. The following is a code snippet as an example:

```cpp

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



The events defined in the kernel code are displayed by `cat /sys/kernel/debug/tracing/available_events`. In the author's current environment, there are 1565 defined kernel events.

Note: There is a lot more content in the `/sys/kernel/debug/tracing/` directory.



#### USDT probe 

USDT probe (User Statically-Defined Tracing) is the full name of user-level statically defined tracing. It requires the insertion of DTRACE_PROBE() code in the source code and compilation into the application. It will not be described in detail here.



### Dynamic probes

As the name suggests, they are probes that are not defined in the code in advance, but can be added dynamically at runtime (the key point is that the target program does not need to be recompiled). They are mainly composed of kprobes (kernel probes) and uprobe (user-mode probes).



#### Kernel probes kprobes

kprobes (Kernel Dynamic Probes) are mainly used for debugging and tracing the kernel. They are a relatively lightweight mechanism that essentially inserts a set of handlers at specified probe points (such as a certain line of a function, the entry and exit addresses of a function, or a specified address in the kernel). When the kernel executes to this set of handlers, it can obtain the current execution context information, such as the current function name, the parameters processed by the function, and the return value of the function. It can also obtain information about registers and even global data structures.

The kprobes mechanism can implement three types of probes:

- kprobe can be inserted into any instruction position of the kernel
- jprobe probe point of the kernel function entry
- kretprobe probes at the return point of a kernel function

In kernel performance monitoring, the use of dynamic probes allows:

1. normal kernel operation during debugging
2. no need to modify or compile the kernel
3. can be enabled and disabled at any time

These features are very useful. Applicable scenarios include:

- checking whether a kernel function has been called
- viewing the time spent by a kernel function
- injecting bug fix code equivalent to a kernel patch



#### User-mode probes uprobes

uprobes (User Dynamic Probes) are used to trace user-mode functions, including uprobe for function calls and uretprobe for function returns.



## Tracing Framework

### ftrace

ftrace is built into the Linux kernel and can be used with Linux kernel tracing points, kprobes and uprobs. It provides the following features: event tracing with optional filters and parameters; event counting and timing, with summary calculations in the kernel; and function execution flow tracing. See ftrace.txt in the kernel source code for detailed examples.

One of the most powerful tracers in ftrace is the function tracer, which is used to trace the execution flow of functions. The principle is to add an option to the compiler to insert code into each function that makes a call to a special function “mcount()”. When the function tracer is not enabled, this code is replaced with “NOP” (NOP is a machine instruction that does nothing); when the function tracer is enabled, “NOP” is replaced with code that calls “mcount()”.

ftrace is not kernel-settable.

### perf_event

perf_events are the main tracing tool for Linux users. The source code is in the Linux kernel and is usually added through the Linux Tool Common Package. The corresponding command-line tool is “perf”. It can do most of the things “ftrace” can do. And it is less hackable (because it has better security/error checking).

One of the main features of perf_events is that it can be sampled (the main methods of performance data collection are probes and sampling) and can perform user-level stack switching.

Like ftrace, it is not kernel-mode programmable.

Nevertheless, perf_event can do a lot of things, is relatively safe, and is recommended for use.

#### How sampling works

Every fixed period of time (depending on the sampling rate), it looks at which process and function it is, and then adds a statistical value to the corresponding process and function, so that you know how much time the CPU has spent in a process or function.



#### Consumable event sources

- Hardware events, tracepoints, kprobes, uprobes, etc.
- Supports custom dynamic events
- Supports sampling 



### eBPF

BPF, Berkeley Packet Filter, is a technique for optimizing packet filters. eBPF stands for Extended Berkerley Packet Filter, which extends the functionality of BPF to do other things besides packet filtering, such as kernel event tracing.

Features:

- A kernel sandbox that can run programs safely and efficiently on events

- Supports common event tracing, including kprobe, uprobe, and perf_event

- Execute custom analysis programs on Linux to process events, including dynamic tracing, static tracing, and profiling events



### SystemTap

is said to be the most powerful tracer (but also possibly the most difficult to use). By writing your own script, it can be compiled into the kernel by stap as a **driver** and used to do almost anything, although it is not very secure.

Supports older kernel versions such as 3.x

Inserted into the kernel as a driver, it can do almost anything.



### sysdig

is comprehensive and powerful, with a unified syntax

Sysdig is a super system tool that has the following advantages over strace:

1. Powerful: Sysdig is more powerful than strace, tcpdump, lsof, and other tools combined. It can capture system status information, save data, and filter and analyze it.
sysdig = strace + tcpdump + htop + iftop + Lsof + docker inspect
2. Developed using Lua: Sysdig is developed using the Lua programming language, providing flexible scripting support. Users can customize scripting to extend its functionality according to their own needs.
3. Command line interface and interactive interface: Sysdig provides a command line interface as well as a powerful interactive interface. Users can conveniently use the command line to operate, or they can use the interactive interface for more intuitive operation and monitoring.

Therefore, choosing Sysdig can get more powerful and flexible system monitoring and analysis capabilities.



Applicable to:

- Mainly used for dynamic tracing of containers (especially k8s)
- Uses a syntax similar to tcpdump and lua to post-process operating system call events;
- Can also be extended using eBPF. It can also be used to trace various functions and events in the kernel.



### Other

There are also some other tracing frameworks, just to name a few:

1. LTTng
2. ktap
3. dtrace4linux
4. Oracle Linux DTrace
5. DTrace



## Front-end tools

Front-end tools are command line or graphical interface tools that provide users with an entry point to use the various tracing framework functions.

### ftrace - file system

ftrace - file system Constructs a file system at the location `/sys/kernel/debug/tracing`, and users use ftrace by reading and writing files.

The Unix philosophy of “everything is a file” is fully reflected here.

```bash
#1. Go to the debugfs directory
$ cd /sys/kernel/debug/tracing
#If you can't find the directory, execute the following command to mount debugfs:
$ mount -t debugfs nodev /sys/kernel/debug

#2. Query supported tracers
$ cat available_tracers
#There are two common types:
#
#- function indicates tracing the execution of a function;
#- function_graph traces the calling relationship of functions;

#3. View the kernel functions and events that support tracing. The function is the name of the function in the kernel, and the event is a predefined trace point in the kernel source code.
#//View kernel functions
$ cat available_filter_functions
#//View events
$ cat available_events

#4. Set the tracing function:
$ echo do_sys_open > set_graph_function

#5. Set the tracer
$ echo function*graph > current_tracer
$ echo funcgraph-proc > trace_options

#6. Enable tracing
$ echo 1 > tracing_on

#7. Execute an ls command and then disable tracing
$ ls
$ echo 0 > tracing_on

#8. Finally, view the tracing results
$ cat trace
```



### perf tool

The perf tool is very powerful. If used well, it can basically fully meet the needs of application performance analysis and tuning.

Execute the command `sudo perf help` to get the perf usage instructions. The perf tool includes several subcommands, listed below:

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

Execute `perf help <subcommand>` to get detailed help information for the subcommand. The specific usage method will be introduced in another feature article.



### trace-cmd 

The ftrace command-line tool is used to collect and display ftrace data.

The following are the most common commands:

- start
- stop
- reset
- record
- -P {pid} Trace the process
- -p {available_tracers} 
- function Trace the execution of the function
- function_graph Trace the call relationship of the function
- -g {function} For function_graph, specify the name of the function to trace
- --max-graph-depth 5 Specify the maximum function call depth to record.
- -c -F Trace subprocesses simultaneously
- report



### perf-tools

Trace and perf_event wrapper. See [perf-tools](https://github.com/brendangregg/perf-tools).



### bcc

Helps develop eBPF programs and simplifies development complexity.

The core development language is C, and it can be written in python and lua. It can be developed using a combination of C and Python.

The bcc GitHub project includes examples and tools that can be used as a reference for development and out-of-the-box tools.

Requires:

1. Familiar with C and Python
2. Familiar with the characteristics of tracked events and functions, such as parameters and return formats
3. Familiar with the various data manipulation methods provided by eBPF



### bpftrace

No code needs to be written, and it can be done in one line, so it is called “One Liner Tools”.

1. Implemented based on bcc
2. bpftrace is used for one-line programs and short scripts
3. Based on C and awk



## References

1. [Exploring USDT Probes on Linux | ZH's Pocket](https://leezhenghui.github.io/linux/2019/03/05/exploring-usdt-on-linux.html)
2. https://www.processon.com/view/link/62a09494637689075856157e
Password: linux 
Thanks: Linux in a Nutshell

4. [linux kprobe_/sys/kernel/debug/kprobes/blacklist-CSDN博客](https://blog.csdn.net/weixin_41028621/article/details/114239403)

5. [Introduction to Intel x86_64 PMU_Xiaoli's blog for learning-CSDN blog](https://xiaolizai.blog.csdn.net/article/details/124238596?spm=1001.2101.3001.6650 .1&utm_medium=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1&depth _1-utm_source=distribute.pc_relevant.none-task-blog-2~default~BlogCommendFromBaidu~Rate-1-124238596-blog-8686130.235^v38^pc_relevant_sort_base1)
