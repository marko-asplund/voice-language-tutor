#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
version="$(cat .node-version)"
case "$(uname -m)" in aarch64) arch=arm64 ;; x86_64) arch=x64 ;; *) echo 'Unsupported architecture' >&2; exit 1 ;; esac
if test -x .tools/node/bin/node; then
  test "$(.tools/node/bin/node --version)" = "v$version"
  exit
fi
work="$(mktemp -d /tmp/voice-tutor-node.XXXXXX)"
trap 'rm -rf "$work"' EXIT
archive="node-v${version}-linux-${arch}.tar.xz"
curl -fsSL "https://nodejs.org/dist/v${version}/SHASUMS256.txt" -o "$work/SHASUMS256.txt"
curl -fsSL "https://nodejs.org/dist/v${version}/${archive}" -o "$work/$archive"
(cd "$work"; awk -v file="$archive" '$2 == file' SHASUMS256.txt | sha256sum --check --strict)
mkdir -p .tools
tar -xJf "$work/$archive" -C .tools
ln -s "node-v${version}-linux-${arch}" .tools/node
