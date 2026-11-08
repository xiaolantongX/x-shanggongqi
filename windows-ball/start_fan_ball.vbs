Set sh = CreateObject("WScript.Shell")
localApp = sh.ExpandEnvironmentStrings("%LOCALAPPDATA%")
dir = localApp & "\XFanGrowth"
py = "py"
' Prefer py launcher; fall back to python
cmd = "cmd /c py -3 """ & dir & "\fan_ball.py"""
sh.Run cmd, 0, False
