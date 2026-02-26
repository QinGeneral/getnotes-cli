---
description: How to automate the release of getnotes-cli to PyPI
---

# Release Process

## Steps

1. 检索当前版本号，然后找我确认更新后的版本号是什么
```bash
CURRENT_VERSION=$(grep -m 1 '^version = ' pyproject.toml | cut -d '"' -f 2)
echo "Current version is: $CURRENT_VERSION"
```

2. 修改版本号和 changelog，然后提交
```bash
# Agent 注意：请先使用文件编辑相关工具修改 pyproject.toml 和 CHANGELOG.md，将版本号更新为确认后的版本。<NEW_VERSION> 替换为实际版本号。
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v<NEW_VERSION>"
```

3. 推代码，打 tag
```bash
git push origin main
git tag "v<NEW_VERSION>"
git push origin "v<NEW_VERSION>"
```

4. gh release
```bash
gh release create "v<NEW_VERSION>" --title "v<NEW_VERSION>" --generate-notes
```
