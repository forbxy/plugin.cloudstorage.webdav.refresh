import hashlib
import urllib.parse
import xbmc
import xbmcgui
import json
import posixpath
import traceback
import os

try:
    import requests
except ImportError:
    pass

class OpenListRefresher:
    STATIC_HASH_SALT = "https://github.com/alist-org/alist"

    def __init__(self, base_url, username, password):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.token = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }
        # Update Referer based on base_url
        self.headers["Referer"] = "{}/@login?redirect=%2F%40manage".format(self.base_url)

    def _get_static_hash(self):
        text = "{}-{}".format(self.password, self.STATIC_HASH_SALT)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def login(self):
        login_url = "{}/api/auth/login/hash".format(self.base_url)
        hashed_pwd = self._get_static_hash()
        
        login_payload = {
            "username": self.username,
            "password": hashed_pwd,
            "otp_code": ""
        }
        
        xbmc.log("[WebDAV Refresh] Logging into: {}".format(login_url), xbmc.LOGINFO)

        try:
            r = requests.post(login_url, json=login_payload, headers=self.headers, timeout=10)
            data = r.json()

            if data.get('code') != 200:
                msg = data.get('message', 'Unknown Error')
                xbmcgui.Dialog().notification('openlist登录失败', str(msg), xbmcgui.NOTIFICATION_ERROR)
                return False
                
            self.token = data.get('data', {}).get('token')
            if not self.token:
                xbmcgui.Dialog().notification('openlist登录失败', '响应中没有Token', xbmcgui.NOTIFICATION_ERROR)
                return False
            
            self.headers['Authorization'] = self.token
            return True

        except Exception as e:
            xbmcgui.Dialog().notification('openlist登录错误', str(e), xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("OpenList Login Exception: " + str(e), xbmc.LOGERROR)
            return False

    def refresh(self, raw_path, recursive=False):
        if not self.token:
            return False

        # Path processing logic specific to OpenList/AList (strips /dav prefix usually)
        # raw_path comes from urllib.parse.path, e.g. /dav/folder
        
        clean_raw_path = raw_path.strip('/')
        path_parts = clean_raw_path.split('/')
        
        # Logic: if path is like "/dav/folder", parts=["dav", "folder"]. We want "/folder".
        if len(path_parts) > 0 and path_parts[0]:
             # Join from index 1 to skip 'dav' prefix
             real_path = "/" + "/".join(path_parts[1:])
        else:
             real_path = "/"
             
        # URL Decode
        real_path = urllib.parse.unquote(real_path)

        if recursive:
             xbmcgui.Dialog().notification('OpenList', '开始递归刷新...', xbmcgui.NOTIFICATION_INFO, 1000)
        else:
             xbmcgui.Dialog().notification('OpenList', '开始刷新...', xbmcgui.NOTIFICATION_INFO, 1000)

        success = self._do_refresh(real_path, recursive)
        
        if success:
             xbmcgui.Dialog().notification('成功', 'openlist刷新成功', xbmcgui.NOTIFICATION_INFO, 1000)
        
        return success

    def _do_refresh(self, real_path, recursive):
        if real_path == '/' or real_path == '':
             xbmcgui.Dialog().notification('openlist刷新', '跳过根目录', xbmcgui.NOTIFICATION_INFO, 1000)
             # Return True to indicate no error, just skipped
             return True
        
        xbmc.log("[WebDAV Refresh] Refreshing Path: {} (Recursive: {})".format(real_path, recursive), xbmc.LOGINFO)

        refresh_url = "{}/api/fs/list".format(self.base_url)
        refresh_payload = {
            "path": real_path,
            "password": "",
            "page": 1,
            "per_page": 0,
            "refresh": True
        }
        
        try:
            r_refresh = requests.post(refresh_url, json=refresh_payload, headers=self.headers, timeout=30)
            res_refresh = r_refresh.json()
            
            if res_refresh.get('code') == 200:
                # Recursive Logic
                if recursive:
                    sub_dirs = [os.path.join(real_path, item.get('name')) for item in res_refresh['data'].get('content', []) if item.get('is_dir')]
                    if sub_dirs:
                        for d in sub_dirs:
                            sub_path = d if d.endswith('/') else d + '/'
                            if sub_path:
                                self._do_refresh(sub_path, True)
                return True
            else:
                msg = res_refresh.get('message', 'Failed')
                xbmcgui.Dialog().notification('openlist刷新失败', str(msg), xbmcgui.NOTIFICATION_ERROR)
                xbmc.log("OpenList Refresh Failed: " + str(msg), xbmc.LOGERROR)
                return False

        except Exception as e:
            xbmcgui.Dialog().notification('openlist刷新错误', str(e), xbmcgui.NOTIFICATION_ERROR)
            xbmc.log("OpenList Refresh Exception: " + traceback.format_exc(), xbmc.LOGERROR)
            return False


    def logout(self):
        if not self.token:
            return

        logout_url = "{}/api/auth/logout".format(self.base_url)
        try:
            requests.get(logout_url, headers=self.headers, timeout=5)
            xbmc.log("[WebDAV Refresh] openlist Logout success", xbmc.LOGINFO)
        except Exception as e_logout:
            xbmc.log("[WebDAV Refresh] openlist Logout warning: {}".format(traceback.format_exc()), xbmc.LOGWARNING)