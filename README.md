# AutoExcel Generate

面向约 20 名学生的在线 Excel 填写系统。学生分别扫描“起点、破、扩、筛”四个固定二维码，在网页中填写原 Excel 工作表对应区域；教师按学号查看四张表的完成情况，并可下载单个学生或全班的 Excel。

## 已实现

- 四个固定学生入口：`/student/qidian`、`/student/po`、`/student/kuo`、`/student/shai`
- 按原始 Excel 的行列、合并单元格、颜色、边框、字号和行列尺寸渲染
- 姓名和学号必填；同一学号同一阶段再次提交会覆盖旧结果
- 学生可读取旧内容后继续修改
- “筛”阶段自动读取该学生在“扩”阶段填写的四个候选方案
- SQLite WAL 并发存储，适合约 20 人同时使用
- 教师密码登录、搜索、完成状态筛选、在线查看
- 下载单个学生的完整原版 Excel
- 批量下载全班 ZIP，每名学生一个 Excel
- 教师端生成和下载四个二维码
- Docker 部署及持久化数据卷

## 本地运行

需要 Python 3.11 或更高版本。推荐使用 `uv`：

```bash
uv sync --extra dev
export TEACHER_PASSWORD='请设置教师密码'
export SESSION_SECRET='请设置至少32位随机字符串'
export PUBLIC_BASE_URL='http://localhost:8000'
export QR_BASE_URL='http://localhost:8000'
export COOKIE_SECURE='false'
uv run uvicorn app.main:app --reload
```

打开 `http://localhost:8000`。教师入口为 `http://localhost:8000/teacher/login`。

也可以使用 Docker Compose：

```bash
cp .env.example .env
# 编辑 .env 后运行
docker compose up --build
```

## 公网部署

该项目可部署到支持 Docker 和持久化磁盘的平台或学校服务器。公网部署必须满足：

1. 使用固定 HTTPS 域名，并将 `PUBLIC_BASE_URL` 设置为该域名，例如 `https://innovation.example.edu`。
2. 如需微信直接扫码访问国内镜像，将 `QR_BASE_URL` 设置为镜像域名，例如 `https://innovation.example.cn`；二维码会统一使用该地址，网页自身仍可保留 `PUBLIC_BASE_URL`。
3. 设置强 `TEACHER_PASSWORD`。
4. 设置至少 32 位随机 `SESSION_SECRET`。
5. 设置 `COOKIE_SECURE=true`。
6. 将 `/data` 挂载到持久化磁盘；否则服务器重启可能丢失学生提交。
7. 备份 `/data/submissions.db`。

`QR_BASE_URL`（未设置时回退到 `PUBLIC_BASE_URL`）确定后，教师端生成的四个二维码可长期使用。更换域名后需要重新下载二维码。

## 数据与模板

- 原始模板位于 `app/assets/template.xlsx`，系统下载时会复制该文件并写入学生答案，不会修改模板本身。
- 数据存储在 `DATA_DIR/submissions.db`。
- 当前模板区域：起点（第 5–7 行）、破（第 9–14 行）、扩（第 16–26 行）、筛（第 28–40 行）。
- 如果后续更换模板，需要同步检查 `app/template_service.py` 中的区域和可填写单元格配置。

## 测试

```bash
uv run pytest -q
```
