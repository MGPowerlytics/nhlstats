import re
import sys

def fix_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        # Skip header/markdown lines
        if line.strip().startswith('### '):
            continue
        if line.strip().startswith('```'):
            continue

        # Remove line numbers like "1: ", "100: "
        # Regex: start of line, optional whitespace, digits, colon, optional whitespace
        # We capture the rest of the line
        match = re.match(r'^\s*\d+:(.*)', line)
        if match:
            # Re-add newline if it was stripped or missing (though capturing group usually keeps it if we are careful)
            # The capture group (.*) might not include newline if . does not match newline.
            # Let's use replacement instead.
            cleaned_line = re.sub(r'^\s*\d+:\s?', '', line, count=1)
            new_lines.append(cleaned_line)
        else:
            # If no line number, keep line as is?
            # But the file seems consistent. Let's assume lines without numbers might be blank or corrupted differently.
            # Looking at `tail` output: "106:\n" -> just "\n" after strip?
            # actually `tail` showed "106:".
            # If a line is just empty in original code, `read_file` might output "N: \n".
            new_lines.append(line)

    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    print(f"Fixed {file_path}")

if __name__ == '__main__':
    fix_file('plugins/elo/wncaab_elo_rating.py')
