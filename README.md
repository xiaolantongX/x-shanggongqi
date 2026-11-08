# x-shanggongqi

> x关注窗口，及时回关，支持上供

Windows 桌面悬浮球：半透明玻璃胶囊 + 官方 X 标，用于查看粉丝增长、悬停关注列表、一键打开主页 / 回关，并记录「上供」。

面向账号 [@tcblue001](https://x.com/tcblue001)（GitHub [@xiaolantongX](https://github.com/xiaolantongX)）。仓库：https://github.com/xiaolantongX/x-shanggongqi

---

## 功能

| 能力 | 说明 |
|------|------|
| 玻璃胶囊浮层 | 置顶半透明胶囊，显示粉丝总数与「今日 +N」 |
| 新粉 +1 Toast | 检测到新粉时弹出提示动画 |
| 悬停关注列表 | 鼠标悬停胶囊展开最近粉丝列表（头像 / 昵称 / 句柄） |
| 打开 X（图标） | 打开对方主页 `https://x.com/{username}` |
| 回关（图标） | 打开 X 官方关注意图页 `https://x.com/intent/follow?screen_name=…` |
| 上供（文字按钮） | 弹窗备注后写入本地 `tribute_log`，并 Toast「已记上供」 |
| 拖动 / 菜单 | 左键拖动；双击或右键可打开增长面板；右键可退出 |
| 状态同步目录 | 读写 `%LOCALAPPDATA%\XFanGrowth\state.json` |

> **分工说明**：Grok Bot 巡检负责拉取粉丝并写入 `state.json`；本浮层只负责读取、展示与本地操作（打开链接、记上供），不直接调用 X API。

---

## 目录结构

```
.
├── README.md
├── state.example.json          # 状态文件示例（勿提交真实粉丝隐私）
└── windows-ball/
    ├── fan_ball.py             # 主程序（Python + tkinter + Pillow）
    ├── assets/                 # X 标、打开 / 回关图标
    ├── launch_ball.ps1         # 启动（杀旧进程后启动）
    ├── restart_ball.ps1        # 重启（经 VBS 无黑窗）
    ├── start_fan_ball.vbs      # 无控制台窗口启动
    ├── install_shortcut.ps1    # 创建桌面快捷方式
    ├── clear_latest.ps1        # 清理调试用截图等
    └── README.txt              # 本地简要说明
```

运行时程序与资源应放在：

```
%LOCALAPPDATA%\XFanGrowth\
  fan_ball.py
  assets\
  *.ps1 / *.vbs
  state.json                    # 由巡检同步；浮层读取
  avatars\                      # 头像缓存（自动创建）
```

---

## 环境要求

- Windows 10 / 11
- Python 3（推荐 `py -3` 启动器）
- 依赖：`pillow`（缺失时主程序会尝试自动 `pip install`）

```powershell
py -3 -m pip install pillow -q
```

---

## 安装与运行

1. 将本仓库的 `windows-ball/` 内文件复制到 `%LOCALAPPDATA%\XFanGrowth\`（保留 `assets/` 子目录）。
2. 可选：把 `state.example.json` 复制为 `%LOCALAPPDATA%\XFanGrowth\state.json` 作为空模板；日常由 Grok Bot 巡检覆盖写入。
3. 安装依赖并启动：

```powershell
cd $env:LOCALAPPDATA\XFanGrowth
py -3 -m pip install pillow -q
.\launch_ball.ps1          # 或 .\restart_ball.ps1（无黑窗）
.\install_shortcut.ps1     # 可选：桌面「X-Fan-Ball」快捷方式
```

也可双击 `start_fan_ball.vbs` 静默启动。

---

## 状态文件 `state.json`

路径：`%LOCALAPPDATA%\XFanGrowth\state.json`  
字段示例见仓库根目录 [`state.example.json`](./state.example.json)（占位符，不含真实粉丝信息）。

| 字段 | 含义 |
|------|------|
| `account` | 本账号信息（`id` / `username` / `name` / `followers_count`） |
| `follower_ids` | 已知粉丝 ID 列表 |
| `followers` | 关注列表展示用对象（含 `id`、`username`、`name`、`profile_image_url` 等） |
| `new_followers` | 本轮巡检发现的新粉（浮层消费后清空） |
| `toast_queue` | 待弹出的 +1 提示队列 |
| `daily` | 今日新增：`{ date, count, names }`（按 Asia/Shanghai 日期滚动） |
| `tribute_log` | 上供记录（本地追加） |
| `baseline_at` / `last_check_at` / `updated_at` | 基线与巡检时间戳（若存在） |

请勿将含真实粉丝隐私的 `state.json` 提交到公开仓库。

---

## 操作速查

- **左键拖动**：移动胶囊
- **悬停**：展开关注列表
- **列表按钮**：X 图标 → 打开主页；人形+号图标 → 回关；「上供」→ 记备注
- **双击胶囊**：打开增长面板（Cursor Canvas）
- **右键**：打开增长面板 / 关注列表 / 退出

---

## License

私有用途，按仓库所有者约定使用。
