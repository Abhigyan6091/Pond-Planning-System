import markdown
import os
import re

md_path = os.path.join(os.path.dirname(__file__), "OPENTELEMETRY_REPORT.md")
html_path = os.path.join(os.path.dirname(__file__), "OPENTELEMETRY_REPORT.html")

with open(md_path, "r", encoding="utf-8") as f:
    text = f.read()

# Replace absolute file URIs with relative image paths for HTML portability
text_rel = re.sub(r"file:///c:/Users/Abhigyan%20Sharma/OneDrive/Desktop/Contour/", "", text)

html_body = markdown.markdown(text_rel, extensions=["tables", "fenced_code"])

full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenTelemetry Technical Report | Village Pond Planning System</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Outfit', -apple-system, sans-serif;
      line-height: 1.65;
      color: #1e293b;
      background: #f8fafc;
      padding: 2.5rem;
      max-width: 1000px;
      margin: 0 auto;
    }}
    h1, h2, h3, h4 {{ color: #0f172a; margin-top: 1.75rem; margin-bottom: 0.75rem; font-weight: 700; }}
    h1 {{ font-size: 2.2rem; border-bottom: 2px solid #0284c7; padding-bottom: 0.5rem; color: #0284c7; }}
    h2 {{ font-size: 1.5rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.4rem; margin-top: 2.5rem; color: #0369a1; }}
    h3 {{ font-size: 1.2rem; color: #334155; }}
    p, li {{ font-size: 0.95rem; color: #334155; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1.25rem 0; font-size: 0.88rem; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    th, td {{ padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid #e2e8f0; }}
    th {{ background: #f1f5f9; color: #475569; font-weight: 600; text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em; }}
    tr:hover {{ background: #f8fafc; }}
    code {{ font-family: 'JetBrains Mono', monospace; font-size: 0.85em; background: #f1f5f9; padding: 0.2rem 0.4rem; border-radius: 4px; color: #0284c7; }}
    pre {{ background: #0f172a; color: #f8fafc; padding: 1.25rem; border-radius: 8px; overflow-x: auto; margin: 1.25rem 0; }}
    pre code {{ background: transparent; color: #f8fafc; padding: 0; }}
    img {{ max-width: 100%; height: auto; border-radius: 8px; border: 1px solid #cbd5e1; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin: 1rem 0; }}
    hr {{ border: 0; height: 1px; background: #e2e8f0; margin: 2rem 0; }}
    @media print {{
      body {{ background: #fff; padding: 0; max-width: 100%; }}
      img {{ max-width: 95%; page-break-inside: avoid; }}
      h2, h3 {{ page-break-after: avoid; }}
      pre, table {{ page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>
{html_body}
</body>
</html>"""

with open(html_path, "w", encoding="utf-8") as f:
    f.write(full_html)

print(f"Generated {html_path} successfully!")
