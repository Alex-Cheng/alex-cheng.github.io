# Windows系统上搭建Clickhouse开发环境

## 总体思路

微软的开发IDE是很棒的，有两种：Visual Studio 和 VS Code，一个重量级，一个轻量级。近年来VS Code越来越受欢迎，因为她的轻量级和丰富的插件，更重要的是VS Code消耗资源更少，打开大项目的时候不会崩溃。因此选用VS Code。

Clickhouse只能在Linux和MacOS上编译和运行，而开发机器是Windows 10系统，因此需要虚拟机或者WSL。WSL是Windows subsystem Linux，Windows 10原生支持，因此采用WSL。

调试用linux下最常用的GDB，在WSL环境中用GDB调试clickhouse，而开发环境运行在Windows上，这就需要远程连接GDB。

下面是具体步骤。



## 构建clickhouse的debug build

Clickhouse默认是通过静态链接构建出一个完整的release版的运行文件：clickhouse，大小在1G以上。这个巨大的单体release版本的可执行文件并不利于调试。为了开发和调试，我们需要symbol文件，需要把单体巨型文件拆散成一群动态链接库小文件，因此需要特殊的cmake构建参数。

执行以下步骤完成debug构建，有问题参考clickhouse官方文档 [Build on Linux | ClickHouse Documentation ](https://clickhouse.com/docs/en/development/build/#build-clickhouse)

1. 安装WSL
   在管理员PowerShell中运行`wsl --install`，有问题参考微软官方文档 [安装 WSL | Microsoft Docs](https://docs.microsoft.com/zh-cn/windows/wsl/install)

2. 安装构建工具cmake、ninja
   在WSL环境中，运行`sudo apt-get install -y git cmake python ninja-build`，有问题参考google。

3. 安装clang编译器，该编译器效率比gcc据说还要好
   在WSL环境中，运行`sudo bash -c "$(wget -O - https://apt.llvm.org/llvm.sh)"`

4. 下载clickhouse代码

   ```shell
   git clone https://github.com/ClickHouse/ClickHouse.git
   cd ClickHouse
   git submodule update --init --recursive
   ```

   

5. 加参数编译我们需要的clickhouse的适合开发调试的版本

   ```shell
   export CC=clang-13
   export CXX=clang++-13
   cd ClickHouse
   mkdir build
   cd build
   cmake .. \
   	-DUSE_STATIC_LIBRARIES=0 \
   	-DSPLIT_SHARED_LIBRARIES=1 \
   	-DCLICKHOUSE_SPLIT_BINARY=1 \
   	-DCMAKE_BUILD_TYPE=Debug 
   
   ninja
   ```

   USE_STATIC_LIBRARIES=0  -- 不用编译成静态链接

   SPLIT_SHARED_LIBRARIES=1  -- 拆开成共享库

   CLICKHOUSE_SPLIT_BINARY=1  -- 编译的二进制文件拆开

6. (可选）只编译clickhouse client和server

   ```shell
   cmake .. \
       -DCMAKE_C_COMPILER=$(which clang-13) \
       -DCMAKE_CXX_COMPILER=$(which clang++-13) \
       -DCMAKE_BUILD_TYPE=Debug \
       -DENABLE_CLICKHOUSE_ALL=OFF \
       -DENABLE_CLICKHOUSE_SERVER=ON \
       -DENABLE_CLICKHOUSE_CLIENT=ON \
       -DENABLE_LIBRARIES=OFF \
       -DUSE_UNWIND=ON \
       -DENABLE_UTILS=OFF \
       -DENABLE_TESTS=OFF \
      -DUSE_STATIC_LIBRARIES=0  \
      -DSPLIT_SHARED_LIBRARIES=1  \
      -DCLICKHOUSE_SPLIT_BINARY=1 
   
   ```

   

## 配置开发环境

### 安装VS Code

从微软官网上下载并运行VSCode，不再赘述。

安装好VS Code之后，打开VS Code安装C++插件：Microsoft C/C++。



### 关联WSL中的代码仓库

因为编译和运行在WSL中，开发在Windows中，要让两边同步。最好的办法就是Windows环境中VS Code所修改的代码就是WSL中编译运行的代码。好在Windows环境中可以直接通过`\\wsl$`去访问WSL中的文件系统，再通过Windows的把网络路径映射成盘符的功能，我们就能够像访问本地磁盘那样访问WSL中的文件系统。

![image.png](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/fbbb2a85c19e1866c0fd70749c5ef6a6b6b74f1b/_posts/images/10535366-42b00b0bc4527254.png)

这样WSL中的/home/alex/depot/ch-pro代码目录就映射成了 Z:\home\alex\depot\ch-pro 代码目录。用VS Code打开 Z:\home\alex\depot\ch-pro目录，修改其代码会直接修改WSL中的代码。



### VS Code调试运行配置

在WSL环境中安装gdb，`apt install gdb`

**重要**  在VS Code中新建运行配置`./.vscode/launch.json`。

```json
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [

      {
        "name": "(clickhouse) 启动",
        "type": "cppdbg",
        "request": "launch",
        "program": "/home/alex/depot/ch-pro/build/programs/clickhouse-server",
        "args": [],
        "stopAtEntry": false,
        "cwd": "/home/alex/depot/ch-pro",
        "environment": [{"name": "CLICKHOUSE_WATCHDOG_ENABLE", "value":0}],
        "externalConsole": true,
        "windows": {
          "MIMode": "gdb",
          "setupCommands": [
              {
                  "description": "Enable pretty-printing for gdb",
                  "text": "-enable-pretty-printing",
                  "ignoreFailures": true
              }
          ]
      },
      "pipeTransport": {
          "pipeCwd": "",
          "pipeProgram": "C:\\Windows\\System32\\bash.exe",
          "pipeArgs": ["-c"],
          "debuggerPath": "/usr/bin/gdb"
      },
      "sourceFileMap": {
          "/mnt/c": "C:\\",
          "/usr": "Z:\\usr",
          "/home": "Z:\\home"
      }
      }
    ]
}
```

**注意**

`"environment": [{"name": "CLICKHOUSE_WATCHDOG_ENABLE", "value":0}]` 这行尤为重要，以为非从terminal上启动的clickhouse都会把启动进程变成一个watch dog进程，启动另外一个进程作为真正的clickhouse进程，那么调试时attach到的进程是启动进程也就是watch dog进程，无法调试真正的clickhouse代码。必须设置环境变量CLICKHOUSE_WATCHDOG_ENABLE=0来阻止clickhouse这么做。

远程启动clickhouse并调试，如图所示：

![image.png](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/fbbb2a85c19e1866c0fd70749c5ef6a6b6b74f1b/_posts/images/10535366-badf022347a28196.png)

走到断点成功中断运行却提示找不到源代码文件，需要设置gdb的设置，`set substitute-path <from_path> <to_path> ` 添加地址转换。

正常情况下，就已经可以断点调试了。

![image.png](https://raw.githubusercontent.com/Alex-Cheng/alex-cheng.github.io/fbbb2a85c19e1866c0fd70749c5ef6a6b6b74f1b/_posts/images/10535366-d8383ff8136ce38a.png)

修改完代码之后，如果有文件增删，则需要重新运行cmake，如果只是修改文件，则只需要运行ninja。ninja会只编译修改过的文件。
