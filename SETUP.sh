#!/bin/bash
echo "Renaming .py.txt → .py ..."
for f in *.py.txt; do
  mv "$f" "${f%.txt}"
done
echo "Done! Run:  python triage.py --test-connections"
