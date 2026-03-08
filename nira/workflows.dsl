# Example Nira workflows DSL

workflow morning_boot permission=standard:
  open_app target="notepad.exe"
  open_url url="https://www.bing.com"

workflow quick_capture permission=standard:
  take_screenshot path="C:\\Users\\Public\\Pictures\\nira_capture.png"

