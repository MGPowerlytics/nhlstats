def get_nesting_depth(line):
    return (len(line) - len(line.lstrip())) // 4


with open("dashboard/dashboard_app.py", "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    depth = get_nesting_depth(line)
    if depth >= 5:
        print(f"Line {i + 1}: Depth {depth} - {line.strip()[:50]}")
