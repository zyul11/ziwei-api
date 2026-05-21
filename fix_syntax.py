#!/usr/bin/env python3
"""Fix the backend main.py syntax error."""
with open('/home/ubuntu/ziwei-api/api/main.py') as f:
    c = f.read()

# Find if __name__ and fix
idx = c.find('if __name__ == "__main__":')
if idx >= 0:
    rest = c[idx:]
    # Check if uvicorn is in the rest
    if 'uvicorn.run' not in rest:
        c = c[:idx] + 'if __name__ == "__main__":\n    import uvicorn\n    uvicorn.run("api.main:app", host="0.0.0.0", port=8119, reload=True)\n'
    with open('/home/ubuntu/ziwei-api/api/main.py', 'w') as f:
        f.write(c)
    print("Fixed __main__ block")

# Verify syntax
import ast
try:
    ast.parse(c)
    print("Syntax: OK")
except SyntaxError as e:
    print(f"Syntax error: {e}")
    lines = c.split('\n')
    err = e.lineno
    for i in range(max(0,err-3), min(len(lines),err+3)):
        print(f'{i+1}: {lines[i]}')
