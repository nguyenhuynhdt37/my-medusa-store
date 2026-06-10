import json

with open("chatbot-service/app/api/chat_gateway.py", "r") as f:
    content = f.read()

# We only want edits from the transcript BEFORE step 3596
with open("/Users/huynh/.gemini/antigravity-ide/brain/cbe49369-5b60-4b46-a106-14bfef0be846/.system_generated/logs/transcript.jsonl") as f:
    for line in f:
        data = json.loads(line)
        if data.get("step_index", 0) >= 3596:
            break
        if data.get("source") == "MODEL" and data.get("type") == "PLANNER_RESPONSE":
            tool_calls = data.get("tool_calls", [])
            for call in tool_calls:
                name = call.get("name")
                if name in ["replace_file_content", "multi_replace_file_content"]:
                    args = call.get("args", {})
                    target_file = args.get("TargetFile", "")
                    if "chat_gateway.py" in target_file:
                        if name == "replace_file_content":
                            chunks = [args]
                        else:
                            # It is already a list in the parsed JSON tree
                            chunks = args.get("ReplacementChunks", [])
                            if isinstance(chunks, str):
                                try:
                                    chunks = json.loads(chunks)
                                except Exception:
                                    chunks = []
                        
                        for chunk in chunks:
                            target = chunk.get("TargetContent", "")
                            replacement = chunk.get("ReplacementContent", "")
                            if target in content:
                                content = content.replace(target, replacement)
                                print(f"Applied chunk in step {data['step_index']}")
                            else:
                                print(f"Failed to apply chunk in step {data['step_index']}")

with open("chatbot-service/app/api/chat_gateway.py", "w") as f:
    f.write(content)
