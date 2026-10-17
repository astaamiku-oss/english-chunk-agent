# 英语语块学习 v1

一个支持本地运行和 Render 免费部署的 Web 应用。仅使用 Python 标准库、SQLite、原生 HTML/CSS/JavaScript，无需 pip、npm、模型密钥或外部资源。

## 运行

需要 Python 3.10 或以上（包含 sqlite3 模块）。在项目目录执行：

```bash
python3 app.py
```

浏览器打开 **http://127.0.0.1:8000**。首次启动自动创建 `learning.db` 并导入 20 个词、23 个义项、23 个语块；再次启动保留学习记录，不重复导入。Ctrl+C 停止。

```bash
python3 app.py --port 8080 --db /tmp/english-learning.db
```

默认监听 `0.0.0.0`，端口读取环境变量 `PORT`（默认 8000），`--port` 可覆盖。仅本机运行可加 `--host 127.0.0.1`。应用无账户认证，所有访客共享同一份学习记录与知识库，公网部署适合作为公开演示，请勿填写私人信息。页面采用米白背景、居中的圆角练习卡片，适配手机与电脑，并支持系统的减少动态效果设置。数据库时间统一保存为 UTC，页面显示本地时间。备份时停止应用并复制数据库；重置时停止应用、备份后删除数据库即可。

## Render 免费部署

[一键部署到 Render](https://render.com/deploy?repo=https://github.com/astaamiku-oss/english-chunk-agent)

由你在 Render 登录并确认部署。仓库根目录的 `render.yaml` 使用 Python 运行时、`free` 套餐，构建时运行测试，启动命令为 `python app.py --host 0.0.0.0`。无需配置密钥或安装第三方依赖；应用自动读取 Render 的 `PORT`。部署完成后，打开 Render 提供的 `https://…onrender.com` 公网地址。

每次启动自动建表；数据库为空时导入 20 个词、23 个义项、23 个语块，已有数据时不重复导入。数据库不提交到 GitHub。

Render 免费服务的文件系统是临时的：重新部署、重启或休眠后，SQLite 学习记录与编辑会丢失，后续启动恢复种子数据。空闲 15 分钟后会休眠，再次访问需等待唤醒。详见 [Render 免费套餐说明](https://render.com/docs/free)。所有访客共享记录；此配置不提供长期数据保存或独立用户账户。

## 在手机上打开

在运行项目的电脑上执行：

```bash
python3 app.py --host 0.0.0.0 --port 8000
```

1. 电脑打开 **http://127.0.0.1:8000**。
2. 手机和电脑连接同一个 Wi-Fi。
3. 查出电脑的局域网 IPv4 地址：Windows 执行 `ipconfig`；macOS 查看“系统设置 → Wi-Fi → 详细信息 → TCP/IP”；Linux 执行 `hostname -I`。
4. 假设地址为 `192.168.1.23`，手机浏览器打开 **http://192.168.1.23:8000**。请替换成电脑的实际地址，`0.0.0.0` 是监听地址，不是手机打开的地址。

手机和电脑共享同一份学习记录。电脑需保持应用运行。若手机打不开，请检查系统防火墙是否允许 Python 的 8000 端口，以及 Wi-Fi 是否开启了访客网络/设备隔离。仅在可信局域网使用此模式。

如果代码运行在远程开发环境，电脑的 localhost 不指向远程环境；请使用该环境提供的 **8000 端口转发/预览地址**。手机也需要可访问的转发地址，不能直接使用远程容器内网 IP。

## 使用

- **学习总览**：查看示例库规模、审核数量、词汇学习覆盖、到期任务、能力评分和最近练习。
- **基础词**：搜索词元、查看一词多义及关联语块，进行义项识别练习。
- **语块库**：按中文/英文、意图、场景和关联词筛选，查看句型、可替换位置、例句及来源。
- **练习与复习**：读中文提示，口头作答，可记录文字与错误；揭示答案后选择 0–3 分。四种能力分别保存，未练习项保持空值。听力维度供使用自有材料后记录，应用不提供音频。

排程：0 分在 10 分钟后重试；首次成功或失败后的成功在 1 天后复习；之后 1/2/3 分分别将间隔乘以 1.2/2/2.5。排程以学习对象为单位，四项能力共享下次复习时间；每次评分追加事件，保留历史。到期队列仅列出练过且到期的对象，新语块另外选择。这是简单可解释的 v1 排程，不是经过校准的记忆模型。

词汇覆盖只统计直接练过词或义项的词，不因练习相关语块而自动认定该词学过。知识库审核数量、学习覆盖、义项识别成功比例和语块主动调用成功比例分别展示。后两个比例按相应历史练习事件中评分 ≥ 2 的次数计算；自评不代表客观测量。20 个词是原创教学示例，未审核，不代表权威词频顺序或完整常见义项覆盖。

## 数据结构

详见 [schema.sql](schema.sql) 与 [可行性和范围](FEASIBILITY.md)。保留方案中的九张核心表，并增加 `audit_log`。`chunk_senses` 表达语块与义项多对多关系；`chunk_contexts` 关联意图、场景及例句。学习状态唯一键为 `(user_id, item_type, item_id)`，当前用户固定为 `local`。应用统一校验多态学习对象是否存在。

语块编辑记录版本、时间、来源及前后内容，使用版本号检测冲突。v1 API 支持语块新增和文本字段修改（含新增时建立义项/场景关联）；词、义项、分类的维护与现有关联重编排暂不提供写接口。Web 当前只提供浏览和学习，知识编辑由 API 完成。

## Agent JSON API

所有返回值都是 JSON；失败返回 `{"error":"说明"}`，使用 400/403/404/409/413/415/503 等状态码。写请求要求 `Content-Type: application/json`，最大 64 KiB，不开放跨域读写；本地脚本可直接调用，无需 Origin。当前只支持 `local` 用户，不接受 user_id 切换。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/words?q=get` | 搜索词元 |
| GET | `/api/words/1` | 词、义项和关联语块 |
| GET | `/api/chunks?q=理解&word_id=1&intent_id=1&scenario_id=1` | 筛选语块（参数均可省略） |
| GET | `/api/chunks/1` | 语块及完整关联 |
| GET | `/api/meta` | 意图及场景 ID |
| GET | `/api/review` | 到期学习对象 |
| GET | `/api/progress` | 当前学习状态 |
| GET | `/api/events` | 最近 100 次练习 |
| GET | `/api/stats` | 总览与能力指标 |
| POST | `/api/practice` | 提交评分并更新复习计划 |
| POST | `/api/chunks` | 查重并新增语块与关联 |
| PUT | `/api/chunks/1` | 根据版本号更新语块文本字段 |

下面命令仅调用你已经启动的本地应用，无外网请求：

```bash
curl http://127.0.0.1:8000/api/words/1
curl -X POST http://127.0.0.1:8000/api/practice \
  -H 'Content-Type: application/json' \
  -d '{"item_type":"chunk","item_id":1,"ability":"retrieval","grade":2,"answer":"I get it.","error":""}'
```

`item_type` 可为 `word`、`sense`、`chunk`；`ability` 可为 `recognition`、`listening`、`construction`、`retrieval`；`grade` 为整数 0–3；`answer` 和 `error` 可省略，各最多 4000 字。

新增语块示例（先用查询接口查重和确认分类/义项 ID）：

```json
{
  "expression": "I get your point.",
  "meaning_zh": "我理解你的观点。",
  "pattern": "I get {person}'s point.",
  "slots": ["person"],
  "usage_notes": "表示理解，不一定表示同意。",
  "source": "agent:manual-review",
  "sense_ids": [1],
  "contexts": [{"intent_id": 1, "scenario_id": 1, "example": "I get your point, but I need more time."}]
}
```

`expression` 忽略大小写唯一；关联失败则整个新增事务回滚。新增必需 `expression`、`meaning_zh`、`pattern`、`source`，其余可省略。修改先 GET 获取当前 `version`，再 PUT：

```json
{"version": 1, "meaning_zh": "我听懂了。", "source": "agent:correction"}
```

修改可包含 `expression`、`meaning_zh`、`pattern`、`slots`、`usage_notes`；其余字段保持原值。过期版本返回 409，需重新读取再决定修改。修改不能替换关联。审计保存在数据库 `audit_log` 中。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

6 项测试覆盖幂等导入、多对多关系、外键、间隔递增与失败重排、独立能力状态、追加历史、持久化、到期查询、统计、API 校验、重复约束、事务回滚、审计和版本冲突，以及静态页面/API 的 HTTP 请求处理。

已通过实际本地端口 HTTP 测试，并保留无需 socket 的 Handler 测试。另用本地 Chrome 在 1440×1000 桌面尺寸与 390×844 手机尺寸检查四个页面无横向溢出，完成揭示答案、评分、继续练习流程，无 JavaScript 异常。手机尺寸验证为浏览器模拟，未使用实体手机。

页面预览截图：[桌面首页](screenshots/desktop-home.png)、[桌面练习](screenshots/desktop-exercise.png)、[手机首页](screenshots/mobile-home.png)、[手机练习](screenshots/mobile-exercise.png)。参考站点访问工具返回不可访问，因此视觉参考来自用户提供的截图，未声称复刻原站动效。
