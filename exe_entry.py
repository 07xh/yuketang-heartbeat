"""Recovered console launcher. Original EXE bytecode is not fully decompiled.
Preserves existing main.py without editing it. Settings are local-only.
"""
import os
import sys
from pathlib import Path

def home():
    return Path(os.environ.get("YKT_HOME") or Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent)

def cfg_path():
    return home() / ".env"

DEFAULTS = {"VIDEO_SPEED":"1.5","TEST_VIDEO_COUNT":"5","TEST_MODE":"false","MAX_CONCURRENT_VIDEOS":"3","COMPLETION_THRESHOLD":"90"}
def read_cfg():
    data=DEFAULTS.copy()
    if cfg_path().exists():
        for line in cfg_path().read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k,v=line.split("=",1)
                data[k.strip()]=v.strip().strip('"').strip("'")
    return data

def save_cfg(changes):
    p=cfg_path()
    lines=p.read_text(encoding="utf-8-sig").splitlines() if p.exists() else []
    seen=set()
    for i,line in enumerate(lines):
        if "=" in line and not line.lstrip().startswith("#"):
            k=line.split("=",1)[0].strip()
            if k in changes:
                lines[i]=k+"="+changes[k];seen.add(k)
    lines.extend(k+"="+v for k,v in changes.items() if k not in seen)
    p.write_text("\n".join(lines)+"\n",encoding="utf-8")

def settings():
    opts=[("VIDEO_SPEED","视频速度",0.1,4),("TEST_VIDEO_COUNT","视频数量",1,10000),("MAX_CONCURRENT_VIDEOS","并发数量",1,32),("COMPLETION_THRESHOLD","本地完成判定百分比",0,100)]
    while True:
        data=read_cfg()
        print("\n=== 设置管理 ===")
        for i,(key,label,*_) in enumerate(opts,1):
            print(f"[{i}] {label}: {data.get(key,'')}")
        print("[0] 返回")
        choice=input("选择: ").strip()
        if choice=="0":return
        if not choice.isdigit() or not 1<=int(choice)<=len(opts):continue
        key,label,lo,hi=opts[int(choice)-1]
        raw=input(f"{label}（{lo}~{hi}）: ").strip()
        try:
            value=float(raw)
            import math
            if not math.isfinite(value) or not lo<=value<=hi:raise ValueError()
            if key in ("TEST_VIDEO_COUNT","MAX_CONCURRENT_VIDEOS"):
                if not value.is_integer():raise ValueError()
                raw=str(int(value))
            save_cfg({key:raw})
            os.environ[key]=raw
            print("设置已保存。")
        except ValueError:
            print("输入无效。")

def main_menu():
    os.environ["YKT_HOME"]=str(home())
    for k,v in read_cfg().items():
        os.environ.setdefault(k,v)
    while True:
        print("\n=== 雨课堂助手（恢复版） ===")
        print("[1] 运行现有业务程序  [s] 设置  [0] 退出")
        choice=input("选择: ").strip().lower()
        if choice=="0":return
        if choice=="s":settings()
        elif choice=="1":
            print("即将调用 GitHub 原有 main.py；此操作可能向服务端发送请求。")
            if input("确认运行？输入 YES: ").strip()!="YES":continue
            import main as backend
            backend.main()
        else:print("未知选项")
if __name__=="__main__":
    main_menu()
