find . -type f \( -name "*.py" -o -name "*.vue" \) -exec wc -l {} +|sort -nr
