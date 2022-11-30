# Limit of Memory Map Count

You may encounter an error `ENOMEM`(error number 12) when allocate memory with `mmap`, while enough physical memory is available for use. Why the allocation fails when memory is enough for allocation? It is because the limit of number of memory maps. Memory maps are ranges of memory that allocated for a process. The memory maps of a process can be get from `/proc/<pid>/maps`, and `wc -l /proc/<pid>/maps` returns the number of maps.

By default the limit of number of maps is `65530`. Even the memory is enough, when the number of memory maps exceeds the limit, the `ENOMEM` error will happen.

The limit can be check by the command`cat /proc/sys/vm/max_map_count`.

We can change the limit by setting `vm.max_map_count`. The example of increasing the limit by 10 times is as following.

```shell
sudo vi /etc/sysctl.conf
# append a new line "vm.max_map_count=6553000"
sudo sysctl -p
```


**Reference**: 

[elasticsearch - How to increase vm.max_map_count? - Stack Overflow](https://stackoverflow.com/questions/42889241/how-to-increase-vm-max-map-count)
