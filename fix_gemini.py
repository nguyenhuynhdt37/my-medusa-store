with open("chatbot-service/app/clients/gemini_client.py", "r") as f:
    lines = f.readlines()

method_lines = lines[287:307] # 20 lines (from line 288 to 307)
del lines[287:307]

# Insert after line 221 (index 221)
lines.insert(221, "\n")
lines[222:222] = method_lines

with open("chatbot-service/app/clients/gemini_client.py", "w") as f:
    f.writelines(lines)
