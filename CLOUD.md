# 安全微伴云端运行

入口：仓库 Actions → 安全微伴云端运行 → Run workflow。

## 首次使用
1. 先选 environment-check，检查依赖、Python 入口、验证码模型和 Chrome。
2. 在 Settings → Secrets and variables → Actions → New repository secret 添加：
   - WB_USERNAME：安全微伴账号。
   - WB_PASSWORD：安全微伴密码。
   也可改用 WB_USER_ID + WB_TOKEN；两种方式都配置时优先使用 Token。
3. 选 login-check，学校填写全称，默认福建师范大学。
4. 登录检查通过后，可选 study 启动课程任务。此入口关闭考试功能。

账号与密码不要写进源码、运行参数、Issue 或截图。Secrets 只在账号任务步骤通过环境变量提供；环境检查不读取账号。
本项目是公开 Fork，Actions 日志可公开查看，GitHub 会屏蔽与 Secrets 精确匹配的内容；程序产生的其他个人信息仍需留意。
不上传原始日志、配置或账号缓存。运行结束清理临时数据。

## 范围与限制
- 每次手动运行，最多 180 分钟；不需要本地电脑保持开机。
- 同时只执行一个工作流，避免同一账号并发。
- environment-check 通过只表示环境可用，不表示账号或课程流程已验证。
- login-check 不学习、不交卷；Token 方式会向平台查询项目列表以验证 Token。
- study 复用上游课程逻辑，平台拦截、验证码或接口变化可能导致课程跳过；实际完成情况以安全微伴页面为准。
- 若运行时间不足，可再次手动启动，程序按平台已有完成记录判断待学课程。
