import os
import shutil
import fnmatch

REMOTE = False

def main():
    print("Starting deployment to dev environment...")

    source_dir = os.path.dirname(os.path.abspath(__file__))
    addon_id = "plugin.cloudstorage.webdav.refresh"

    if REMOTE:
        target_dir = os.path.join(r"F:\storage\.kodi\addons", addon_id)
    else:
        appdata = os.environ.get('APPDATA', '')
        target_dir = os.path.join(appdata, 'Kodi', 'addons', addon_id)

    print(f"Source Dir: {source_dir}")
    print(f"Target Dir: {target_dir}\n")

    if not os.path.exists(target_dir):
        print("Creating target directory...")
        os.makedirs(target_dir, exist_ok=True)

    exclude_dirs = {'.git', '.vscode', '.idea', '__pycache__', 'dist', 'tests', '.github'}
    exclude_files = ['*.pyc', '.gitignore', 'dev_deploy.ps1', 'dev_deploy.py', 'build_package.py', '.DS_Store']

    print("Cleaning target directory...")
    if os.path.exists(target_dir):
        for item in os.listdir(target_dir):
            item_path = os.path.join(target_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.unlink(item_path)
            except Exception:
                pass

    print("Copying files...")
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        rel_path = os.path.relpath(root, source_dir)
        if rel_path == '.':
            rel_path = ''

        for file in files:
            should_exclude = any(fnmatch.fnmatch(file, pattern) for pattern in exclude_files)
            if not should_exclude:
                src_file = os.path.join(root, file)
                dst_dir = os.path.join(target_dir, rel_path)
                dst_file = os.path.join(dst_dir, file)

                os.makedirs(dst_dir, exist_ok=True)
                shutil.copy2(src_file, dst_file)

                rel_file_path = os.path.join(rel_path, file) if rel_path else file
                print(f"  Copy: {rel_file_path}")

    print("\nDeployment Complete!")
    print(f"Target Dir: {target_dir}\n")
    print("Tip: Restart Kodi or Reload Addons to see changes.")

if __name__ == '__main__':
    main()
