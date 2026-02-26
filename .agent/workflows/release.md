---
description: How to automate the release of getnotes-cli to PyPI
---

# Release Process

// turbo-all

## Steps

1. Configure Python path and UV
```bash
export PATH="$HOME/.cargo/bin:$PATH"
```

2. Read the current version from pyproject.toml
```bash
CURRENT_VERSION=$(grep -m 1 '^version = ' pyproject.toml | cut -d '"' -f 2)
echo "Current version is: $CURRENT_VERSION"
```

3. Ensure you're on the main branch and it's up to date
```bash
git checkout main
git pull origin main
```

4. Ask the user for the new version number
```bash
# INTERACTIVE: Ask user for the new version number (e.g., 0.1.1)
# You must pause here and ask the user for X.Y.Z
```

5. Bump version in pyproject.toml
```bash
# Replace NEW_VERSION with the version provided by the user
NEW_VERSION="WAITING_FOR_USER"
sed -i '' "s/version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
```

6. Update `CHANGELOG.md` with the new version entry (ask user for details if needed)

7. Commit all changes:
```bash
git add pyproject.toml CHANGELOG.md
git commit -m "chore: release v$NEW_VERSION"
```

8. Push and tag:
```bash
git tag "v$NEW_VERSION"
git push origin main
git push origin "v$NEW_VERSION"
```

9. Create a GitHub release to trigger PyPI publish:
```bash
gh release create "v$NEW_VERSION" --title "v$NEW_VERSION" --generate-notes
```

## Checklist

- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG updated
- [ ] Committed and pushed
- [ ] Tagged and pushed tag
- [ ] GitHub release created (triggers PyPI publish via publish.yml)
