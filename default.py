import sys
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import urllib.parse
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    xbmcgui.Dialog().notification('WebDAV刷新', '缺少 script.module.requests 模块', xbmcgui.NOTIFICATION_ERROR, 1000)
    sys.exit(1)

# Import implementations
from refresh_openlist import OpenListRefresher

def _search_passwords_xml(pass_file, target_path, t_host, t_path):
    """在单个 passwords.xml 中搜索匹配 target_path 的凭证。"""
    if not xbmcvfs.exists(pass_file):
        return None, None

    try:
        f = xbmcvfs.File(pass_file)
        xml_content = f.read()
        f.close()
        root = ET.fromstring(xml_content)

        for path_node in root.findall('path'):
            from_node = path_node.find('from')
            to_node = path_node.find('to')
            if from_node is None or to_node is None:
                continue
            from_val = from_node.text
            to_val = to_node.text
            if not from_val or not to_val:
                continue

            xbmc.log("[WebDAV Refresh] Checking: {} against {}".format(from_val, target_path), xbmc.LOGDEBUG)
            try:
                from_parsed = urllib.parse.urlparse(from_val)
                if t_host != from_parsed.hostname:
                    continue
                f_path = urllib.parse.unquote(from_parsed.path).rstrip('/')
                if t_path == f_path or t_path.startswith(f_path + '/'):
                    xbmc.log("[WebDAV Refresh] Match: {} for {}".format(from_val, target_path), xbmc.LOGINFO)
                    to_parsed = urllib.parse.urlparse(to_val)
                    if to_parsed.username and to_parsed.password:
                        return to_parsed.username, to_parsed.password
            except Exception:
                pass
    except Exception as e:
        xbmc.log("[WebDAV Refresh] Error reading {}: {}".format(pass_file, e), xbmc.LOGWARNING)

    return None, None


def find_credentials_in_passwords_xml(target_path):
    """
    Search Kodi passwords.xml for credentials.
    Kodi itself checks current profile first, then falls back to master profile.
    """
    try:
        target_parsed = urllib.parse.urlparse(target_path)
        t_host = target_parsed.hostname
        t_path = urllib.parse.unquote(target_parsed.path).rstrip('/')
    except Exception:
        return None, None

    # 当前 profile 优先（和 Kodi 源码逻辑一致）
    profile_file = xbmcvfs.translatePath('special://profile/passwords.xml')
    user, password = _search_passwords_xml(profile_file, target_path, t_host, t_path)
    if user and password:
        return user, password

    # 回退到主 profile
    master_file = xbmcvfs.translatePath('special://masterprofile/passwords.xml')
    if master_file != profile_file:
        user, password = _search_passwords_xml(master_file, target_path, t_host, t_path)
        if user and password:
            return user, password

    return None, None

def strip_url_params(path):
    # Basic strip of URL parameters if present
    if '?' in path:
        return path.split('?', 1)[0]
    return path

def main():
    ADDON = xbmcaddon.Addon()
    # 0. Parse Arguments
    args = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            key, val = arg.split('=', 1)
            args[key.lower()] = val.strip()
            
    is_recursive = args.get('recursive', 'false').lower() == 'true'

    # 1. Get Context
    folder_path = xbmc.getInfoLabel('Container.FolderPath')
    
    # Basic validation
    if not folder_path:
        xbmcgui.Dialog().notification('WebDAV刷新', '未找到文件夹路径', xbmcgui.NOTIFICATION_WARNING, 1000)
        return

    # Parse URL
    try:
        parsed = urllib.parse.urlparse(folder_path)
    except Exception as e:
        xbmcgui.Dialog().notification('WebDAV刷新', 'URL解析错误', xbmcgui.NOTIFICATION_ERROR, 1000)
        return
    
    username = parsed.username
    password = parsed.password
    hostname = parsed.hostname
    port = parsed.port
    scheme = parsed.scheme
    
    # Normalize scheme
    if scheme.startswith('dav'):
        if scheme == 'davs':
            scheme = 'https'
        else:
            scheme = 'http'
    elif scheme in ['http', 'https']:
        pass
    else:
        xbmcgui.Dialog().notification('WebDAV刷新', '未识别的WebDAV源', xbmcgui.NOTIFICATION_WARNING, 1000)
        return
            
    if not hostname:
        xbmcgui.Dialog().notification('WebDAV刷新', '未找到主机名', xbmcgui.NOTIFICATION_ERROR, 1000)
        return
        
    # Attempt to find credentials if missing
    if not username or not password:
         xbmc.log("[WebDAV Refresh] No credentials in path, searching in passwords.xml...", xbmc.LOGINFO)
         found_user, found_pass = find_credentials_in_passwords_xml(folder_path)
         if found_user and found_pass:
             username = found_user
             password = found_pass
             xbmc.log("[WebDAV Refresh] Found credentials in passwords.xml", xbmc.LOGINFO)
         else:
             xbmcgui.Dialog().notification('WebDAV刷新', '未找到账号密码', xbmcgui.NOTIFICATION_ERROR, 1000)
             xbmc.log("[WebDAV Refresh] Missing username or password in URL: {}".format(folder_path), xbmc.LOGERROR)
             return

    # Construct Base URL
    base_url = "{}://{}".format(scheme, hostname)
    if port:
        base_url += ":{}".format(port)
    
    # === ROUTING ===
    # Check port to decide implementation
    
    # Default port normalization
    check_port = port
    if not check_port:
        if scheme == 'https': check_port = 443
        else: check_port = 80
        
    refresher = None
    
    configured_port = ADDON.getSettingInt("port")
    if configured_port < 1024 or configured_port > 65535:
        configured_port = 5244

    if int(check_port) == configured_port:
        xbmc.log("[WebDAV Refresh] Port {} detected, using OpenListRefresher".format(configured_port), xbmc.LOGINFO)
        refresher = OpenListRefresher(base_url, username, password)
    else:
        xbmcgui.Dialog().notification('WebDAV刷新', '端口不匹配: {} (配置: {})'.format(check_port, configured_port), xbmcgui.NOTIFICATION_WARNING, 1000)
        xbmc.log("[WebDAV Refresh] Unsupported port: {} (configured: {})".format(check_port, configured_port), xbmc.LOGWARNING)
        return

    # === EXECUTION ===
    try:
        if refresher.login():
            if refresher.refresh(parsed.path, recursive=is_recursive):
                # Only reload Kodi container if refresh trigger was successful
                # (Skipping root returns True, so it will reload too, which is fine)
                xbmc.executebuiltin("Container.Refresh")
                
    except Exception as e:
        xbmc.log("[WebDAV Refresh] Execution Error: {}".format(e), xbmc.LOGERROR)
    finally:
        refresher.logout()

if __name__ == '__main__':
    main()

