# Publishing `openbenchml-cli` to npm

This guide walks you through publishing the OpenBenchML CLI to the npm registry
so anyone can install it with `npm install -g openbenchml-cli`.

**Author / Maintainer:** Kartheek BVS `<bvskartheek83@gmail.com>`
**Package name:** `openbenchml-cli`
**Current version:** `4.2.0`
**Registry:** https://registry.npmjs.org/
**License:** MIT

---

## 1. One-time setup — create your npm account

1. Go to <https://www.npmjs.com/signup>.
2. Sign up with email **`bvskartheek83@gmail.com`** and a username of your choice
   (e.g. `kartheekbvs`).
3. Verify the email — npm will email a 6-digit code to `bvskartheek83@gmail.com`.
   Enter it on the npm site.
4. (Recommended) Enable **2FA**:
   *Avatar → Account Settings → Two-Factor Authentication →** set to
   `auth-and-writes`. Save the recovery codes somewhere safe.

## 2. Log in from this machine

```bash
cd /home/z/my-project/download/openbenchml/packages/openbenchml-cli
npm login
```

You'll be prompted for:

| Prompt             | Value                                  |
| ------------------ | -------------------------------------- |
| npm user name      | your npm username (e.g. `kartheekbvs`) |
| Password           | your npm password                      |
| Email              | `bvskartheek83@gmail.com` (prefilled)  |
| OTP (if 2FA on)    | 6-digit code from your authenticator   |

`npm login` writes a token to `~/.npmrc`. Verify it worked:

```bash
npm whoami
# → kartheekbvs
```

## 3. Dry-run the publish (always do this first)

This packs the package exactly the way `npm publish` will, **without**
uploading anything. It lets you sanity-check which files are included.

```bash
npm pack --dry-run
```

You should see a list containing only:

```
package.json
README.md
LICENSE
bin/openbenchml.js
src/client.js
src/command.js
src/index.js
```

If you see `node_modules/`, `.env`, `package-lock.json` or anything else you
don't want published, fix the `files` array in `package.json` (already
configured correctly above).

## 4. Bump the version (if you haven't already)

```bash
# patch  : 4.2.0 → 4.2.1   (bug fix)
# minor  : 4.2.0 → 4.3.0   (new feature, backwards compatible)
# major  : 4.2.0 → 5.0.0   (breaking change)
npm version patch   # or `minor`, or `major`
```

`npm version` will:
1. Edit `package.json`'s `version` field.
2. Create a git commit `v4.2.1`.
3. Create a git tag `v4.2.1`.

Push the tag so GitHub has it:

```bash
git push origin main --tags
```

## 5. Publish 🚀

```bash
npm publish
```

If 2FA is on, npm will ask for a one-time code from your authenticator app.
After the upload finishes (usually < 10 seconds) you'll see:

```
+ openbenchml-cli@4.2.0
```

Your package is now live at:
**<https://www.npmjs.com/package/openbenchml-cli>**

Anyone can now install it:

```bash
npm install -g openbenchml-cli
# or
npx openbenchml-cli --help
```

## 6. Verify the published package

```bash
npm view openbenchml-cli
```

You should see your name (`kartheekbvs`) and email
(`bvskartheek83@gmail.com`) in the maintainers list.

Test the global install in a fresh shell:

```bash
npx --yes openbenchml-cli --version
# → 4.2.0

npx --yes openbenchml-cli --help
```

## 7. Updating the package later

Every time you want to push a new version:

```bash
cd packages/openbenchml-cli
# edit code...
npm version patch         # bump + git tag
npm publish               # upload
git push origin main --tags
```

## 8. Unpublishing / deprecating

npm only lets you unpublish within **72 hours** of publishing. After that you
can only deprecate:

```bash
npm deprecate openbenchml-cli@"<version>" "Use openbenchml-cli@latest instead"
```

## 9. Common errors

| Error                                                       | Fix                                                                                                                       |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `403 Forbidden - You do not have permission to publish`    | The package name is already taken. Pick a scoped name like `@kartheekbvs/openbenchml-cli` and update `package.json`.     |
| `402 Payment Required`                                      | You're trying to publish a private package. Make sure `publishConfig.access` is `"public"` (it is, by default).           |
| `ENEEDAUTH`                                                 | Run `npm login` again. Your `~/.npmrc` token may have expired.                                                            |
| `EOTP`                                                      | You have 2FA on. Re-run `npm publish` and enter the 6-digit code from your authenticator when prompted.                  |
| `You cannot publish over the previously published versions`| Bump the version first: `npm version patch`.                                                                              |

---

## tl;dr — minimum command sequence

```bash
cd packages/openbenchml-cli
npm login                      # one-time, then npm whoami to verify
npm pack --dry-run             # sanity check
npm version patch              # bump
npm publish                    # upload — enter 2FA code if prompted
git push origin main --tags
```
