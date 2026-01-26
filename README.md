# WebDAV 刷新插件 (plugin.cloudstorage.webdav.refresh)

kodi插件，简单实现了 WebDAV 的手动刷新接口，目前只实现了 OpenList。  

写这个插件的主要是不想进webdav目录时看到那令人窒息的转圈和卡顿。  
目前看起来唯一的解法就是把存储的缓存过期时间设的超级大，然后在kodi手动刷新

### 使用方法

1.  安装插件，然后将按键绑定到 `RunScript(plugin.cloudstorage.webdav.refresh)`
2.  在 Kodi 中进入想要刷新的 WebDAV (OpenList) 目录按键即可
3.  **(可选) 递归刷新**：如果希望刷新当前目录及其下所有子目录，请使用参数 `recursive=true`：
    `RunScript(plugin.cloudstorage.webdav.refresh, recursive=true)`

### 注意事项

1.  需要 OpenList服务端口是绑定的是默认的 5244 端口
2.  Kodi 添加 OpenList webdav源时用的是管理员账号（反正就是在网页上有刷新权限的，没细研究 OpenList 的权限管理）
