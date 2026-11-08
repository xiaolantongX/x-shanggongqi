# x-shanggongqi

Windows 桌面 X 粉丝增长悬浮球：新粉 +1 提示、关注列表悬停、打开 X / 回关图标、「上供」文字按钮、今日新增。

## 目录

- `windows-ball/` — 悬浮球程序（Python + tkinter）
  - `fan_ball.py` — 主程序
  - `assets/` — X 图标与回关图标
  - `launch_ball.ps1` / `restart_ball.ps1` — 启动 / 重启
  - `install_shortcut.ps1` — 桌面快捷方式
  - `README.txt` — 本地安装说明
- `state.example.json` — 状态文件示例（复制为 `%LOCALAPPDATA%\XFanGrowth\state.json`）

## 运行

Windows 上需已安装 Python 3，并安装依赖：`pip install pillow`。

```powershell
cd windows-ball
.\launch_ball.ps1
```

状态文件默认读取 `%LOCALAPPDATA%\XFanGrowth\state.json`（由巡检同步写入）。
