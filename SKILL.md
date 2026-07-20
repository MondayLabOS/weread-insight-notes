---
name: weread-insight-notes
description: 将微信读书的划线、个人笔记、本人点赞过的观点沉淀成结构化洞察笔记。适用于整理微信读书划线/笔记/书评/点赞观点、按章节分类、生成 Markdown/JSON/XML、同步到飞书/Obsidian/WPS 笔记/知识库、把读书笔记做成文档或思维导图。
---

# 微信读书洞察笔记

用于把一本微信读书里的阅读痕迹整理成可复用的结构化知识资产。默认先产出通用 Markdown/JSON，以及可发布到飞书的 XML；用户指定目标时，再同步到飞书、Obsidian、WPS 笔记或其他知识库。

核心输出格式：

```text
# 大章节

## 二级分类

1. 原文划线：用户在微信读书划过的原文
   > 我的笔记：用户自己写在这条划线上的想法
   > 我点赞的观点（作者）：用户自己点过赞的观点
```

## 依赖条件

- 微信读书 skill 已安装在 `~/.codex/skills/weread-skills`，或具备等价能力。
- `WEREAD_API_KEY` 已写入环境变量或 macOS 用户会话，可用 `launchctl getenv WEREAD_API_KEY` 检查。
- 只生成本地 Markdown/JSON/XML 时，不需要飞书授权。
- 如果要发布到飞书，`lark-cli` 必须已配置到目标飞书租户，并完成用户身份授权。
- 飞书文档使用 docs v2 命令：`lark-cli docs +create|+update --api-version v2`。

如果飞书授权因为租户不匹配而失败，不要为了省事改用 bot 身份创建文档，除非用户明确接受文档创建到 bot 应用所在租户。默认应重新配置 `lark-cli` 到目标租户。

## 工作流

1. 确认书籍。
   - 如果用户给了 `bookId`，直接使用。
   - 如果用户只给书名，先搜索；如果上下文里已经同步过书架，也可用 `/shelf/sync` 的结果匹配。

2. 必要时先阅读微信读书能力说明：
   - `~/.codex/skills/weread-skills/notes.md`
   - `~/.codex/skills/weread-skills/book.md`

3. 导出微信读书原始材料。
   - 优先使用 `scripts/export_weread_notes.py`。
   - 脚本会调用 `/book/chapterinfo`、`/book/bookmarklist`、`/review/list/mine`，必要时调用 `/book/readreviews`。
   - 脚本会输出 Markdown、JSON、XML 到指定目录。
   - 当用户要求包含“我点赞过的观点”时，使用 `--include-liked`。

4. 判断输出目标。
   - 用户没有指定目标时：只返回本地 Markdown/JSON/XML 文件路径。
   - 用户说 Obsidian：优先交付 Markdown，可放入用户指定 vault 或文件夹。
   - 用户说 WPS 笔记、语雀、Notion 或其他知识库：优先交付 Markdown；如有对应 CLI/API，再按目标系统发布。
   - 用户说飞书：使用生成的 XML 创建或更新飞书文档。

5. 发布到飞书时：
   - 新建文档：
     ```bash
     lark-cli docs +create --api-version v2 --as user --doc-format xml --content @exports/<file>.xml --parent-position my_library
     ```
   - 更新已有文档：
     ```bash
     lark-cli docs +update --api-version v2 --as user --doc <doc_token_or_url> --command overwrite --doc-format xml --content @exports/<file>.xml
     ```

6. 返回文件路径、发布链接和关键数量统计。

## 默认理解用户需求

当用户要求整理一本新书的读书笔记时，默认目标是：

```text
把《书名》的微信读书划线、我的笔记、我点赞过的观点整理成结构化洞察笔记。
按大章节做一级标题，按内容做二级分类。
每条记录以原文划线为主；如果这条划线有我的笔记或我点赞的观点，放在引用块里。
不要显示时间、位置、range、跳转链接和分割线。
默认先生成本地 Markdown、JSON 和 XML；只有用户指定飞书时才创建或更新飞书文档。
```

如果用户给了已有飞书文档 token 或 URL，确认这是目标文档后再覆盖更新。如果用户给的是本地文件夹路径，把 Markdown 写入该路径。如果用户要求新建飞书文档，在当前用户授权的目标租户里创建，并返回链接。

## 格式规则

- 微信读书的 `chapterUid` 往往是小节，不一定是大章。遇到很多 `level=2` 小节时，把内容归到最近的上一级 `level=1` 大章下面。
- 大章使用 `h1`。
- 二级分类使用 `h2`，根据书名、章节名、划线文本、个人笔记和点赞观点共同判断。
- 除非用户明确要求可追溯信息，否则不要显示时间、range、位置或深度链接。
- 每条记录优先展示原文划线。
- 如果某条划线有匹配的个人笔记，即 `chapterUid + range` 一致，把笔记放到这条划线下面的引用块，标签为 `我的笔记`。
- 如果某条个人笔记没有匹配到划线，保留为 `关联原文` 加 `我的笔记`，不要丢弃。
- 当用户说“点赞”时，必须区分：
  - `别人给我的笔记点赞`：默认不放进文档。
  - `我点赞过的观点`：只有 `/book/readreviews` 返回 `isLike=1` 时才放进文档。
- 对于“我点赞过的观点”，写在相关划线下面：
  ```text
  > 我点赞的观点（作者）：...
  ```
- 除非用户明确要总结性表达，否则不要生成 `围绕“某小节”...` 这类套话。
- 不要编造原文。如果划线本身不完整，保留微信读书返回的文本，或只在明确标注为总结时改写。

## 输出目标规则

| 目标 | 默认交付物 | 处理方式 |
|---|---|---|
| 本地归档 | Markdown、JSON、XML | 写入 `exports/` 或用户指定目录。 |
| Obsidian | Markdown | 保留 `#`、`##`、编号列表和引用块，避免飞书专用元素。 |
| WPS 笔记 | Markdown | 交付 Markdown；如用户提供导入方式，再按对应方式处理。 |
| 飞书 | XML + 文档链接 | 用 `lark-cli docs +create` 或 `+update` 发布。 |
| 其他知识库 | Markdown 优先 | 没有明确 API/CLI 时，只生成可复制导入的 Markdown。 |

## 不要放进文档的内容

- 默认不要放别人对用户笔记的评论。
- 不要把 `/review/list/mine` 里的 `likesCount` 或 `commentsCount` 当成用户关注点。
- 当存在原文划线时，不要把用户自己的笔记放成编号条目的主体；编号条目必须从原文划线开始。
- 不要在章节或分类之间添加分割线。
- 不要为了“补全”而编造缺失的原文。
- 用户没指定飞书时，不要主动要求飞书授权，也不要创建飞书文档。
- 当用户期望文档在自己租户里时，不要用 bot 身份创建飞书文档。

## 失败处理

| 触发条件 | 处理方式 |
|---|---|
| 缺少 `WEREAD_API_KEY` | 先让用户重新设置或授权微信读书 skill，再导出。 |
| 书名搜索结果不唯一 | 展示候选书籍，让用户选择，不要猜。 |
| `/book/readreviews` 调用失败 | 先继续生成划线和个人笔记版本，并说明“我点赞过的观点”未能纳入。 |
| 用户指定的本地目录不存在 | 询问是否创建目录；不要静默写到其他位置。 |
| 飞书授权指向错误租户 | 创建或更新文档前停止，让用户切换租户或应用授权。 |
| 用户提供已有飞书文档 token | 确认目标无误后，才使用 `+update --command overwrite` 覆盖更新。 |
| XML 上传失败 | 保留已生成的 Markdown/XML/JSON 路径，并报告失败命令。 |

## 飞书授权与租户安全

仅当用户明确要求发布到飞书时执行本节。

- 写入飞书前，先检查 `lark-cli config show` 和 `lark-cli auth status`。
- 如果当前应用或用户在错误租户：
  - 只有在用户同意后，才清理旧配置：
    ```bash
    lark-cli config remove
    ```
  - 重新初始化：
    ```bash
    lark-cli config init --new
    ```
  - 再请求用户授权：
    ```bash
    lark-cli auth login --scope "docx:document:create" --no-wait --json
    ```
- 使用分段授权流程：先展示 URL/二维码并停下；用户确认授权后，再运行 `lark-cli auth login --device-code <code>`。
- 不要同时启动多个 device-code 轮询进程。重新生成授权链接前，先清理旧的 `lark-cli auth login --device-code ...` 进程。

## 常见产物

- 完整原始归档：包含全部划线和个人想法的 Markdown/JSON。
- 通用洞察笔记：按大章节和二级分类组织的 Markdown。
- 飞书读书文档：按大章节和二级分类组织的 XML，并发布成飞书文档。
- 阅读友好版：不含时间、位置、分割线，以划线为主组织记录。

## 测试提示词

修改 skill 后，用这些提示词验证：

1. `帮我把《金钱心理学》的微信读书划线、我的笔记、我点赞的观点整理成 Markdown，按大章节和二级分类排版。`
2. `这本书只要本地 XML/JSON/Markdown，不要创建飞书文档；不要时间、位置、链接和分割线。`
3. `更新这个飞书文档：<doc_url>。划线优先，笔记和我点赞的观点都放引用块里，别人的评论不要放。`
4. `整理成 Obsidian 能直接放进 vault 的 Markdown。`

## 脚本

使用：

```bash
python3 ~/.codex/skills/weread-insight-notes/scripts/export_weread_notes.py \
  --book-id 3300129936 \
  --title "金钱心理学" \
  --out-dir exports \
  --include-liked
```

然后根据用户指定目标，返回本地文件路径，或用生成的 XML 创建/更新飞书文档。
