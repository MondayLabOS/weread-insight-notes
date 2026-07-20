# 会话沉淀

这个 skill 来自一次把微信读书笔记整理成飞书文档的完整工作流，但核心能力不应绑定飞书；飞书只是可选输出目标之一。

关键经验：

- 微信读书的 `chapterUid` 可能代表小节，不一定是书籍大章。用 `chapterinfo.level=1` 作为大章，把小节内容归到大章下面。
- `/book/bookmarklist` 返回划线文本。
- `/review/list/mine` 返回用户自己的个人想法，以及对应的 `abstract`。
- 个人想法和划线用 `(chapterUid, range)` 匹配。
- 有些个人想法在 `/book/bookmarklist` 里找不到匹配划线，要保留为独立记录。
- `/review/list/mine` 里可能有 `likesCount` 和 `commentsCount`，这是别人对用户想法的互动，不是用户自己的关注点，默认不要放。
- “我点赞过的观点”需要对划线 range 调 `/book/readreviews`，筛选 `isLike=1` 的 review。
- `/review/single` 可以取单条 review 详情，但通过 skill gateway 不一定能稳定拿到完整评论正文。
- 默认输出应是通用 Markdown/JSON/XML，方便进入 Obsidian、WPS 笔记、飞书或其他知识库。
- 发布到飞书时，必须用正确租户和 `--as user`。bot 身份可能把文档创建到应用租户，后续删除也更麻烦。
- 如果创建到了错误飞书租户，可在启用 `space:document:delete` 后，用 `lark-cli drive +delete --as bot --type docx --file-token <token> --yes` 删除。
