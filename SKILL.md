---
name: weread-insight-notes
description: 将微信读书的划线、个人笔记、本人点赞过的观点及划线对应原图沉淀成结构化洞察笔记。适用于整理读书笔记、补齐插图、生成 Markdown/JSON/XML，以及同步到飞书、Obsidian 或其他知识库。
---

# 微信读书洞察笔记

用于把一本微信读书里的阅读痕迹整理成可复用的结构化知识资产。默认先产出通用 Markdown/JSON，以及可发布到飞书的 XML；用户指定目标时，再同步到飞书、Obsidian、WPS 笔记或其他知识库。

核心输出格式：

```text
# 大章节

## 二级分类

1. 原文划线：用户在微信读书划过的原文
   [对应的原书插图，如有]
   > 我的笔记：用户自己写在这条划线上的想法
   > 我点赞的观点（作者）：用户自己点过赞的观点
```

## 依赖条件

- 微信读书 skill 已安装在 `~/.codex/skills/weread-skills`，或具备等价能力。
- `WEREAD_API_KEY` 已写入环境变量或 macOS 用户会话，可用 `launchctl getenv WEREAD_API_KEY` 检查。
- 只生成本地 Markdown/JSON/XML 时，不需要飞书授权。
- 如果要发布到飞书，`lark-cli` 必须已配置到目标飞书租户，并完成用户身份授权。
- 飞书文档使用 `lark-cli docs +create|+update`；以当前安装版本的帮助和文档技能为准，不照搬旧版本的 `--api-version v2` 参数。
- 需要补齐原图而 API 没有图片资源时，使用环境中可用的浏览器技能和用户已授权的微信读书阅读页。没有阅读权限的图片保留为待补齐项。

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

   检查插图线索。用户要求包含图片，或原文出现 `[插图]`、`U+FFFC` 时，阅读 [原图识别、导出与同步](references/image-sync.md)。先辨别插图和脚注，再把确认的原图按 `bookId + chapterUid + range` 绑定到记录；一条划线可以有多张原图。不要将整章图片都当成用户划线。

4. 判断输出目标。
   - 用户没有指定目标时：只返回本地 Markdown/JSON/XML 文件路径。
   - 用户说 Obsidian：优先交付 Markdown，可放入用户指定 vault 或文件夹。
   - 用户说 WPS 笔记、语雀、Notion 或其他知识库：优先交付 Markdown；如有对应 CLI/API，再按目标系统发布。
   - 用户说飞书：使用生成的 XML 创建或更新飞书文档。

5. 发布到飞书时：
   - 新建文档：
     ```bash
     cd exports
     lark-cli docs +create --as user --doc-format xml --content @./<file>.xml --parent-position my_library
     ```
   - 追加到已有文档：先 fetch，生成不含 `<title>` 的追加片段，再执行：
     ```bash
     cd exports
     lark-cli docs +update --as user --doc <doc_token_or_url> --command append --doc-format xml --content @./<fragment>.xml
     ```
   - 只补图片时按对应条目做局部更新，遵循 [图片同步参考](references/image-sync.md)；图片放在原文后、个人笔记和点赞观点前。
   - 有图片的 XML 中 `@./images/...` 相对导出目录解析，运行发布命令时进入该目录，或按实际执行目录调整路径。
   - 逐次 fetch 验证写入结果；整篇覆盖仅用于用户明确要求重建文档。

6. 返回文件路径、发布链接和关键数量统计；包含图片时报告成功插入的原图数量及仍未补齐的记录。

## 默认理解用户需求

当用户要求整理一本新书的读书笔记时，默认目标是：

```text
把《书名》的微信读书划线、我的笔记、我点赞过的观点整理成结构化洞察笔记。
按大章节做一级标题，按内容做二级分类。
每条记录以原文划线为主；如果这条划线有我的笔记或我点赞的观点，放在引用块里。
不要显示时间、位置、range、跳转链接和分割线。
默认先生成本地 Markdown、JSON 和 XML；只有用户指定飞书时才创建或更新飞书文档。
```

用户提供飞书文档 token 或 URL 即指定了目标；结合用户要求选择追加或局部编辑，不默认覆盖，不重复索取已有授权。如果用户给的是本地文件夹路径，把 Markdown 写入该路径。如果用户要求新建飞书文档，在当前用户授权的目标租户里创建，并返回链接。

## 格式规则

- 微信读书的 `chapterUid` 往往是小节，不一定是大章。遇到很多 `level=2` 小节时，把内容归到最近的上一级 `level=1` 大章下面。
- 大章使用 `h1`。
- 二级分类使用 `h2`，根据书名、章节名、划线文本、个人笔记和点赞观点共同判断。
- 除非用户明确要求可追溯信息，否则不要显示时间、range、位置或深度链接。
- 每条记录优先展示原文划线。
- 有对应原图时，把原图放进同一条记录，顺序为原文、图片、个人笔记、点赞观点。保留占位文本作为原始资料，不把脚注当图片，也不以截图、重画或生成图冒充原图。
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
| 用户提供已有飞书文档 token | fetch 现状，按用户要求追加或局部修改；不要默认 overwrite。 |
| 只得到图片占位符，未取到原图 | 保留原文和心得，记录未补齐的 chapterUid/range 及原因；不猜测图片 URL 或图文对应关系。 |
| XML 上传失败 | 保留已生成的 Markdown/XML/JSON 路径，并报告失败命令。 |

## 飞书授权与租户安全

仅当用户明确要求发布到飞书时执行本节。

- 写入飞书前，先检查 `lark-cli config show` 和 `lark-cli auth status`；有多个已授权 profile 时，优先选择能访问用户目标文档的 profile，并在 fetch/update 中保持一致。不要将本次会话的 profile 名或文档 token 写死到技能中。
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
5. `划线里有一些图片，帮我把原图补到已有飞书笔记的对应条目下，保留我的心得和编号，不要重复插入。`
6. `用已导出的 JSON 和我核对过的图片清单生成带原图的 Markdown/XML，不重新调用微信读书。`

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

带原图的离线重导出使用 `--input-json` 与 `--image-manifest`，清单结构和用法见 [图片同步参考](references/image-sync.md)。脚本验证绑定、复制原图到输出目录，并生成含图片的 Markdown/JSON/XML；图片识别、阅读页导出和飞书局部编辑由该参考指导。
