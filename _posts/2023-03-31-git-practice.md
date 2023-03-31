# GIT使用技巧

## 导出GIT日志到文件

按照 <哈希> - <作者名> <作者邮箱地址> - <作者日期> : <commit描述> 的格式导出日志

```Bash
git log --pretty=format:"%H - %an <%ae> - %ad : %s" master > log.txt
```

筛选日志并按照从旧到新的顺序排序，且只要提交哈希值（用于批量cherry-pick等操作）

```Bash
cat log.txt | grep <匹配关键字> | awk '{print $1}' | tac
```



## 批量git cherry-pick

要批量应用 `git cherry-pick` 命令，可以使用 `xargs`配合 `git cherry-pick` 使用。具体步骤如下：

1. 将要应用的提交 ID 复制到一个文本文件中，每行一个提交 ID。
2. 执行以下命令：

```Bash
cat file.txt | xargs git cherry-pick <options>
```

`options `可以是 `-m 1` ，意思是遇到merge commit的时候，因为merge commit会有多个parent，需要选择以哪个parent为主。`-m 1` 是指以第一个parent为主。如果不指定该选项，遇到merge commit会报错中断。

当使用 `git cherry-pick` 命令批量应用提交时，可能会发生冲突。如果发生冲突，Git 会停止应用提交，并提示您解决冲突。在解决冲突后，您需要继续应用剩余的提交。可以使用 `git cherry-pick --continue` 命令来继续应用提交，或者使用 `git cherry-pick --abort` 命令取消应用提交。



## 查看删除文件的历史记录

用以下命令去查看改名或者删除某个文件的commit。

```Bash
git log --follow --diff-filter=RD --full-history <分支名> -- <文件路径>
```

`git log`会从分支的HEAD节点往上回溯，找到所有符合条件的commit。



## 强行更新submodules

submodules的内容有时候会丢失，但是却无法补全，执行`git submodule update --init --recursive`也无效。这时候需要强制更新 `-f`。

```Bash
git submodule update --init --recursive -f
```



## 查看某个文件从某个点开始回溯的历史变动路径

用以下命令打开gitk图形用户界面。

```Bash
gitk <分支/tag/commit> <文件路径>
```
