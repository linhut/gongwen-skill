#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.font_cmds -- font management commands.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

GONGWEN_FONTS = {
    "方正小标宋简体": "方正小标宋简.TTF",
    "仿宋_GB2312": "仿宋_GB2312.ttf",
    "楷体_GB2312": "楷体_GB2312.TTF",
}


def _get_fonts_dir() -> Path:
    """定位项目内 assets/fonts/ 目录。"""
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _download_font(ttf_file: str, dest: Path) -> bool:
    """从 GitHub 下载字体文件到 dest，返回是否成功。"""
    import urllib.request
    import urllib.error
    url = f"{FONTS_DOWNLOAD_BASE}/{ttf_file}"
    try:
        print(f"  ⬇️  下载 {ttf_file} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "gongwen-skill"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
        # SEC-V168-03 修复：完整性校验——字体文件应 >1MB
        if len(data) < 1_000_000:
            print(f"  ❌ 下载文件过小 ({len(data)} bytes)，可能不完整")
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print(f"  📦 已下载: {dest} ({len(data) / 1024:.0f}KB)")
        return True
    except Exception as e:
        print(f"  ❌ 下载失败: {e}")
        return False


def _ensure_font_file(ttf_file: str, fonts_dir: Path) -> Path | None:
    """确保字体文件存在：优先用本地 assets/fonts/，不存在则从 GitHub 下载到缓存目录。"""
    local = fonts_dir / ttf_file
    if local.exists() and local.stat().st_size > 10000:
        return local
    # 本地缺失，尝试下载到用户缓存目录
    try:
        from config import APP_DATA_DIR
        cache_dir = APP_DATA_DIR / "fonts"
    except Exception:
        cache_dir = Path.home() / ".gongwen-skill" / "fonts"
    cached = cache_dir / ttf_file
    if cached.exists() and cached.stat().st_size > 10000:
        return cached
    if _download_font(ttf_file, cached):
        return cached
    return None


def _get_windows_fonts_dir() -> Path:
    """Windows 用户字体目录。"""
    import os
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Microsoft" / "Windows" / "Fonts"


def _is_font_installed(font_name: str) -> bool:
    """检查字体是否已安装（Windows 注册表检查，其他平台检查字体目录）。"""
    import platform
    if platform.system() == "Windows":
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    key = winreg.OpenKey(hive,
                                         r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
                except OSError:
                    continue
                for i in range(512):
                    try:
                        name, _val, _typ = winreg.EnumValue(key, i)
                        if font_name in name:
                            winreg.CloseKey(key)
                            return True
                    except OSError:
                        break
                winreg.CloseKey(key)
        except Exception:
            pass
        return False
    else:
        # Linux/macOS: 检查常见字体目录
        font_dirs = [
            Path.home() / ".fonts",
            Path.home() / ".local" / "share" / "fonts",
            Path("/usr/share/fonts"),
            Path("/usr/local/share/fonts"),
        ]
        for d in font_dirs:
            if d.exists():
                for f in d.rglob("*.ttf"):
                    if font_name.replace(" ", "").lower() in f.stem.replace(" ", "").lower():
                        return True
                for f in d.rglob("*.TTF"):
                    if font_name.replace(" ", "").lower() in f.stem.replace(" ", "").lower():
                        return True
        return False


def _install_font_file(font_path: Path, font_name: str) -> bool:
    """安装单个字体文件到系统。返回是否成功。"""
    import platform
    import shutil

    if not font_path.exists():
        print(f"  ❌ 字体文件不存在: {font_path}")
        return False

    system = platform.system()

    if system == "Windows":
        # Windows: 复制到用户字体目录（不需要管理员权限）
        fonts_dir = _get_windows_fonts_dir()
        fonts_dir.mkdir(parents=True, exist_ok=True)
        dest = fonts_dir / font_path.name

        # 如果已存在且大小相同，确保注册表项存在后跳过
        if dest.exists() and dest.stat().st_size == font_path.stat().st_size:
            # 确保注册表项存在
            try:
                import winreg
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
                reg_name = f"{font_name} (TrueType)"
                winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, dest.name)
                winreg.CloseKey(key)
            except Exception:
                pass
            print(f"  ⏭️  {font_name}: 已存在（跳过）")
            return True

        shutil.copy2(font_path, dest)

        # 注册字体（用户级注册表，不需要管理员权限）
        try:
            import winreg
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                   r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
            reg_name = f"{font_name} (TrueType)"
            winreg.SetValueEx(key, reg_name, 0, winreg.REG_SZ, dest.name)
            winreg.CloseKey(key)
        except Exception as e:
            _logger.warning(f"注册字体 {font_name} 到注册表失败: {e}")

        print(f"  ✅ {font_name}: 已安装 → {dest}")
        return True

    elif system == "Darwin":
        # macOS: 复制到 ~/Library/Fonts/
        fonts_dir = Path.home() / "Library" / "Fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        dest = fonts_dir / font_path.name
        if dest.exists() and dest.stat().st_size == font_path.stat().st_size:
            print(f"  ⏭️  {font_name}: 已存在（跳过）")
            return True
        shutil.copy2(font_path, dest)
        print(f"  ✅ {font_name}: 已安装 → {dest}")
        return True

    else:
        # Linux: 复制到 ~/.local/share/fonts/
        fonts_dir = Path.home() / ".local" / "share" / "fonts"
        fonts_dir.mkdir(parents=True, exist_ok=True)
        dest = fonts_dir / font_path.name
        if dest.exists() and dest.stat().st_size == font_path.stat().st_size:
            print(f"  ⏭️  {font_name}: 已存在（跳过）")
            return True
        shutil.copy2(font_path, dest)
        # 刷新字体缓存
        try:
            import subprocess
            subprocess.run(["fc-cache", "-f", str(fonts_dir)],
                           capture_output=True, timeout=30)
        except Exception:
            pass
        print(f"  ✅ {font_name}: 已安装 → {dest}")
        return True


def cmd_font(args):
    """公文标准字体管理：安装/检查/列出项目内置字体。"""
    action = getattr(args, "action", "list")
    fonts_dir = _get_fonts_dir()

    if action == "list":
        print("📋 公文标准字体清单：")
        print(f"{'─' * 60}")
        for font_name, ttf_file in GONGWEN_FONTS.items():
            ttf_path = fonts_dir / ttf_file
            has_file = "📦 内置" if ttf_path.exists() else "🌐 可下载"
            installed = _is_font_installed(font_name)
            status = "✅ 已安装" if installed else "❌ 未安装"
            print(f"  {font_name:<16} {has_file}  {status}")
        print(f"{'─' * 60}")
        print("提示：运行 `python -m gongwen font install` 安装缺失字体")
        print("     字体来源：项目内置 assets/fonts/ 或 GitHub 自动下载")
        return

    if action == "check":
        print("🔍 字体安装状态检查：")
        print(f"{'─' * 60}")
        all_ok = True
        for font_name, ttf_file in GONGWEN_FONTS.items():
            installed = _is_font_installed(font_name)
            ttf_path = fonts_dir / ttf_file
            has_file = ttf_path.exists()
            if not installed:
                all_ok = False
            status = "✅" if installed else "❌"
            source = "（项目内置）" if has_file else "（可从 GitHub 下载）"
            print(f"  {status} {font_name:<16} {source}")
        print(f"{'─' * 60}")
        if all_ok:
            print("✅ 所有公文标准字体已安装")
        else:
            print("❌ 部分字体未安装，运行 `python -m gongwen font install` 安装")
        return 0 if all_ok else 1

    if action == "install":
        print("📥 安装公文标准字体...")
        print(f"{'─' * 60}")

        installed_count = 0
        for font_name, ttf_file in GONGWEN_FONTS.items():
            # 优先用项目内置 assets/fonts/，不存在则从 GitHub 下载
            ttf_path = _ensure_font_file(ttf_file, fonts_dir)
            if ttf_path is None:
                print(f"  ❌ {font_name}: 字体文件不可用（本地缺失且下载失败）")
                continue
            if _install_font_file(ttf_path, font_name):
                installed_count += 1

        print(f"{'─' * 60}")
        print(f"✅ 安装完成: {installed_count}/{len(GONGWEN_FONTS)} 个字体")
        print("⚠️  新安装的字体可能需要重启 Word/WPS 才能生效")
        return 0 if installed_count > 0 else 1

    print(f"未知的 font action: {action}")
    return 1
