# Methods for checking illegal memory access



## Commonly seen illegal memory access

Commonly seen illegal memory access includes the following:

1. Use after free
Memory is released on the heap, but then accessed again. For example:

   ```cpp
     5 int main (int argc, char** argv)
     6 {
     7     int* array = new int[100];
     8     delete []array;
     9     return array[1]; // 访问了释放后的内存。
    10 }
   ```



2. heap buffer overflow
Accessing a location beyond the boundary of the heap-based memory (e.g. an array). Example:

   ```cpp
     2 int main (int argc, char** argv)
     3 {
     4     int* array = new int[100];
     5     int res = array[100]; // 这句访问越界。
     6     delete [] array;
     7     return res;
     8 } 
   ```



3. stack buffer overflow
Accessing a location beyond the boundary of stack-based memory (e.g. an array). For example

   ```cpp
     2 int main (int argc, char** argv)
     3 {
     4     int array[100];
     5     return array[100]; // 这句访问越界。
     6 }
   ```



4. global buffer overflow 
Accessing an array out of bounds. Example:

   ```cpp
     2 int array[100];
     3 
     4 int main (int argc, char** argv)
     5 {
     6     return array[100]; // 这句访问越界。
     7 }
   ```



5. Accessing the stack space of a function after it returns use after return
After a function returns, its stack memory is accessed. For example:

   ```cpp
   char* foo() {
       char stack_buffer[42];
       x = &stack_buffer[13];
   }
   
   int main() {
   
       char* x = foo();
       *x = 42; // 访问了foo函数的栈内存空间。
   
       return 0;
   }
   ```



6. Accessing stack memory out of scope

Requires that stack memory (usually local variables) can only be accessed within the scope, but there are cases where local variables within the scope can be accessed outside the scope. For example:

   ```cpp
   int *gp;
   bool b = true;
   int main() {
       if (b) {
           int x[5];
           gp = x+1;
       }
       return *gp;  // 在范围外访问了栈内存。
   }
   ```

Or another example with lambda:

   ```cpp
   #include <functional>
   
   int main() {
       std::function<int()> f;
       // 这是一个范围scope。
       {
           int x = 0;
           f = [&x]() {
               return x;  // 访问了范围外的栈内存。
           };
       }
       return f();  // 这时候f绑定的x已经是出了范围的了。
   }
   ```



7. Double free
Memory allocated on the heap is double-freed. Example:

   ```cpp
   int main() {
   
       int *x = new int[42];
       delete [] x;
   
       // ... 经过一些复杂的代码执行
   
       delete [] x; // 在某处重复释放之前释放过的内存。
       return 0;
   }
   ```



8. Initialization order bugs

9. Memory leaks
Memory that has been allocated is not released. Example:

   ```cpp
    47 int func4(void)
    48 {
    49    char * p = (char*) malloc(5);
    50    memset(p,0x0,5);
    51    memcpy(p,"1234",4),
    52    printf("%s\n",p);   
    53 } // p指向的内存没有释放。
   ```



## Address Sanitizer

Address Sanitizer can check for the above errors by maintaining a poison flag for memory and adding check code to all instructions that access memory.

### Maintaining the memory poison flag

Address Sanitizer replaces malloc() / free() and marks the space before and after the memory as poison when allocating memory. The memory that is actually allocated is marked as unpoison, and after being released, it will also be marked as poison.

The specific method is to first divide the address space of the process into two parts:

1. main application memory
The memory actually used by the program.
2. shadow memory
The memory marking area that maintains the poison mark of the memory actually used by the program. One byte of shadow memory corresponds to 8 bytes of memory actually used by the program.

One byte of shadow memory may have the following different values:

- all 8 bytes are `unpoisoned`, the value is 0;
- all 8 bytes are `poisoned`, the value is negative;
- the first k bytes are `unpoisoned`, the next 8-k bytes are `poisoned`, the value is k.



**Note:**

If you bypass malloc() / free() and use mmap directly, you will bypass Address Sanitizer.



**Example:**

For the following code, Address Sanitizer will generate code to set up the poisoned memory area and the corresponding shadow content.

Before conversion:

```cpp
void foo() 
{
  char a[8];
  ...
  return;
}
```

After conversion:

```cpp
void foo() 
{
  char redzone1[32];  // 32-byte aligned
  char a[8];          // 32-byte aligned
  char redzone2[24];
  char redzone3[32];  // 32-byte aligned
  int  *shadow_base = MemToShadow(redzone1);
  shadow_base[0] = 0xffffffff;  // poison redzone1
  shadow_base[1] = 0xffffff00;  // poison redzone2, unpoison 'a'
  shadow_base[2] = 0xffffffff;  // poison redzone3
  ...
  shadow_base[0] = shadow_base[1] = shadow_base[2] = 0; // unpoison all
  return;
}
```



### Insertion checking instructions

A judgment statement is inserted at all places where memory is accessed. If it is in a poisoned state, an error is reported.

For example, in the following code,

```cpp
*address = ...;
```

will be replaced with

```cpp
if (IsPoisoned(address))
{
    ReportError(address, kAccessSize, kIsWrite);
}
*address = ...;
```

If an illegal memory access occurs, Address Sanitizer will report the following, including the address of the memory being accessed, the file and position of the statement accessing the memory, and the file and position of the statement allocating the memory.

```ini
==3499==ERROR: AddressSanitizer: global-buffer-overflow on address 0x000000601270 
at pc 0x000000400915 bp 0x7ffd8e80c020 sp 0x7ffd8e80c010
READ of size 4 at 0x000000601270 thread T0
    #0 0x400914 in main /home/ron/dev/as/global_buf_overflow.cpp:6
    #1 0x7f613c1c882f in __libc_start_main (/lib/x86_64-linux-gnu/libc.so.6+0x2082f)
    #2 0x400808 in _start (/home/ron/dev/as/build/global_buf_overflow+0x400808)

0x000000601270 is located 0 bytes to the right of global variable 'array' defined in 
'/home/ron/dev/as/global_buf_overflow.cpp:2:5' (0x6010e0) of size 400
SUMMARY: AddressSanitizer: global-buffer-overflow /home/ron/dev/as/global_buf_overflow.cpp:6 main
```




### Replacement of malloc and free

Address Sanitizer replaces the malloc and free functions with the following features:

1. When allocating memory, mark the allocated memory as unpoisoned and enclose it in an unpoisoned memory area, so that it can be detected as soon as it is accessed out of bounds;
2. When freeing memory, re-mark the freed memory as poisoned;
3. After freeing, do not reallocate the freed memory for as long as possible to better detect `use after free` errors.



## References

1. [AddressSanitizer · google/sanitizers Wiki (github.com)](https://github.com/google/sanitizers/wiki/AddressSanitizer)
2. [Address Sanitizer 用法 - 简书 (jianshu.com)](https://www.jianshu.com/p/3a2df9b7c353)
3. [Work Notes - cpp's Fast Memory Error Detection Tool Address Sanitizer - Zhihu (zhihu.com)](https://zhuanlan.zhihu.com/p/103966527)
