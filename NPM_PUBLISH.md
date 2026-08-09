# Publishing OpenBenchML to npm

The CLI lives at [`packages/openbenchml-cli/`](packages/openbenchml-cli/) and
is published to npm as
[`openbenchml-cli`](https://www.npmjs.com/package/openbenchml-cli).

**Author / Maintainer:** Kartheek BVS `<bvskartheek83@gmail.com>`

For the full step-by-step guide (account setup, 2FA, dry-run, version
bumping, error troubleshooting), see
[`packages/openbenchml-cli/NPM_PUBLISH.md`](packages/openbenchml-cli/NPM_PUBLISH.md).

## tl;dr

```bash
cd packages/openbenchml-cli
npm login                       # use email bvskartheek83@gmail.com
npm pack --dry-run              # sanity check
npm version patch               # bump 4.2.0 → 4.2.1
npm publish                     # enter 2FA code when prompted
git push origin main --tags
```

After publishing, anyone can install:

```bash
npm install -g openbenchml-cli
# or
npx openbenchml-cli --help
```
