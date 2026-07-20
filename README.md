# weread-insight-notes

微信读书洞察笔记 skill：把微信读书里的划线、个人笔记、本人点赞过的观点，整理成结构化读书笔记。

默认输出通用 `Markdown / JSON / XML`，不绑定飞书。用户指定目标时，可进一步同步到飞书、Obsidian、WPS 笔记或其他知识库。

## 输出格式

```markdown
# 大章节

## 二级分类

1. 原文划线：用户在微信读书划过的原文
   > 我的笔记：用户自己写在这条划线上的想法
   > 我点赞的观点（作者）：用户自己点过赞的观点
```

默认不显示时间、位置、range、跳转链接和分割线。

## 安装

```bash
npx skills add MondayLabOS/weread-insight-notes -g
```

或手动复制本仓库到本地 skills 目录：

```bash
~/.codex/skills/weread-insight-notes
```

## 依赖

- 已安装并授权微信读书 skill
- `WEREAD_API_KEY` 已写入环境变量或 macOS 用户会话
- 只生成本地 Markdown/JSON/XML 时，不需要飞书授权
- 如果要发布到飞书，需要可用的 `lark-cli` 用户授权

## 典型提示词

生成通用洞察笔记：

```text
用 weread-insight-notes，把《书名》的微信读书划线、我的笔记、我点赞过的观点整理成结构化洞察笔记。
按大章节做一级标题，按内容做二级分类。
每条记录以原文划线为主；如果这条划线有我的笔记或我点赞的观点，放在引用块里。
不要显示时间、位置、range、跳转链接和分割线。
默认生成本地 Markdown、JSON 和 XML，不要主动创建飞书文档。
```

生成 Obsidian 版本：

```text
用 weread-insight-notes，把《书名》的微信读书划线、我的笔记、我点赞过的观点整理成 Obsidian 能直接放进 vault 的 Markdown。
按大章节和二级分类组织；划线优先，笔记和我点赞的观点放引用块。
不要时间、位置、range、跳转链接和分割线。
```

发布到飞书：

```text
用 weread-insight-notes，把《书名》的微信读书划线、我的笔记、我点赞过的观点整理成飞书文档。
按大章节做一级标题，按内容做二级分类。
划线优先，个人笔记和我点赞过的观点放引用块。
不要时间、位置、range、跳转链接和分割线。
创建到我当前授权的飞书租户里，并返回文档链接。
```

## 脚本

```bash
python3 scripts/export_weread_notes.py \
  --book-id 3300129936 \
  --title "金钱心理学" \
  --out-dir exports \
  --include-liked
```

输出：

- `<书名>-insight-notes.md`
- `<书名>-weread-notes.json`
- `<书名>-notes.xml`

## 口径

- `原文划线` 来自微信读书划线。
- `我的笔记` 是用户自己写在划线上的想法。
- `我点赞的观点` 是用户本人点赞过的观点，通过 `/book/readreviews` 筛选 `isLike=1`。
- 别人对用户笔记的点赞数、评论数，不等于用户点赞过的观点，默认不放。
- 如果个人笔记没有匹配到划线，保留为 `关联原文 + 我的笔记`。
