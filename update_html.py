
import os

file_path = "templates/index.html"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Find the start of the script tag
start_marker = "<script>"
end_marker = "</script>"
start_idx = content.rfind(start_marker)
end_idx = content.rfind(end_marker)

if start_idx != -1 and end_idx != -1:
    # We want to keep the closing </script> tag
    new_content = content[:start_idx] + '<script src="/static/js/app.js">' + content[end_idx:]
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully updated index.html")
else:
    print(f"Could not find script tags. Start: {start_idx}, End: {end_idx}")
