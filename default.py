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

def find_credentials_in_passwords_xml(target_path):
    """
    Search Kodi passwords.xml (Network Locations) for credentials.
    """
    pass_file = xbmcvfs.translatePath('special://profile/passwords.xml')
    if not xbmcvfs.exists(pass_file):
        return None, None
        
    try:
        # Parse target once
        try:
            target_parsed = urllib.parse.urlparse(target_path)
            t_host = target_parsed.hostname
            t_path = urllib.parse.unquote(target_parsed.path).rstrip('/')
        except:
            return None, None

        f = xbmcvfs.File(pass_file)
        xml_content = f.read()
        f.close()
        
        # Simple string search if XML parsing fails or for robustness, but XML is better
        root = ET.fromstring(xml_content)
        
        # <passwords><path><from>...</from><to>...</to></path></passwords>
        for path_node in root.findall('path'):
            from_node = path_node.find('from')
            to_node = path_node.find('to')
            
            if from_node is None or to_node is None:
                continue
                
            from_val = from_node.text
            to_val = to_node.text
            
            if not from_val or not to_val:
                continue
            
            xbmc.log("[WebDAV Refresh] Checking password entry: {} against {}".format(from_val, target_path), xbmc.LOGDEBUG)

            # Fuzzy match logic
            try:
                from_parsed = urllib.parse.urlparse(from_val)
                f_host = from_parsed.hostname
                
                # Check Hostname
                if t_host != f_host:
                    continue
                
                # Check Path Prefix (normalized)
                f_path = urllib.parse.unquote(from_parsed.path).rstrip('/')
                
                # If from_path is root, it matches everything on that host
                # Or if target starts with from_path
                if t_path == f_path or t_path.startswith(f_path + '/'):
                    xbmc.log("[WebDAV Refresh] Loose match found: {} for {}".format(from_val, target_path), xbmc.LOGINFO)
                    to_parsed = urllib.parse.urlparse(to_val)
                    if to_parsed.username and to_parsed.password:
                         return to_parsed.username, to_parsed.password
            except:
                pass
    except Exception as e:
        xbmc.log("[WebDAV Refresh] Error reading passwords.xml: {}".format(e), xbmc.LOGWARNING)
        
    return None, None

def strip_url_params(path):
    # Basic strip of URL parameters if present
    if '?' in path:
        return path.split('?', 1)[0]
    return path

def main():
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
    
    if int(check_port) == 5244:
        xbmc.log("[WebDAV Refresh] Port 5244 detected, using OpenListRefresher", xbmc.LOGINFO)
        refresher = OpenListRefresher(base_url, username, password)
    else:
        xbmcgui.Dialog().notification('WebDAV刷新', '尚不支持端口 {}'.format(check_port), xbmcgui.NOTIFICATION_WARNING, 1000)
        xbmc.log("[WebDAV Refresh] Unsupported port: {}".format(check_port), xbmc.LOGWARNING)
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

