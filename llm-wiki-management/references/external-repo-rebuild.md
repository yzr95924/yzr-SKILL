# 外部代码仓跨主机重建协议

> 适用：当 wiki 仓被 `git clone` 到一台新机器，但 `raw/external/<source-name>/`
> 下的 symlink 不在 git 里（spec §13.4 `.gitignore` 排除），需要从 anchor
> 重建外部源代码的链接。

## 原理：为什么 anchor 进 git、symlink 不进 git

```gitignore
raw/external/*              # symlink 不进 git（跨主机无意义：target 在新机器不存在）
!raw/external/**/.symlink-anchor.json  # anchor 进 git（记录接入意图）
```

anchor 文件**进 git** 是这一机制的根：

- symlink 本身是机器相关的——即使是 `~/src/linux` 在新机器也要重建（home-relative
  仅指同 home 布局的逻辑路径，跟机器绑定的文件系统不是一回事）
- 但 anchor 的 `remote_url` / `commit` / `branch` 三字段是**跨主机稳定**的——
  任何机器上的 LLM 读 anchor 都可还原"接入瞬间"的精确状态
- anchor 的 `target` 字段（0.14.0+ 推荐 `~/...` 形式，兼容绝对路径）——同 home
  布局的新机器直接可用；跨 home 布局的机器 LLM 重写。这正是
  `.symlink-anchor.json` 与 symlink 解耦的价值：**anchor 描述意图、
  symlink 描述当前主机的具体绑定**

## 重建触发

| 触发场景 | 用户感知 |
| --- | --- |
| 在新机器 `git clone` wiki 仓后，symlink 不存在 | `ls raw/external/` 看到 anchor 但没 symlink 文件 |
| 跑 `lint_wiki.py` 时大量 `external-target-dead` | target 路径在新机器不存在 |
| 用户主动在新机器重建（"我换了电脑 / 加了一台机器"） | 同上 |

## 重建步骤（agent 驱动）

新机器的 LLM agent 跑下列流程：

### Step 1 — 读 anchor

```bash
# 找到所有需要重建的 anchor
find raw/external -name .symlink-anchor.json
```

每个 anchor 必须含 `remote_url` / `commit` / `branch` 三个 git 扩展字段（spec §13.5）；
若缺一个，跑 `lint_wiki.py` 会报 `external-git-anchor-incomplete`，需要先在**原机器**补齐再 push。

### Step 2 — 决定目标路径

约定 `<source-name>` 的 target 落在新机器的 `~/src/<source-name>/`（可与用户协商改其他路径）。
本字段会写入 anchor 的 `target`（0.14.0+ 推荐 `~/...` 形式，让同 home 布局的同 wiki
仓的其它机器共享）：

```bash
TARGET_ABS="$HOME/src/<source-name>"   # git clone 的真实落地路径
TARGET_ANCHOR="~/src/<source-name>"    # 写回 anchor 的 target 字段
```

### Step 3 — clone + checkout

```bash
git clone "$remote_url" "$TARGET_ABS"
cd "$TARGET_ABS"
git checkout "$commit"  # 切到 anchor 记录的精确 commit
# 若 anchor 含可选字段 subpath，symlink 应指向 $TARGET_ABS/$subpath（见 step 4）
```

### Step 4 — 创建 symlink + 更新 anchor

```bash
mkdir -p "raw/external/<source-name>"
if [ -n "$subpath" ]; then
  ln -s "$TARGET_ABS/$subpath" "raw/external/<source-name>/<symlink-name>"
else
  ln -s "$TARGET_ABS" "raw/external/<source-name>/<symlink-name>"
fi
```

最后**用 `~/...` 形式覆盖 anchor 的 `target` 字段**（0.14.0+ 推荐；老 anchor 写绝对路径也兼容）：

```bash
# 用脚本而非手写更稳：先把 anchor 读成 dict、改 target、写回
python3 -c "
import json, sys, pathlib
p = pathlib.Path('raw/external/<source-name>/.symlink-anchor.json')
data = json.loads(p.read_text())
data['target'] = '~/src/<source-name>'   # 0.14.0+ 推荐 home-relative
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
"
```

`remote_url` / `commit` / `branch` 三个字段**保持原值不动**——它们是接入意图，不是机器状态。

### Step 5 — 验证

```bash
# symlink 是否能解析到 target
readlink -f raw/external/<source-name>/<symlink-name>

# lint 跑通（不应再报 external-target-dead / external-git-anchor-stale）
# 注意 lint 端会做 Path(target).expanduser()，所以 '~/src/...' 形式 + 同 home 布局下不报 dead
python3 ../path/to/scripts/lint_wiki.py .
```

## 与日常接入的关系

- **首次接入**（用户说"把 X 仓纳入 wiki"）：见 SKILL.md §1.bulk 外部代码仓子节与
  spec §13.3；LLM 在**原机器**跑 5 步接入
- **跨主机重建**（在新机器复现）：本文件；LLM 在**新机器**跑 4 步重建
- **漂移刷新**（用户日常 `git pull` 触发）：spec §13.5；LLM 重读 git 三字段后
  Edit anchor，**target 字段不动**

## 反模式

- **不要在新机器直接 `cp -r` 外部仓到 wiki 仓内**——失去 commit 锚点 + 占用空间 +
  违反 spec §13 纪律（SKILL.md 反模式清单末条）
- **不要修改 anchor 的 `remote_url` / `commit` / `branch`**——这三字段是接入意图，
  不是机器状态；新机器若需要升级 commit，请 Edit `commit` 字段并在原机器 push，
  让所有机器同步刷新
- **不要绕过 anchor 直接 `ln -s`**——没有 anchor 的 symlink = lint 报
  `external-anchor-missing`，且新机器无法重建
- **不要把 symlink 文件本身 commit 进 git**——已由 `.gitignore` 排除，强行 `--force`
  add 会污染仓

## 失败兜底

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `git clone` 失败：remote not found | `remote_url` 拼错 / 已删除 / 私有 repo 缺凭据 | 检查 remote_url；私有 repo 配 SSH key 或 token |
| `git checkout <commit>` 失败：object not found | remote 已 force-push / commit 被 rebase 改写 | 询问用户：保留 anchor commit（指向 dangling commit）还是选新 commit？ |
| `readlink -f` 显示 anchor 路径不存在 | symlink 写错 / target 未建好 | 检查 step 3 4 路径字面量 |
| `lint_wiki.py` 报 `external-git-anchor-stale` | clone 下来后又跑了 `git pull` / 切了分支 | 重跑本文件 step 4，更新 `target` 字段；若接受新 commit 则按漂移刷新走 |
| 找不到 `git` CLI | 新机器没装 git | 装 git 后重跑；这是 lint `external-git-anchor-incomplete` 报错的子信号 |
