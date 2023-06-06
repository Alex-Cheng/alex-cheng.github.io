# cmake简略

构建系统对于一个大型项目至关重要，本身就可以看成大项目中的一个子项目。cmake是C++生态环境中常用的构建工具。这里简单介绍一下cmake的用法。



## 最简单的例子

```cmake
cmake_minimum_required(VERSION 3.15)

# set the project name
project(Tutorial)

# add the executable
add_executable(Tutorial tutorial.cpp)
```



## 常用的命令 

以下面这个复杂一些的CMakeLists.txt文件内容为例：

```cmake
cmake_minimum_required(VERSION 3.15)

# set the project name
project(Tutorial)

set(SRC_LIST tutorial.cpp)

option(USE_MYMATH "Use tutorial provided math implementation" ON)

# add the executable
add_executable(${PROJECT_NAME} ${SRC_LIST})

# add the library
add_library(MathFunctions MathFunctions/mysqrt.cpp)

configure_file(TutorialConfig.h.in TutorialConfig.h)

target_include_directories(${PROJECT_NAME} PUBLIC
                           ${PROJECT_BINARY_DIR}
                           )

target_link_libraries(${PROJECT_NAME} PUBLIC MathFunctions)
```



- cmake_minimum_required(VERSION 3.15)
  要求cmake最低版本
- project(Tutorial)
  设置项目名称
- set(SRC_LIST tutorial.cpp)
  设置变量
- option(USE_MYMATH "Use tutorial provided math implementation" ON)
  设置构建选项
- add_executable(${PROJECT_NAME} ${SRC_LIST})
  添加可执行文件作为构建目标
- add_library(MathFunctions MathFunctions/mysqrt.cpp)
  添加库作为构建目标
- configure_file(TutorialConfig.h.in TutorialConfig.h)
  根据模板替换模板中的内容生成包含配置信息的头文件
- target_include_directories
  `target_include_directories(${PROJECT_NAME} PUBLIC  ${PROJECT_BINARY_DIR}  )`
  为构建目标添加include目录
- target_link_libraries(${PROJECT_NAME} PUBLIC MathFunctions)
  为构建目标链接静态库。



## 设置变量

```cmake
list(APPEND EXTRA_LIBS MathFunctions)
set(SRC_LIST a.cpp b.cpp c.cpp)
string(TIMESTAMP COMPILE_TIME %Y%m%d-%H%M%S)
unset(SRC_LIST)
```



### 常用变量

${PROJECT_NAME}

${PROJECT_SOURCE_DIR}

${PROJECT_BINARY_DIR}

${CMAKE_ROOT}

${CMAKE_CURRENT_BINARY_DIR}

${CMAKE_CURRENT_SOURCE_DIR}



### 控制编译器行为

```cmake
set (CMAKE_CXX_STANDARD 23)
set (CMAKE_CXX_EXTENSIONS OFF)
set (CMAKE_CXX_STANDARD_REQUIRED ON)
```



## 构建开关

`option`定义构建开关，以下面为例：

```cmake
option(USE_MYMATH "Use tutorial provided math implementation" ON)
if(USE_MYMATH)
  add_subdirectory(MathFunctions)
  list(APPEND EXTRA_LIBS MathFunctions)
  list(APPEND EXTRA_INCLUDES ${PROJECT_SOURCE_DIR}/MathFunctions)
endif()

```



## cmake的信息到源代码

在这个例子中，在CMakeLists.txt文件中定义几个版本和构建时间的变量，然后通过configure_file生成头文件。

**CMakeLists.txt**

```cmake
set (Tutorial_VERSION_MAJOR 1)
set (Tutorial_VERSION_MINOR 0)
set (Tutorial_VERSION_PATCH 12)
string(TIMESTAMP COMPILE_TIME %Y%m%d-%H%M%S)

configure_file(TutorialConfig.h.in TutorialConfig.h)
```



**TutorialConfig.h.in**

```c++
// the configured options and settings for Tutorial
#define Tutorial_VERSION_MAJOR @PROJECT_VERSION_MAJOR@
#define Tutorial_VERSION_MINOR @PROJECT_VERSION_MINOR@
#define Tutorial_VERSION_PATCH @PROJECT_VERSION_PATCH@

#define TIMESTAMP @COMPILE_TIME@
```



### 导入options

假设`USE_SSL`是cmake定义的option，`option(USE_SSL "Use SSL" ON)`。在`config.h.in`中可以这样定义并获得option的值。

```cmake
#cmakedefine01 USE_SSL
```



## Macro

cmake的macro可以是很强大的。

比如这个就很有用，用于添加源代码文件到变量里。

```cmake
macro(add_glob cur_list)
    file(GLOB __tmp CONFIGURE_DEPENDS RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} ${ARGN})
    list(APPEND ${cur_list} ${__tmp})
endmacro()

macro(add_headers_and_sources prefix common_path)
    add_glob(${prefix}_headers ${CMAKE_CURRENT_SOURCE_DIR} ${common_path}/*.h)
    add_glob(${prefix}_sources ${common_path}/*.cpp ${common_path}/*.c ${common_path}/*.h)
endmacro()

macro(add_headers_only prefix common_path)
    add_glob(${prefix}_headers ${CMAKE_CURRENT_SOURCE_DIR} ${common_path}/*.h)
endmacro()

```



比如这个就扩展了`add_executable`的功能，创建了一个更强大的`add_executable`。

```cmake
macro (clickhouse_add_executable target)
    # invoke built-in add_executable
    # explicitly acquire and interpose malloc symbols by clickhouse_malloc
    # if GLIBC_COMPATIBILITY is ON and ENABLE_THINLTO is on than provide memcpy symbol explicitly to neutrialize thinlto's libcall generation.
    if (ARCH_AMD64 AND GLIBC_COMPATIBILITY AND ENABLE_THINLTO)
        add_executable (${ARGV} $<TARGET_OBJECTS:clickhouse_malloc> $<TARGET_OBJECTS:memcpy>)
    else ()
        add_executable (${ARGV} $<TARGET_OBJECTS:clickhouse_malloc>)
    endif ()

    get_target_property (type ${target} TYPE)
    if (${type} STREQUAL EXECUTABLE)
        # disabled for TSAN and gcc since libtsan.a provides overrides too
        if (TARGET clickhouse_new_delete)
            # operator::new/delete for executables (MemoryTracker stuff)
            target_link_libraries (${target} PRIVATE clickhouse_new_delete)
        endif()

        # In case of static jemalloc, because zone_register() is located in zone.c and
        # is never used outside (it is declared as constructor) it is omitted
        # by the linker, and so jemalloc will not be registered as system
        # allocator under osx [1], and clickhouse will SIGSEGV.
        #
        #   [1]: https://github.com/jemalloc/jemalloc/issues/708
        #
        # About symbol name:
        # - _zone_register not zone_register due to Mach-O binary format,
        # - _je_zone_register due to JEMALLOC_PRIVATE_NAMESPACE=je_ under OS X.
        # - but jemalloc-cmake does not run private_namespace.sh
        #   so symbol name should be _zone_register
        if (ENABLE_JEMALLOC AND OS_DARWIN)
            set_property(TARGET ${target} APPEND PROPERTY LINK_OPTIONS -u_zone_register)
        endif()
    endif()
endmacro()

```



## build目录

```text
build/
    CMakeCache.txt
    CMakeFiles/
    cmake_install.cmake
    Makefile
    Tutorial.exe
    TutorialConfig.h
    MathFunctions/
```



`Makefile` 是 cmake 根据顶级 CMakeLists.txt 生成的构建文件，通过该文件可以对整个项目进行编译。

`Tutorial.exe` 就是生成的可执行文件，通过该文件运行程序。

`MathFunction`是库的目录。

## 更进一步
cmake其实是一个语言，可以简单地使用其基本功能，也可以复杂地把它当成一门编程语言。
[cmake详细介绍](https://blog.csdn.net/wzj_110/category_10357507.html) 说得更加详细。
