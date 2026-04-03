# VariaType — 10.129.244.202

## Attack Chain Summary
1. Git dump on portal → gitbot creds
2. Portal LFI (download.php ....// bypass) → read Flask source
3. Designspace format 5.0 variable-font filename → output path traversal
4. PHP polyglot font written as cmd.php → RCE as www-data
5. TODO: escalate to steve → root

## Key Learning
Input extension was checked (.ttf/.otf). Output extension was NOT.
Think about what the code PRODUCES, not just what it accepts.
