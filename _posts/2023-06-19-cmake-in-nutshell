# cmake in a nutshell

The build system is critical to a large project, and can itself be seen as a sub-project within the larger project. cmake is a common build tool in the C++ ecosystem. Here is a brief introduction to the usage of cmake.



## The simplest example

```cmake
cmake_minimum_required(VERSION 3.15)

# set the project name
project(Tutorial)

# add the executable
add_executable(Tutorial tutorial.cpp)
```



## Common commands 

Take the following complex CMakeLists.txt file as an example:

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
  Required minimum version of cmake
- project(Tutorial)
  Set the name of the project
- set(SRC_LIST tutorial.cpp)
  Set variables
- option(USE_MYMATH "Use tutorial provided math implementation" ON)
  Set build options
- add_executable(${PROJECT_NAME} ${SRC_LIST})
  Add an executable as a build target
- add_library(MathFunctions MathFunctions/mysqrt.cpp)
  Add a library as a build target
- configure_file(TutorialConfig.h.in TutorialConfig.h)
  Generate a header file containing configuration information based on the template by replacing the contents of the template
- target_include_directories
  `target_include_directories(${PROJECT_NAME} PUBLIC ${PROJECT_BINARY_DIR} )`
  Add include directories to the build target
- target_link_libraries(${PROJECT_NAME} PUBLIC MathFunctions)
  Link static libraries for the build target.



## Set variables

```cmake
list(APPEND EXTRA_LIBS MathFunctions)
set(SRC_LIST a.cpp b.cpp c.cpp)
string(TIMESTAMP COMPILE_TIME %Y%m%d-%H%M%S)
unset(SRC_LIST)
```



### Common variables

${PROJECT_NAME}

${PROJECT_SOURCE_DIR}

${PROJECT_BINARY_DIR}

${CMAKE_ROOT}

${CMAKE_CURRENT_BINARY_DIR}

${CMAKE_CURRENT_SOURCE_DIR}



### Control compiler behavior

```cmake
set (CMAKE_CXX_STANDARD 23)
set (CMAKE_CXX_EXTENSIONS OFF)
set (CMAKE_CXX_STANDARD_REQUIRED ON)
```



## build switch

``option`'' defines the build switch, as in the following example:

```cmake
option(USE_MYMATH "Use tutorial provided math implementation" ON)
if(USE_MYMATH)
  add_subdirectory(MathFunctions)
  list(APPEND EXTRA_LIBS MathFunctions)
  list(APPEND EXTRA_INCLUDES ${PROJECT_SOURCE_DIR}/MathFunctions)
endif()

```



## Information from cmake to source code

In this example, define several variables for version and build time in the CMakeLists.txt file, and then generate the header file via configure_file.

**CMakeLists.txt**

```cmake
set (Tutorial_VERSION_MAJOR 1)
set (tutorial_VERSION_MINOR 0)
set (tutorial_VERSION_PATCH 12)
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



### Importing options

Assume that `USE_SSL` is an option defined by cmake, `option(USE_SSL "Use SSL" ON)`. You can define and get the value of option in `config.h.in` like this.

``cmake
#cmakedefine01 USE_SSL
```



## Macro

cmake's macro can be very powerful.

For example, this one is useful for adding source files to variables.

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



This one, for example, extends `add_executable` to create a more powerful `add_executable`.

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
        # [1]: https://github.com/jemalloc/jemalloc/issues/708
        #
        # About symbol name.
        # - _zone_register not zone_register due to Mach-O binary format.
        # - _je_zone_register due to JEMALLOC_PRIVATE_NAMESPACE=je_ under OS X.
        # - but jemalloc-cmake does not run private_namespace.sh
        # so symbol name should be _zone_register
        if (ENABLE_JEMALLOC AND OS_DARWIN)
            set_property(TARGET ${target} APPEND PROPERTY LINK_OPTIONS -u_zone_register)
        endif()
    endif()
endmacro()

```



## build directory

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



`Makefile` is the build file generated by cmake from the top-level CMakeLists.txt, through which the whole project can be compiled.

`Tutorial.exe` is the generated executable file through which the program is run.

`MathFunction` is the directory of the library.
