import re
from collections import Counter

with open('templates/result.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all opening and closing tags
opening_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*(?<!/)>', content)
closing_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9]*)>', content)

# Count tags
opening_count = Counter(opening_tags)
closing_count = Counter(closing_tags)

# Self-closing tags that don't need closing tags
self_closing = {'br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'source', 'track', 'wbr', 'circle'}

# Find unmatched tags
unmatched = []
for tag in set(opening_tags + closing_tags):
    if tag in self_closing:
        continue
    if opening_count[tag] != closing_count[tag]:
        unmatched.append(f'{tag}: {opening_count[tag]} opening, {closing_count[tag]} closing')

if unmatched:
    print('Unmatched HTML tags:')
    for tag in unmatched:
        print(f'  {tag}')
else:
    print('All HTML tags are properly matched!')

# Check for common issues
print(f'\nTag statistics:')
print(f'Total opening tags: {len(opening_tags)}')
print(f'Total closing tags: {len(closing_tags)}')
print(f'Most common tags: {opening_count.most_common(5)}')