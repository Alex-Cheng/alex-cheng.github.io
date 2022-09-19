# 检查非法内存访问的方法



## 一般常见的错误内存访问

常见的内存错误访问包括以下几种：

1. 释放后使用 use after free
   在堆上释放了内存，但是后面又去访问。例如：

   ```c++
     5 int main (int argc, char** argv)
     6 {
     7     int* array = new int[100];
     8     delete []array;
     9     return array[1]; // 访问了释放后的内存。
    10 }
   ```

   

2. 堆缓冲区访问溢出 heap buffer overflow
   访问位置超出堆上的内存（例如：数组）的边界。例如：

   ```c++
     2 int main (int argc, char** argv)
     3 {
     4     int* array = new int[100];
     5     int res = array[100]; // 这句访问越界。
     6     delete [] array;
     7     return res;
     8 } 
   ```

   

3. 栈缓冲区访问溢出 stack buffer overflow
   访问位置超出栈上内存（例如：数组）的边界。例如

   ```c++
     2 int main (int argc, char** argv)
     3 {
     4     int array[100];
     5     return array[100]; // 这句访问越界。
     6 }
   ```

   

4. 全局缓冲区溢出 global buffer overflow 
   越界访问了一个全局数组。例如：

   ```c++
     2 int array[100];
     3 
     4 int main (int argc, char** argv)
     5 {
     6     return array[100]; // 这句访问越界。
     7 }
   ```

   

5. 函数返回后访问其栈空间 use after return
   函数返回后，访问了函数的栈内存。例如：

   ```c++
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

   

6. 访问超出范围的栈内存 use after scope

   要求只能在范围内访问栈内存（通常是局部变量），但是有些情况下可以出现在范围外访问范围内的局部变量。例如：

   ```c++
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

   或者另外一个关于lamda的例子：

   ```c++
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

   

7. 重复释放 double free
   堆上分配的内存，被重复释放。例如：

   ```c++
   int main() {
   
       int *x = new int[42];
       delete [] x;
   
       // ... 经过一些复杂的代码执行
   
       delete [] x; // 在某处重复释放之前释放过的内存。
       return 0;
   }
   ```

   

8. 初始化顺序错误 initializations order bugs

9. 内存泄漏 memory leaks
   分配的内存没有得到释放。例如：

   ```c++
    47 int func4(void)
    48 {
    49    char * p = (char*) malloc(5);
    50    memset(p,0x0,5);
    51    memcpy(p,"1234",4),
    52    printf("%s\n",p);   
    53 } // p指向的内存没有释放。
   ```

   

## Address Sanitizer

Address Sanitizer 可以检查上述的错误，用的方法是：***对内存维护一个poison标记，并在所有访问内存的指令处加检查代码***。

### 维护内存poison标记

Address Sanitizer会替换malloc() / free()，在分配内存时，会把内存前后的空间标记为poison，真正分配的内存才是被标注成 unpoison，释放之后会被也标注成poison。

具体做法是先把进程的地址空间分为两部分：

1. main application memory
   程序实际使用的内存。
2. shadow memory
   内存标记区，维护程序实际使用的内存的poison标记。shadow memory的一个字节对应程序实际使用内存的8个字节。

shadow memory的一个字节可能有以下几种不同的取值：

- 所有8字节都是`unpoisoned`的，则值为0；
- 所有8字节都是`poisoned`的，则值为负；
- 前k字节为`unpoisoned`，后面8-k字节为`poisoned`， 则值为k。



**注意：**

如果绕开malloc() / free() ，直接用mmap，就会绕过Address Sanitizer。



**示例：**

对于以下代码，Address Sanitizer会产生poison内存区和相应的shadow内容设置代码。

转换前：

```c++
void foo() 
{
  char a[8];
  ...
  return;
}
```

转换后：

```c++
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



### 插入检查指令

所有对内存的访问的地方都插入判断语句，如果是poison状态，则报告错误。

例如以下代码，

```c++
*address = ...;
```

会被替换为

```c++
if (IsPoisoned(address))
{
    ReportError(address, kAccessSize, kIsWrite);
}
*address = ...;
```

如果发生非法内存访问，Address Sanitizer会报告以下内容，包括试图访问的内存地址、访问内存的语句所在文件和位置、分配内存的语句所在文件和位置。

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



### malloc与free的替换

Address Sanitizer替换malloc与free函数，增加以下特性：

1. 在malloc时，将分配的内存标志为unpoisoned，并将其夹在unpoisoned内存区域之中，这样一旦访问出界就能够检测出；
2. 在free时，将释放的内存重新标志为poisoned；
3. 在free后，被释放的内存尽量长时间不要再次分配出去，以更好地检测出`use after free`错误。



## 参考资料

1. [AddressSanitizer · google/sanitizers Wiki (github.com)](https://github.com/google/sanitizers/wiki/AddressSanitizer)
2. [Address Sanitizer 用法 - 简书 (jianshu.com)](https://www.jianshu.com/p/3a2df9b7c353)
3. [工作笔记——C++快速的内存错误检测工具Address Sanitizer - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/103966527)



