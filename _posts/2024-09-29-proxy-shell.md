# 使用proxy

假设代理服务器安装在本机127.0.0.1的地址上，在~/.profile中添加如下代码。

```shell
function proxy() {
    hostip=$(cat /etc/resolv.conf | grep nameserver | awk '{ print $2 }')
    #hostip=127.0.0.1
    ALL_PROXY=socks5://$hostip:10808 $@
    #https_proxy=http://$hostip:10809 http_proxy=http://$hostip:10809 $@
    echo $ALL_PROXY
}
```

如果使用代理服务器访问外网，用`proxy`开头后面跟命令，例如：
```
proxy git submodule update --init --recursive --force
```
