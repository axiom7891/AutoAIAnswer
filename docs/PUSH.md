# 把项目推到 GitHub（只用点两下）

这个脚本做三件事：设置远端仓库 → 推送 `main` → 推送 `v0.2.63` 标签（标签会触发 macOS 打包工作流）。

## 前提

1. 有一个 GitHub 账号（没有先去 https://github.com/signup 注册，免费）。
2. 在 GitHub 上新建一个**空仓库**（不要勾 README / .gitignore / license），拿到形如
   `https://github.com/你的用户名/仓库名.git` 的地址。

## 操作

1. 双击桌面的 **上传到GitHub.bat**（或仓库里的 `push-to-github.bat`）。
2. 粘贴仓库地址，回车。
3. 首次推送会弹出浏览器要求登录 GitHub：点 **Sign in**，用你的账号授权（Git Credential Manager，令牌只存在本机）。
4. 看到 `Everything up-to-date` / `new branch` 之类的输出、脚本提示「完成」即可关闭窗口。

## 之后

- 打开仓库页面 → **Actions** 标签，能看到 `Build macOS app` 正在跑（约 8–15 分钟）。
- 跑完后右侧 **Releases** 里会出现 `v0.2.63`，资产是 `QQMusic-macOS-arm64.zip` 和 `SHA256SUMS-arm64.txt`。
- 以后更新版本只需要：改代码 → `git add -A && git commit -m "..."` → `git tag v0.2.64` → 再跑一次这个脚本。

## 失败怎么办

| 提示 | 处理 |
|---|---|
| `Authentication failed` | 浏览器登录没完成，重跑脚本，注意浏览器里的授权页 |
| `Could not resolve host` / `Failed to connect` | 网络问题；脚本会自动尝试系统代理，仍失败就开代理再跑 |
| `remote origin already exists` | 脚本会先删再加，可忽略 |
| `Updates were rejected` | 远端仓库不是空的（建仓库时勾了 README）；删掉仓库重建，或先 `git pull --rebase origin main` |
| 仓库 Settings → Actions 提示无权限 | Settings → Actions → General → Workflow permissions 选 Read and write |
