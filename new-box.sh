#!/bin/bash
# Usage: ./scripts/new-box.sh <name>
name="${1:?Usage: new-box.sh <name>}"
cp -r machines/.template "machines/$name"
sed -i "s/Box Name/$name/" "machines/$name/notes.md"
echo "Created machines/$name"
